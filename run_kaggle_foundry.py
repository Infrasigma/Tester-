#!/usr/bin/env python3
"""Kaggle entrypoint for the private ACSIE Gen3 Foundry.

The kernel runs without internet. It writes one generation bundle per seed and
generation, a SHA-256 artifact manifest, and a compact receipt candidate. The
candidate is never published from the research kernel itself.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import io
import json
import multiprocessing
import os
import platform
import queue
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import traceback
import unittest
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SEEDS = (771221, 771222, 771223, 771224, 771225)
STATUS = {"PASSED", "FAILED", "BLOCKED", "CRASHED", "INVALID", "INCONCLUSIVE"}
# The embedded-source builder binds the effective deployment configuration.
DEPLOYMENT_KERNEL_ID = None
DEPLOYMENT_GPU_REQUESTED = False
DEPLOYMENT_PROFILE_ONLY = False
INTEGRITY_FLAGS = (
    "external_model", "pretrained_model", "embeddings", "external_api",
    "hidden_prompt", "task_family_routing", "target_access_during_discovery",
    "holdout_used_for_training", "holdout_used_for_selection",
    "transfer_used_for_selection", "hidden_strategy", "network_dependency",
)
def _resolve_package_root() -> Path:
    """Resolve the verified package extracted from the private Kaggle input dataset."""
    here = Path(__file__).resolve().parent
    required = (
        "run_kaggle_foundry.py",
        "source-manifest.json",
        "research/gen3_learning_rule_foundry_v1.py",
        "research/tests/test_emit_validated_receipt.py",
        "research/tests/test_gen3_foundry_generations.py",
        "scripts/archive_foundry_outputs.py",
        "scripts/tests/test_archive_foundry_outputs.py",
    )

    def is_package(candidate: Path) -> bool:
        return candidate.is_dir() and all((candidate / item).is_file() for item in required)

    if is_package(here):
        return here

    input_root = Path("/kaggle/input")
    if input_root.is_dir():
        archives = list(input_root.glob("*/acsie-gen3-foundry-package.tar.gz"))
        if not archives:
            archives = list(input_root.rglob("acsie-gen3-foundry-package.tar.gz"))
        for archive_path in archives:
            destination = Path("/kaggle/working/acsie-gen3-foundry-package")
            if is_package(destination):
                return destination
            if destination.exists():
                import shutil
                shutil.rmtree(destination)
            destination.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive_path, mode="r:gz") as archive:
                members = archive.getmembers()
                for member in members:
                    member_path = Path(member.name)
                    if (member_path.is_absolute() or ".." in member_path.parts
                            or member.issym() or member.islnk()):
                        raise RuntimeError("private source archive contains an unsafe path")
                archive.extractall(destination, members=members)
            if is_package(destination):
                return destination

        manifests = list(input_root.glob("*/source-manifest.json"))
        if not manifests:
            manifests = list(input_root.rglob("source-manifest.json"))
        for manifest_path in manifests:
            candidate = manifest_path.parent
            if is_package(candidate):
                return candidate

    # Keep the original path so Phase 0 emits a precise missing-package report.
    return here

ROOT = _resolve_package_root()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def safe_status(value: Any) -> str:
    return value if value in STATUS else "INVALID"


def load_source_manifest() -> dict[str, Any]:
    path = ROOT / "source-manifest.json"
    if not path.is_file():
        raise RuntimeError("source manifest is missing")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    commit = manifest.get("source_commit")
    if (manifest.get("repository") != "Infrasigma/ACSIE"
            or not isinstance(commit, str)
            or not re.fullmatch(r"[0-9a-f]{40}", commit)):
        raise RuntimeError("source manifest is invalid")
    if manifest.get("network_during_research") is not False:
        raise RuntimeError("research kernel must have internet disabled")
    return manifest


def fallback_seed(seed: int, run_error: dict[str, Any], checkpoint_dir: Path) -> dict[str, Any]:
    generations = []
    for generation in range(12):
        status = "CRASHED" if generation == 0 else "BLOCKED"
        evaluated = False
        record = {
            "generation": generation,
            "scientific_status": status,
            "evaluated": evaluated,
            "reason": "foundry_driver_exception" if generation == 0 else "blocked_by_prior_generation_exception",
            "candidate_count": 0,
            "selected_program_sha256": None,
            "state_in_sha256": None,
            "state_out_sha256": None,
            "fitness": None,
            "replay_exact": False,
            "persistent_state_roundtrip": False,
            "persistent_state_delta": False,
            "candidate_crash_count": 0,
            "gen_duration_sec": 0.0,
            "result_sha256": canonical_sha256({
                "seed": seed, "generation": generation, "scientific_status": status,
                "evaluated": evaluated,
            }),
        }
        bundle = {
            "schema": "ACSIE.gen3-foundry-generation-checkpoint.v1",
            "seed": seed,
            "generation": generation,
            "checkpoint_available": False,
            "generation_record": record,
            "error": run_error if generation == 0 else {"reason": "blocked_by_prior_generation_exception"},
        }
        path = checkpoint_dir / f"generation-{generation:02d}.json"
        write_json(path, bundle)
        record["checkpoint_path"] = path.as_posix()
        generations.append(record)
    return {
        "version": "gen3-learning-rule-foundry-v1",
        "seed": seed,
        "scientific_status": "CRASHED",
        "passed": False,
        "reason": "foundry_driver_exception",
        "generation_count": 12,
        "generations": generations,
        "final_metrics": {},
        "integrity": {flag: False for flag in INTEGRITY_FLAGS},
        "runner_error": run_error,
    }


def matrix_row(seed_result: dict[str, Any], seed: int) -> dict[str, Any]:
    raw_gens = seed_result.get("generations")
    if not isinstance(raw_gens, list) or len(raw_gens) != 12:
        raise ValueError(f"seed {seed} did not emit twelve explicit generation records")
    generations = []
    seen = set()
    for item in raw_gens:
        if not isinstance(item, dict):
            raise ValueError(f"seed {seed} emitted a malformed generation record")
        number = item.get("generation")
        if isinstance(number, bool) or not isinstance(number, int) or number not in range(12) or number in seen:
            raise ValueError(f"seed {seed} emitted duplicate or invalid generation indices")
        seen.add(number)
        status = safe_status(item.get("scientific_status"))
        evaluated = item.get("evaluated")
        if not isinstance(evaluated, bool):
            raise ValueError(f"seed {seed} generation {number} omitted its evaluated flag")
        if status == "PASSED" and evaluated is not True:
            raise ValueError(f"seed {seed} generation {number} claimed PASSED without evaluation")
        result_sha = item.get("result_sha256")
        if not isinstance(result_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", result_sha):
            result_sha = canonical_sha256({
                "seed": seed, "generation": number, "scientific_status": status,
                "evaluated": evaluated, "reason": item.get("reason"),
            })
        generations.append({
            "generation": number,
            "scientific_status": status,
            "evaluated": evaluated,
            "result_sha256": result_sha,
        })
    if seen != set(range(12)):
        raise ValueError(f"seed {seed} generation matrix is incomplete")
    generations.sort(key=lambda row: row["generation"])
    status = safe_status(seed_result.get("scientific_status"))
    if status == "PASSED" and any(row["scientific_status"] != "PASSED" for row in generations):
        raise ValueError(f"seed {seed} has conflicting passed status")
    return {"seed": seed, "scientific_status": status, "generations": generations}


def run_phase0_tests() -> bool:
    """Run the required synthetic test suite inside the Kaggle worker before compute."""
    working = Path("/kaggle/working")
    if not working.is_dir():
        working = ROOT / "kaggle-output"
    report_path = working / "test_report.json"
    working.mkdir(parents=True, exist_ok=True)

    required = (
        ("receipt_emitter", ROOT / "research" / "tests" / "test_emit_validated_receipt.py"),
        ("generation_driver", ROOT / "research" / "tests" / "test_gen3_foundry_generations.py"),
        ("archive_manifest", ROOT / "scripts" / "tests" / "test_archive_foundry_outputs.py"),
    )
    suite = unittest.TestSuite()
    loader_errors = []
    loaded_suites = []
    file_rows = []
    for label, test_path in required:
        present = test_path.is_file()
        file_rows.append({"suite": label, "path": test_path.relative_to(ROOT).as_posix(), "present": present})
        if not present:
            loader_errors.append({
                "suite": label,
                "error": "required Phase 0 test file is missing from the staged Kaggle package",
            })
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"_acsie_phase0_{label}", test_path)
            if spec is None or spec.loader is None:
                raise ImportError("could not create an import loader for test module")
            module = importlib.util.module_from_spec(spec)
            # ProcessPoolExecutor tests require importable, pickleable module names.
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            tests = unittest.defaultTestLoader.loadTestsFromModule(module)
            if tests.countTestCases() == 0:
                raise RuntimeError("test module loaded but contains zero unittest cases")
            suite.addTests(tests)
            loaded_suites.append(label)
        except Exception as exc:
            loader_errors.append({
                "suite": label,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            })

    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)

    def serialize_errors(rows):
        return [
            {
                "test": test.id() if hasattr(test, "id") else str(test),
                "traceback": detail,
            }
            for test, detail in rows
        ]

    passed = result.wasSuccessful() and not loader_errors and result.testsRun > 0
    report = {
        "schema": "ACSIE.kaggle-phase0-test-report.v1",
        "created_at_utc": utc_now(),
        "status": "PASSED" if passed else "FAILED",
        "worker": "kaggle",
        "required_suite_count": len(required),
        "loaded_suite_count": len(loaded_suites),
        "required_test_files": file_rows,
        "tests_run": result.testsRun,
        "tests_passed": result.testsRun - len(result.failures) - len(result.errors),
        "failure_count": len(result.failures),
        "error_count": len(result.errors),
        "loader_errors": loader_errors,
        "failures": serialize_errors(result.failures),
        "errors": serialize_errors(result.errors),
        "test_log": stream.getvalue(),
        "research_started": False,
    }
    write_json(report_path, report)
    print(json.dumps({
        "phase": "phase0_unit_tests",
        "status": report["status"],
        "tests_run": report["tests_run"],
        "failure_count": report["failure_count"],
        "error_count": report["error_count"],
        "loader_error_count": len(loader_errors),
        "test_report": report_path.as_posix(),
    }, indent=2, sort_keys=True))
    return passed


def _gpu_device_telemetry() -> dict[str, Any]:
    """Report visible GPU devices without implying GPU compute was used."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        devices = [
            line.strip() for line in (result.stdout or "").splitlines()
            if line.strip()
        ] if result.returncode == 0 else []
        return {
            "nvidia_smi_available": result.returncode == 0,
            "query_returncode": result.returncode,
            "devices": devices,
            "gpu_computation_used": False,
        }
    except Exception as exc:
        return {
            "nvidia_smi_available": False,
            "query_returncode": None,
            "devices": [],
            "error_type": type(exc).__name__,
            "gpu_computation_used": False,
        }


def _profile_one_generation(package_root: str, working: Path, seed: int = 0) -> dict[str, Any]:
    """Measure one diagnostic generation without weakening the frozen 12-gen run."""
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    foundry = importlib.import_module("research.gen3_learning_rule_foundry_v1")
    original_limit = getattr(foundry, "GENERATION_COUNT", None)
    if original_limit != 12:
        raise RuntimeError("cannot profile: production generation limit is not 12")
    started = time.perf_counter()
    profile: dict[str, Any]
    try:
        with tempfile.TemporaryDirectory(prefix="acsie-gen3-onegen-") as tmp:
            # This is a diagnostic-only in-memory generation limit. Restore 12
            # in finally, keep output temporary, and exclude the result from 5x12.
            foundry.GENERATION_COUNT = 1
            events: list[dict[str, Any]] = []
            result = foundry.run_generations(
                seed=seed, generations=1, checkpoint_dir=Path(tmp),
                progress_callback=events.append,
            )
            rows = result.get("generations", [])
            if len(rows) != 1:
                raise RuntimeError("one-generation profile did not emit exactly one row")
            row = rows[0]
            duration = row.get("gen_duration_sec")
            profile = {
                "schema": "ACSIE.gen3-foundry-one-generation-profile.v1",
                "diagnostic_only": True,
                "qualification_slot": False,
                "seed": seed,
                "generation": row.get("generation"),
                "scientific_status": row.get("scientific_status"),
                "evaluated": row.get("evaluated") is True,
                "candidate_count": row.get("candidate_count", 0),
                "sec_per_gen": duration,
                "wall_clock_sec_including_setup_and_final_metrics": round(time.perf_counter() - started, 6),
                "replay_exact": row.get("replay_exact") is True,
                "note": "diagnostic-only seed 0; not part of the frozen qualification matrix",
                "created_at_utc": utc_now(),
            }
    finally:
        foundry.GENERATION_COUNT = original_limit
    write_json(working / "one_generation_profile.json", profile)
    print(json.dumps({"event": "one_generation_profile", **profile}, sort_keys=True, separators=(",", ":")), flush=True)
    return profile


def _run_seed_worker(seed: int, package_root: str, checkpoints_root: str, progress_queue) -> dict[str, Any]:
    """Run one independent seed in its own process and checkpoint directory."""
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    checkpoint_dir = Path(checkpoints_root) / f"seed-{seed}"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    try:
        foundry = importlib.import_module("research.gen3_learning_rule_foundry_v1")
        driver = getattr(foundry, "run_generations", None)
        if not callable(driver):
            raise RuntimeError("Foundry source lacks run_generations(seed, generations=12)")
        result = driver(
            seed,
            generations=12,
            checkpoint_dir=checkpoint_dir,
            progress_callback=progress_queue.put,
        )
        if not isinstance(result, dict):
            raise TypeError("run_generations did not return an object")
        if len(result.get("generations", [])) != 12:
            raise ValueError("run_generations returned an incomplete generation matrix")
        result.setdefault("seed", seed)
        result["scientific_status"] = safe_status(result.get("scientific_status"))
        result["passed"] = result.get("passed") is True and result["scientific_status"] == "PASSED"
        if result["scientific_status"] == "PASSED" and not result["passed"]:
            result["scientific_status"] = "FAILED"
        return {"seed": seed, "result": result}
    except Exception as exc:
        return {
            "seed": seed,
            "run_error": {
                "exception_type": type(exc).__name__,
                "exception": str(exc),
                "traceback": traceback.format_exc(),
            },
        }


def _run_parallel_seeds(
    seeds: tuple[int, ...],
    package_root: str,
    checkpoints_root: Path,
    working: Path,
    run_id: str,
    source_commit: str,
    embedded_archive_sha256: str,
    hardware_info: dict[str, Any],
) -> dict[int, dict[str, Any]]:
    """Run independent frozen seeds concurrently and persist parent-owned heartbeats."""
    worker_count = min(len(seeds), os.cpu_count() or 4)
    heartbeat_path = working / "progress_heartbeat.json"
    heartbeat = {
        "schema": "ACSIE.gen3-foundry-progress-heartbeat.v1",
        "run_id": run_id,
        "source_commit": source_commit,
        "kernel_slug": DEPLOYMENT_KERNEL_ID,
        "embedded_source_archive_sha256": embedded_archive_sha256,
        "status": "RUNNING",
        "worker_count": worker_count,
        "reported_cpu_count": os.cpu_count() or 4,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "gpu_requested": DEPLOYMENT_GPU_REQUESTED,
        "gpu_acceleration_enabled": False,
        "gpu_device_telemetry": hardware_info,
        "expected_generation_events": len(seeds) * 12,
        "completed_generation_events": 0,
        "events": [],
        "updated_at_utc": utc_now(),
    }
    write_json(heartbeat_path, heartbeat)
    print(json.dumps({
        "event": "parallel_dispatch_started",
        "run_id": run_id,
        "seed_count": len(seeds),
        "worker_count": worker_count,
        "reported_cpu_count": os.cpu_count() or 4,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "gpu_requested": DEPLOYMENT_GPU_REQUESTED,
        "gpu_acceleration_enabled": False,
        "gpu_device_telemetry": hardware_info,
    }, sort_keys=True, separators=(",", ":")), flush=True)
    outcomes: dict[int, dict[str, Any]] = {}

    def consume_events(event_queue) -> None:
        changed = False
        while True:
            try:
                event = event_queue.get_nowait()
            except queue.Empty:
                break
            if not isinstance(event, dict):
                continue
            event = dict(event)
            event["observed_at_utc"] = utc_now()
            heartbeat["events"].append(event)
            heartbeat["completed_generation_events"] = len(heartbeat["events"])
            heartbeat["updated_at_utc"] = utc_now()
            print(json.dumps(event, sort_keys=True, separators=(",", ":")), flush=True)
            changed = True
        if changed:
            write_json(heartbeat_path, heartbeat)

    with multiprocessing.Manager() as manager:
        event_queue = manager.Queue()
        context = multiprocessing.get_context("fork")
        with ProcessPoolExecutor(max_workers=worker_count, mp_context=context) as executor:
            future_to_seed = {
                executor.submit(
                    _run_seed_worker, seed, package_root, str(checkpoints_root), event_queue
                ): seed
                for seed in seeds
            }
            pending = set(future_to_seed)
            while pending:
                consume_events(event_queue)
                completed = {future for future in pending if future.done()}
                for future in completed:
                    seed = future_to_seed[future]
                    try:
                        payload = future.result()
                        if not isinstance(payload, dict):
                            raise TypeError("seed worker returned a malformed result")
                        outcomes[seed] = payload
                    except Exception as exc:
                        outcomes[seed] = {
                            "seed": seed,
                            "run_error": {
                                "exception_type": type(exc).__name__,
                                "exception": str(exc),
                                "traceback": traceback.format_exc(),
                            },
                        }
                    pending.remove(future)
                if pending:
                    time.sleep(0.25)
            consume_events(event_queue)

    heartbeat["status"] = (
        "COMPLETE"
        if len(outcomes) == len(seeds)
        and heartbeat["completed_generation_events"] == len(seeds) * 12
        else "INCOMPLETE"
    )
    heartbeat["worker_results"] = len(outcomes)
    heartbeat["updated_at_utc"] = utc_now()
    write_json(heartbeat_path, heartbeat)
    return outcomes


def main() -> int:
    kernel_started = time.perf_counter()
    sys.path.insert(0, str(ROOT))
    if not run_phase0_tests():
        print('PHASE0_FAILED: refusing to start the 5x12 research run.', file=sys.stderr)
        return 2
    manifest = load_source_manifest()
    source_sha = manifest["source_commit"]
    dispatch_nonce = manifest.get("dispatch_nonce")
    if not isinstance(dispatch_nonce, str) or not dispatch_nonce:
        raise RuntimeError("source manifest omitted the orchestration dispatch nonce")
    embedded_archive_sha256 = globals().get("EMBEDDED_SOURCE_SHA256")
    if not isinstance(DEPLOYMENT_KERNEL_ID, str) or not re.fullmatch(r"[a-z0-9._-]+/[a-z0-9._-]+", DEPLOYMENT_KERNEL_ID):
        raise RuntimeError("embedded kernel builder did not bind the deployed kernel ID")
    if not isinstance(embedded_archive_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", embedded_archive_sha256):
        raise RuntimeError("embedded kernel source archive SHA-256 was not bound")
    if not isinstance(DEPLOYMENT_GPU_REQUESTED, bool):
        raise RuntimeError("embedded GPU request marker is invalid")
    if not isinstance(DEPLOYMENT_PROFILE_ONLY, bool):
        raise RuntimeError("embedded profile-only marker is invalid")
    hardware_info = _gpu_device_telemetry()
    run_id = f"gen3-foundry-{source_sha[:10]}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    working = Path("/kaggle/working")
    if not working.is_dir():
        working = ROOT / "kaggle-output"
    checkpoints_root = working / "checkpoints"
    summaries_root = working / "seed-results"
    checkpoints_root.mkdir(parents=True, exist_ok=True)
    summaries_root.mkdir(parents=True, exist_ok=True)

    foundry = None
    import_error = None
    try:
        foundry = importlib.import_module("research.gen3_learning_rule_foundry_v1")
        driver = getattr(foundry, "run_generations")
        if not callable(driver):
            raise RuntimeError("Foundry source lacks run_generations(seed, generations=12)")
    except Exception as exc:
        import_error = {
            "exception_type": type(exc).__name__,
            "exception": str(exc),
            "traceback": traceback.format_exc(),
        }
        driver = None

    research_started = time.perf_counter()
    parallel_results = {}
    if driver is None and DEPLOYMENT_PROFILE_ONLY:
        print(json.dumps({
            "event": "one_generation_profile_failed",
            "reason": "production generation driver could not be imported",
            "source_commit": source_sha,
            "dispatch_nonce": dispatch_nonce,
        }, sort_keys=True, separators=(",", ":")), flush=True)
        return 2
    if driver is not None and DEPLOYMENT_PROFILE_ONLY:
        profile = _profile_one_generation(str(ROOT), working, seed=0)
        profile.update({
            "source_commit": source_sha,
            "dispatch_nonce": dispatch_nonce,
            "kernel_slug": DEPLOYMENT_KERNEL_ID,
            "embedded_source_archive_sha256": embedded_archive_sha256,
        })
        write_json(working / "one_generation_profile.json", profile)
        print(json.dumps({
            "event": "one_generation_profile_sealed",
            "sec_per_gen": profile.get("sec_per_gen"),
            "evaluated": profile.get("evaluated"),
            "scientific_status": profile.get("scientific_status"),
            "dispatch_nonce": dispatch_nonce,
        }, sort_keys=True, separators=(",", ":")), flush=True)
        write_json(working / "profile_only_summary.json", {
            "schema": "ACSIE.gen3-foundry-profile-only-summary.v1",
            "status": "COMPLETE",
            "source_commit": source_sha,
            "dispatch_nonce": dispatch_nonce,
            "kernel_slug": DEPLOYMENT_KERNEL_ID,
            "embedded_source_archive_sha256": embedded_archive_sha256,
        })
        print(json.dumps({
            "event": "profile_only_complete",
            "profile_file": (working / "one_generation_profile.json").as_posix(),
        }, sort_keys=True, separators=(",", ":")), flush=True)
        return 0
    if driver is not None:
        parallel_results = _run_parallel_seeds(
            SEEDS, str(ROOT), checkpoints_root, working, run_id, source_sha,
            embedded_archive_sha256, hardware_info,
        )

    results = []
    for seed in SEEDS:
        checkpoint_dir = checkpoints_root / f"seed-{seed}"
        if driver is None:
            result = fallback_seed(seed, import_error or {"reason": "foundry driver unavailable"}, checkpoint_dir)
        else:
            payload = parallel_results.get(seed, {})
            if payload.get("run_error") or not isinstance(payload.get("result"), dict):
                result = fallback_seed(
                    seed,
                    payload.get("run_error") or {"reason": "parallel_seed_worker_returned_no_result"},
                    checkpoint_dir,
                )
            else:
                result = payload["result"]
        results.append(result)
        write_json(summaries_root / f"result-{seed}.json", result)

        # If a driver returned records but failed to write a bundle, preserve a clearly
        # marked failure record instead of fabricating a model-state checkpoint.
        existing_numbers = set()
        for path in checkpoint_dir.glob("generation-*.json"):
            try:
                existing_numbers.add(int(path.stem.split("-")[-1]))
            except ValueError:
                continue
        for generation in range(12):
            if generation in existing_numbers:
                continue
            row = result["generations"][generation]
            record = {
                "generation": generation,
                "scientific_status": "CRASHED",
                "evaluated": False,
                "reason": "generation_checkpoint_missing",
                "candidate_count": 0,
                "selected_program_sha256": None,
                "state_in_sha256": None,
                "state_out_sha256": None,
                "fitness": None,
                "replay_exact": False,
                "persistent_state_roundtrip": False,
                "persistent_state_delta": False,
                "candidate_crash_count": 0,
                "gen_duration_sec": 0.0,
            }
            record["result_sha256"] = canonical_sha256({
                "seed": seed, "generation": generation,
                "scientific_status": "CRASHED", "evaluated": False,
                "reason": "generation_checkpoint_missing",
            })
            row.update({"scientific_status": "CRASHED", "evaluated": False, "result_sha256": record["result_sha256"], "gen_duration_sec": 0.0})
            write_json(checkpoint_dir / f"generation-{generation:02d}.json", {
                "schema": "ACSIE.gen3-foundry-generation-checkpoint.v1",
                "seed": seed, "generation": generation, "checkpoint_available": False,
                "generation_record": record,
                "error": {"reason": "generation_checkpoint_missing"},
            })
        write_json(summaries_root / f"result-{seed}.json", result)

    # The manifest lists every durable output other than itself. Checkpoint bytes and
    # per-seed summaries stay in Kaggle kernel output, not in Git or on the phone.
    manifest_files = []
    for path in sorted(checkpoints_root.rglob("*.json")):
        relative = path.relative_to(working).as_posix()
        bundle = json.loads(path.read_text(encoding="utf-8"))
        record = bundle.get("generation_record", {})
        manifest_files.append({
            "path": relative,
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
            "kind": "generation_bundle",
            "seed": int(bundle["seed"]),
            "generation": int(bundle["generation"]),
            "scientific_status": safe_status(record.get("scientific_status")),
            "evaluated": bool(record.get("evaluated")) if isinstance(record.get("evaluated"), bool) else False,
            "result_sha256": record.get("result_sha256") if isinstance(record.get("result_sha256"), str) else canonical_sha256(record),
            "checkpoint_available": bool("native_state" in bundle),
        })
    for path in sorted(summaries_root.glob("result-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest_files.append({
            "path": path.relative_to(working).as_posix(),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
            "kind": "seed_summary",
            "seed": int(payload["seed"]),
        })
    summary = {
        "run_id": run_id,
        "source_commit": source_sha,
        "scientific_status": "PASSED" if all(r.get("scientific_status") == "PASSED" for r in results) else (
            "CRASHED" if any(r.get("scientific_status") == "CRASHED" for r in results) else "FAILED"
        ),
        "qualification_status": "PASSED" if all(r.get("passed") is True for r in results) else "FAILED",
        "seed_count": len(results),
        "expected_generation_records": 60,
        "evaluated_generation_records": sum(
            1 for r in results for g in r["generations"] if g.get("evaluated") is True
        ),
        "passed_generation_records": sum(
            1 for r in results for g in r["generations"] if g.get("scientific_status") == "PASSED"
        ),
        "failed_generation_records": sum(
            1 for r in results for g in r["generations"] if g.get("scientific_status") != "PASSED"
        ),
        "checkpoint_bundle_count": len(list(checkpoints_root.rglob("*.json"))),
        "kernel_wall_clock_sec": round(max(0.0, time.perf_counter() - kernel_started), 3),
        "research_wall_clock_sec": round(max(0.0, time.perf_counter() - research_started), 3),
        "reported_cpu_count": os.cpu_count() or 4,
        "parallel_worker_count": min(len(SEEDS), os.cpu_count() or 4) if driver is not None else 0,
        "gpu_requested": DEPLOYMENT_GPU_REQUESTED,
        "gpu_acceleration_enabled": False,
        "gpu_device_telemetry": hardware_info,
        "profile_only": DEPLOYMENT_PROFILE_ONLY,
        "platform": platform.platform(),
        "machine": platform.machine(),
    }
    write_json(working / "foundry-summary.json", summary)
    manifest_files.append({
        "path": "foundry-summary.json",
        "sha256": sha256_file(working / "foundry-summary.json"),
        "size_bytes": (working / "foundry-summary.json").stat().st_size,
        "kind": "foundry_summary",
    })
    artifact_manifest = {
        "schema": "ACSIE.kaggle-foundry-artifact-manifest.v1",
        "run_id": run_id,
        "source_commit": source_sha,
        "dispatch_nonce": dispatch_nonce,
        "expected_seed_ids": list(SEEDS),
        "expected_generations_per_seed": 12,
        "files": manifest_files,
        "file_count": len(manifest_files),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in manifest_files),
    }
    write_json(working / "artifact_manifest.json", artifact_manifest)

    compact_rows = [matrix_row(result, int(result["seed"])) for result in results]
    failures = []
    for row in compact_rows:
        seed = row["seed"]
        failed_generations = []
        for generation in row["generations"]:
            if generation["scientific_status"] == "PASSED":
                continue
            failed_generations.append(generation)
            failures.append({
                "status": generation["scientific_status"] if generation["scientific_status"] in STATUS - {"PASSED"} else "FAILED",
                "reason": f"seed {seed} generation {generation['generation']} status {generation['scientific_status']}",
                "seed": seed,
                "generation": generation["generation"],
            })
        if row["scientific_status"] != "PASSED" and not failed_generations:
            failures.append({
                "status": row["scientific_status"] if row["scientific_status"] in STATUS - {"PASSED"} else "FAILED",
                "reason": str(next((r.get("reason") for r in results if r["seed"] == seed), "seed qualification failed")),
                "seed": seed,
            })

    seed_statuses = [row["scientific_status"] for row in compact_rows]
    if "CRASHED" in seed_statuses:
        overall = "CRASHED"
    elif "INVALID" in seed_statuses:
        overall = "INVALID"
    elif "BLOCKED" in seed_statuses:
        overall = "BLOCKED"
    elif "INCONCLUSIVE" in seed_statuses:
        overall = "INCONCLUSIVE"
    elif all(status == "PASSED" for status in seed_statuses):
        overall = "PASSED"
    else:
        overall = "FAILED"

    candidate_artifacts = []
    manifest_path = working / "artifact_manifest.json"
    candidate_artifacts.append({
        "storage": "kaggle-kernel-output",
        "path": "artifact_manifest.json",
        "sha256": sha256_file(manifest_path),
        "size_bytes": manifest_path.stat().st_size,
    })
    for item in manifest_files:
        if item.get("kind") == "generation_bundle":
            candidate_artifacts.append({
                "storage": "kaggle-kernel-output",
                "path": item["path"],
                "sha256": item["sha256"],
                "size_bytes": item["size_bytes"],
            })

    integrity = {}
    for flag in INTEGRITY_FLAGS:
        values = [
            result.get("integrity", {}).get(flag)
            for result in results
            if isinstance(result.get("integrity"), dict)
            and isinstance(result["integrity"].get(flag), bool)
        ]
        if len(values) == len(results):
            integrity[flag] = any(values)

    candidate = {
        "candidate_schema": "ACSIE.kaggle-foundry-candidate.v1",
        "run_id": run_id,
        "created_at_utc": utc_now(),
        "experiment_id": "gen3-learning-rule-foundry-v1",
        "scientific_status": overall,
        "qualification_status": "PASSED" if overall == "PASSED" else "FAILED",
        "source": {"repository": "Infrasigma/ACSIE", "commit_sha": source_sha},
        "execution": {
            "platform": "kaggle",
            "kernel_slug": DEPLOYMENT_KERNEL_ID,
            "kernel_visibility": "private",
            "internet_enabled": False,
            "entrypoint": "python run_kaggle_foundry.py",
            "dataset_inputs": [],
            "embedded_source_archive_sha256": embedded_archive_sha256,
            "gpu_requested": DEPLOYMENT_GPU_REQUESTED,
            "gpu_computation_used": False,
            "gpu_device_telemetry": hardware_info,
            "profile_only": DEPLOYMENT_PROFILE_ONLY,
        },
        "gate": {
            "gate_id": "frozen_5x12",
            "qualification": True,
            "expected_seed_count": 5,
            "expected_generations_per_seed": 12,
        },
        "expected_seed_ids": list(SEEDS),
        "seed_results": compact_rows,
        "artifacts": candidate_artifacts,
        "integrity": integrity,
        "failures": failures,
        "provenance": {
            "workflow_source": "Infrasigma/Tester-",
            "orchestration_commit": manifest.get("orchestration_commit"),
            "requested_acsie_ref": manifest.get("requested_ref"),
            "actual_acsie_commit": source_sha,
            "dispatch_nonce": dispatch_nonce,
        },
    }
    write_json(working / "receipt-candidate.json", candidate)
    print(json.dumps({
        "run_id": run_id,
        "source_commit": source_sha,
        "scientific_status": overall,
        "qualification_status": candidate["qualification_status"],
        "seed_count": len(compact_rows),
        "generation_records": sum(len(row["generations"]) for row in compact_rows),
        "evaluated_generation_records": summary["evaluated_generation_records"],
        "passed_generation_records": summary["passed_generation_records"],
        "checkpoint_bundle_count": len(candidate_artifacts) - 1,
        "artifact_manifest_sha256": sha256_file(manifest_path),
        "kernel_wall_clock_sec": round(max(0.0, time.perf_counter() - kernel_started), 3),
        "research_wall_clock_sec": round(max(0.0, time.perf_counter() - research_started), 3),
        "reported_cpu_count": os.cpu_count() or 4,
        "parallel_worker_count": min(len(SEEDS), os.cpu_count() or 4) if driver is not None else 0,
        "gpu_requested": DEPLOYMENT_GPU_REQUESTED,
        "gpu_acceleration_enabled": False,
        "gpu_device_telemetry": hardware_info,
        "profile_only": DEPLOYMENT_PROFILE_ONLY,
        "platform": platform.platform(),
        "machine": platform.machine(),
    }, indent=2, sort_keys=True))
    # Infrastructure success means complete diagnostic records were written. Scientific
    # failure is represented in the records; it never gets upgraded to PASSED here.
    return 0 if len(compact_rows) == 5 and all(len(row["generations"]) == 12 for row in compact_rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())

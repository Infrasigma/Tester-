from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = RUNTIME_ROOT / "source"
STAGING_ROOT = RUNTIME_ROOT / "v22_3_staging"
FROZEN_SEEDS = [2026100301, 2026100302, 2026100303, 2026100304, 2026100305]
GENERATIONS_PER_SEED = 12
SEED_TIMEOUT_SECONDS = 7200
TARGET_ACCESS_DURING_DISCOVERY = False
TEST_NAMES = (
    "test_h7_v22_2_overlay_regressions.py",
    "test_h7_closure_telemetry_audit.py",
    "test_h7_v22_3_repairs.py",
    "test_h7_generation_pair_summary.py",
)
KERNEL_POLICY = {
    "id": "memorican/acsie-h7-v22-3-frozen-qualification",
    "canonical_notebook_url_slug": "memorican/acsie-h7-v22-3-frozen-qualification",
    "legacy_kernel_metadata_id_alias": "memorican/acsie-h7-v22-3",
    "title": "ACSIE H7 V22.3 Frozen Qualification",
    "code_file": "run_acsie_h7_v22_3.py",
    "language": "python",
    "kernel_type": "script",
    "is_private": True,
    "enable_gpu": False,
    "enable_internet": False,
    "dataset_sources": [],
    "competition_sources": [],
    "kernel_sources": [],
}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def make_archive(files: dict[str, bytes]) -> bytes:
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as archive:
            for name, data in sorted(files.items()):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o644
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = 0
                archive.addfile(info, io.BytesIO(data))
    return raw.getvalue()


def build() -> dict:
    if not SOURCE_ROOT.is_dir():
        raise SystemExit(f"recovered source root missing: {SOURCE_ROOT}")
    if not (SOURCE_ROOT / "lab/h7_exact_audit.py").is_file():
        raise SystemExit("exact audit memoizer missing from recovered source package")
    if not (SOURCE_ROOT / "research/audit_h7_closure_telemetry.py").is_file():
        raise SystemExit("closure telemetry auditor missing from isolated source package")

    archive_files: dict[str, bytes] = {}
    source_prefix = "research/recovered/h7_v22_2_runtime/source"
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        name = f"{source_prefix}/{path.relative_to(SOURCE_ROOT).as_posix()}"
        archive_files[name] = path.read_bytes()

    for name in TEST_NAMES:
        path = REPO_ROOT / "research/tests" / name
        if not path.is_file():
            raise SystemExit(f"required regression suite missing: {path}")
        archive_files[f"research/tests/{name}"] = path.read_bytes()

    file_entries = [
        {"path": name, "bytes": len(data), "sha256": sha256(data)}
        for name, data in sorted(archive_files.items())
    ]
    archive_bytes = make_archive(archive_files)
    archive_sha = sha256(archive_bytes)
    metadata_bytes = (json.dumps(KERNEL_POLICY, indent=2, sort_keys=True) + "\n").encode("utf-8")
    metadata_sha = sha256(metadata_bytes)

    manifest = {
        "schema": "ACSIE.h7.v22_3.embedded_source_manifest.v1",
        "archive_sha256": archive_sha,
        "archive_bytes": len(archive_bytes),
        "files": file_entries,
        "source_root": source_prefix,
        "frozen_contract": {
            "seeds": FROZEN_SEEDS,
            "generations_per_seed": GENERATIONS_PER_SEED,
            "total_seed_generation_slots": len(FROZEN_SEEDS) * GENERATIONS_PER_SEED,
            "required_unordered_pairs_per_generation": "g*(g+1)/2",
            "target_access_during_discovery": TARGET_ACCESS_DURING_DISCOVERY,
            "selection_uses_holdout_transfer_ood": False,
            "thresholds_or_denominators_changed": False,
            "promotion": "DO NOT PROMOTE",
        },
        "runtime_policy": {"per_seed_timeout_seconds": 7200, "one_child_process_per_seed": True, "on_timeout": "TIMEOUT_ACTIVE_SLOT_BLOCK_REST_OF_SEED_CONTINUE_NEXT_SEED", "continue_after_seed_crash": True, "manifest_has_all_seed_generation_slots": True},
        "kernel_policy": KERNEL_POLICY,
        "kernel_metadata_sha256": metadata_sha,
    }
    manifest_bytes = canonical_bytes(manifest)
    manifest_sha = sha256(manifest_bytes)

    template = r'''#!/usr/bin/env python3
from __future__ import annotations
import argparse
import base64
import compileall
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

EMBEDDED_SOURCE_B64 = __EMBEDDED_SOURCE_B64__
EMBEDDED_SOURCE_SHA256 = __ARCHIVE_SHA256__
SOURCE_MANIFEST = __SOURCE_MANIFEST__
SOURCE_MANIFEST_SHA256 = __SOURCE_MANIFEST_SHA256__
KERNEL_METADATA_SHA256 = __KERNEL_METADATA_SHA256__
KERNEL_POLICY = __KERNEL_POLICY__
FROZEN_SEEDS = [2026100301, 2026100302, 2026100303, 2026100304, 2026100305]
GENERATIONS_PER_SEED = 12
SEED_TIMEOUT_SECONDS = 7200
TARGET_ACCESS_DURING_DISCOVERY = False

_FINAL_RUN_CONTEXT = {
    "started_epoch_seconds": time.time(),
    "seed_results": [],
    "seed_summaries": {},
    "seed_generation_slots": [],
    "slot_status_counts": {},
    "run_status": None,
    "terminal_exception": None,
    "qualification_status": "NOT_QUALIFIED",
    "promotion": "DO NOT PROMOTE",
}


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def emit(event, **fields):
    print(json.dumps({"event": event, **fields}, sort_keys=True), flush=True)


def safe_relative(name):
    path = Path(name)
    return not path.is_absolute() and bool(name) and all(
        part not in ("", ".", "..") for part in path.parts
    )


def extract_verified(root):
    payload = base64.b64decode(EMBEDDED_SOURCE_B64, validate=True)
    observed = sha256(payload)
    if observed != EMBEDDED_SOURCE_SHA256:
        raise RuntimeError("embedded source archive SHA-256 mismatch")
    expected = {entry["path"]: entry for entry in SOURCE_MANIFEST["files"]}
    extracted = set()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            if not member.isfile() or not safe_relative(member.name):
                raise RuntimeError("archive contains a non-regular or unsafe member")
            if member.name in extracted or member.name not in expected:
                raise RuntimeError("archive contains a duplicate or unexpected member")
            handle = archive.extractfile(member)
            if handle is None:
                raise RuntimeError("archive member could not be read")
            content = handle.read()
            entry = expected[member.name]
            if len(content) != entry["bytes"] or sha256(content) != entry["sha256"]:
                raise RuntimeError("source file digest/size mismatch: " + member.name)
            target = root / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            extracted.add(member.name)
    if extracted != set(expected):
        raise RuntimeError("embedded archive omitted manifest-listed source files")
    source_root = root / SOURCE_MANIFEST["source_root"]
    if not (source_root / "lab/acsie_open_ended_self_extending_proving.py").is_file():
        raise RuntimeError("recovered H7 driver missing after extraction")
    if not (source_root / "lab/h7_exact_audit.py").is_file():
        raise RuntimeError("exact audit memoizer missing after extraction")
    return payload, source_root


def check_frozen_contract():
    contract = SOURCE_MANIFEST["frozen_contract"]
    checks = {
        "private_kernel": KERNEL_POLICY.get("is_private") is True,
        "internet_disabled": KERNEL_POLICY.get("enable_internet") is False,
        "gpu_disabled": KERNEL_POLICY.get("enable_gpu") is False,
        "no_dataset_sources": KERNEL_POLICY.get("dataset_sources") == [],
        "no_kernel_sources": KERNEL_POLICY.get("kernel_sources") == [],
        "frozen_seeds_exact": contract.get("seeds") == FROZEN_SEEDS,
        "generations_exact": contract.get("generations_per_seed") == GENERATIONS_PER_SEED,
        "slots_exact": contract.get("total_seed_generation_slots") == 60,
        "target_access_during_discovery_false": contract.get("target_access_during_discovery") is False
            and TARGET_ACCESS_DURING_DISCOVERY is False,
        "holdout_transfer_ood_not_used_for_selection": contract.get("selection_uses_holdout_transfer_ood") is False,
        "thresholds_denominators_unchanged": contract.get("thresholds_or_denominators_changed") is False,
        "full_pair_denominator_frozen": contract.get("required_unordered_pairs_per_generation") == "g*(g+1)/2",
        "promotion_locked": contract.get("promotion") == "DO NOT PROMOTE",
        "metadata_digest_bound": KERNEL_METADATA_SHA256 == SOURCE_MANIFEST.get("kernel_metadata_sha256"),
        "kernel_slug_bound": (
            KERNEL_POLICY.get("id") == "memorican/acsie-h7-v22-3-frozen-qualification"
            and KERNEL_POLICY.get("canonical_notebook_url_slug") == "memorican/acsie-h7-v22-3-frozen-qualification"
            and KERNEL_POLICY.get("legacy_kernel_metadata_id_alias") == "memorican/acsie-h7-v22-3"
        ),
        "frozen_seed_timeout_exact": SEED_TIMEOUT_SECONDS == 7200 and SOURCE_MANIFEST.get("runtime_policy", {}).get("per_seed_timeout_seconds") == 7200,
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    if failed:
        raise RuntimeError("frozen preflight failed: " + ",".join(failed))
    return checks


def run_phase0(root, source_root):
    compile_ok = compileall.compile_dir(str(source_root), quiet=1, force=True)
    test_root = root / "research/tests"
    compile_ok = compileall.compile_dir(str(test_root), quiet=1, force=True) and compile_ok
    env = os.environ.copy()
    extra_path = [str(source_root), str(root)]
    if env.get("PYTHONPATH"):
        extra_path.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(extra_path)
    command = [
        sys.executable, "-m", "unittest", "discover",
        "-s", str(test_root), "-p", "test_h7_*.py", "-v",
    ]
    completed = subprocess.run(command, cwd=str(root), env=env, check=False)
    report = {
        "schema": "ACSIE.h7.v22_3.phase0_report.v1",
        "compile_status": "PASSED" if compile_ok else "FAILED",
        "regression_exit_code": completed.returncode,
        "phase0_status": "PASSED" if compile_ok and completed.returncode == 0 else "FAILED",
        "research_started": False,
        "qualification_slots_evaluated": 0,
        "promotion": "DO NOT PROMOTE",
        "archive_sha256": EMBEDDED_SOURCE_SHA256,
        "manifest_sha256": SOURCE_MANIFEST_SHA256,
    }
    emit("V22_3_PHASE0_REPORT", **report)
    return 0 if report["phase0_status"] == "PASSED" else 2


def _read_jsonl(path):
    events = []
    if not path.is_file():
        return events
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                value = json.loads(line)
            except Exception:
                continue
            if isinstance(value, dict):
                events.append(value)
    return events


def _read_seed_log(path):
    events = []
    summary = None
    if not path.is_file():
        return events, summary
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                value = json.loads(line)
            except Exception:
                continue
            if not isinstance(value, dict):
                continue
            if value.get("event"):
                events.append(value)
            if "finite_open_ended_growth_gate" in value and "generations_detail" in value:
                summary = value
    return events, summary


def _generation_slot_gates(row, generation):
    # The existing frozen gates are not altered here. This surfaces their
    # per-generation components; the original seed-level gate remains decisive.
    checks = {
        "primary_accepted": bool(row.get("accepted")),
        "closure_competence_perfect": (
            int(row.get("closure_pair_count", -1)) == 0
            or float(row.get("closure_success_rate", 0.0)) == 1.0
        ),
        "closure_reuse_perfect": (
            int(row.get("closure_pair_count", -1)) == 0
            or float(row.get("closure_reuse_rate", 0.0)) == 1.0
        ),
        "closure_trap_free": int(row.get("closure_trap_count", -1)) == 0,
        "probe_competence_perfect": float(row.get("probe_success_rate", 0.0)) == 1.0,
        "probe_reuse_perfect": float(row.get("probe_reuse_rate", 0.0)) == 1.0,
        "probe_trap_free": int(row.get("probe_trap_count", -1)) == 0,
    }
    if generation > 0:
        checks["parent_lineage_present"] = bool(row.get("parent_used"))
        checks["strict_growth_this_generation"] = int(row.get("growth_delta", 0)) > 0
    if generation in (9, 10, 11):
        checks["primary_pair_recency_gate_passed"] = (
            row.get("primary_pair_recency_gate_passed") is True
        )
    return checks


def run_frozen_qualification(root, source_root):
    overall_started = time.time()
    output_dir = Path("/kaggle/working") if Path("/kaggle/working").is_dir() else root
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_jsonl = output_dir / "acsie-h7-v22-3-audit-events.jsonl"
    pair_dir = output_dir / "acsie-h7-v22-3-pair-audits"
    pair_dir.mkdir(parents=True, exist_ok=True)
    audit_jsonl.write_text("", encoding="utf-8")
    env_base = os.environ.copy()
    env_base["ACSIE_H7_AUDIT_JSONL"] = str(audit_jsonl)
    env_base["ACSIE_H7_PAIR_AUDIT_DIR"] = str(pair_dir)
    env_base["PYTHONPATH"] = os.pathsep.join(
        [str(source_root)] + ([env_base["PYTHONPATH"]] if env_base.get("PYTHONPATH") else [])
    )

    seed_results = []
    seed_summaries = {}
    seed_events = {}
    _FINAL_RUN_CONTEXT.update({
        "output_dir": str(output_dir),
        "started_epoch_seconds": overall_started,
        "seed_results": seed_results,
        "seed_summaries": seed_summaries,
        "seed_events": seed_events,
        "seed_generation_slots": [],
        "slot_status_counts": {},
        "run_status": None,
    })
    for seed in FROZEN_SEEDS:
        seed_log = output_dir / f"acsie-h7-v22-3-seed-{seed}.log"
        command = [
            sys.executable,
            str(source_root / "lab/acsie_open_ended_self_extending_proving.py"),
            "--seeds", str(seed),
            "--generations", str(GENERATIONS_PER_SEED),
        ]
        started = time.time()
        return_code = None
        execution_status = "CRASHED"
        exception_summary = None
        emit("V22_3_SEED_CHILD_START", seed=seed, timeout_seconds=SEED_TIMEOUT_SECONDS,
             command=command, log_path=str(seed_log), promotion="DO NOT PROMOTE")
        try:
            with seed_log.open("w", encoding="utf-8", buffering=1) as log:
                completed = subprocess.run(
                    command,
                    cwd=str(source_root),
                    env=env_base,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                    timeout=SEED_TIMEOUT_SECONDS,
                )
            return_code = int(completed.returncode)
            execution_status = "COMPLETED" if return_code == 0 else "CRASHED"
        except subprocess.TimeoutExpired:
            execution_status = "TIMEOUT"
            exception_summary = f"seed child exceeded frozen {SEED_TIMEOUT_SECONDS}-second timeout"
            with seed_log.open("a", encoding="utf-8", buffering=1) as log:
                log.write(json.dumps({
                    "event": "V22_3_SEED_CHILD_TIMEOUT",
                    "seed": seed,
                    "timeout_seconds": SEED_TIMEOUT_SECONDS,
                    "timestamp_epoch_seconds": time.time(),
                    "promotion": "DO NOT PROMOTE",
                }, sort_keys=True) + "\n")
        except BaseException as exc:
            execution_status = "CRASHED"
            exception_summary = type(exc).__name__ + ": " + str(exc)
            with seed_log.open("a", encoding="utf-8", buffering=1) as log:
                log.write(json.dumps({
                    "event": "V22_3_SEED_CHILD_LAUNCH_CRASH",
                    "seed": seed,
                    "exception_type": type(exc).__name__,
                    "message": str(exc),
                    "promotion": "DO NOT PROMOTE",
                }, sort_keys=True) + "\n")

        elapsed = round(time.time() - started, 3)
        events, summary = _read_seed_log(seed_log)
        seed_events[seed] = events
        if summary is not None:
            seed_summaries[seed] = summary
        seed_passed = bool(
            execution_status == "COMPLETED"
            and summary is not None
            and summary.get("finite_open_ended_growth_gate") is True
            and int(summary.get("completed_generations", 0)) == GENERATIONS_PER_SEED
            and summary.get("external_model") is False
            and summary.get("target_identity_available_to_runtime") is False
            and summary.get("task_family_route") is False
        )
        seed_results.append({
            "seed": seed,
            "execution_status": execution_status,
            "return_code": return_code,
            "seed_gate_passed": seed_passed,
            "elapsed_seconds": elapsed,
            "timeout_seconds": SEED_TIMEOUT_SECONDS,
            "log_path": str(seed_log),
            "summary_available": summary is not None,
            "completed_generations": int(summary.get("completed_generations", 0)) if summary else
                sum(1 for event in events if event.get("event") == "GENERATION_PROGRESS"),
            "exception": exception_summary,
            "promotion": "DO NOT PROMOTE",
        })
        emit("V22_3_SEED_CHILD_END", **seed_results[-1])

    # Merge the durable JSONL and child stdout, deduplicating events emitted
    # to both destinations. Without this identity key, an interrupted slot
    # would appear to have twice its observed H7_PAIR_OUTCOME count.
    all_events = _read_jsonl(audit_jsonl)
    for events in seed_events.values():
        all_events.extend(events)
    deduplicated_events = {}
    for event in all_events:
        expected = event.get("expected_parent_ids", event.get("macro_pair", ()))
        event_identity = (
            event.get("event"),
            event.get("seed"),
            event.get("generation"),
            event.get("phase"),
            event.get("pair_index"),
            event.get("probe_index"),
            tuple(sorted(str(value) for value in expected)) if isinstance(expected, (list, tuple, set)) else str(expected),
            event.get("generation_completed"),
        )
        deduplicated_events.setdefault(event_identity, event)
    all_events = list(deduplicated_events.values())

    begins, ends, progresses = {}, {}, {}
    pair_rows, probe_rows = {}, {}
    for event in all_events:
        try:
            seed = int(event.get("seed"))
            generation = int(event.get("generation"))
        except (TypeError, ValueError):
            continue
        key = (seed, generation)
        name = event.get("event")
        if name == "GENERATION_BEGIN":
            begins[key] = event
        elif name == "AUDIT_END" and event.get("phase") == "CLOSURE_PAIR_EVALUATION":
            ends[key] = event
        elif name == "GENERATION_PROGRESS":
            progresses[key] = event
        elif name == "H7_PAIR_OUTCOME":
            pair_rows.setdefault(key, []).append(event)
        elif name == "H7_PROBE_DIAGNOSTIC":
            probe_rows.setdefault(key, []).append(event)

    slot_rows = []
    for seed_result in seed_results:
        seed = seed_result["seed"]
        summary = seed_summaries.get(seed)
        detail_by_generation = {
            int(row.get("generation", -1)): row
            for row in (summary.get("generations_detail", []) if summary else [])
        }
        begun_generations = sorted(g for (s, g) in begins if s == seed)
        completed_generations = set(detail_by_generation) | {
            g for (s, g) in progresses if s == seed
        }
        incomplete_started = [g for g in begun_generations if g not in completed_generations]
        missing_generations = set(range(GENERATIONS_PER_SEED)) - completed_generations
        active_timeout_generation = (
            min(incomplete_started) if incomplete_started
            else (min(missing_generations) if seed_result["execution_status"] == "TIMEOUT" and missing_generations else None)
        )
        active_crash_generation = (
            min(incomplete_started) if incomplete_started
            else (min(missing_generations) if seed_result["execution_status"] == "CRASHED" and missing_generations else None)
        )
        for generation in range(GENERATIONS_PER_SEED):
            key = (seed, generation)
            row = detail_by_generation.get(generation)
            progress = progresses.get(key)
            end = ends.get(key)
            required_pairs = generation * (generation + 1) // 2
            this_pairs = pair_rows.get(key, [])
            this_probes = probe_rows.get(key, [])
            observed_pairs = int(end.get("observed_pair_count", len(this_pairs))) if end else len(this_pairs)
            observed_probes = len(this_probes)
            if row is not None or progress is not None:
                # Fall back to event telemetry if the process stopped after emitting
                # generation progress but before its final seed summary was flushed.
                gates_row = dict(row or progress or {})
                gates_row.setdefault("closure_pair_count", required_pairs)
                gates_row.setdefault("closure_trap_count", sum(bool(x.get("closure_trap")) for x in this_pairs))
                gates_row.setdefault("probe_trap_count", sum(
                    bool(x.get("competence")) and not bool(x.get("reuse_ok")) and bool(x.get("expected_parent_ids"))
                    for x in this_probes
                ))
                complete = bool(
                    progress is not None
                    and end is not None
                    and int(end.get("observed_pair_count", -1)) == required_pairs
                    and int(end.get("missing_pair_count", -1)) == 0
                    and observed_pairs == required_pairs
                    and observed_probes == 4
                )
                gates = _generation_slot_gates(gates_row, generation)
                passed = complete and all(gates.values())
                slot_status = "PASSED" if passed else ("FAILED" if complete else "INCONCLUSIVE")
            elif seed_result["execution_status"] == "TIMEOUT" and generation == active_timeout_generation:
                gates, complete, passed, slot_status = {}, False, False, "TIMEOUT"
            elif seed_result["execution_status"] == "CRASHED" and generation == active_crash_generation:
                gates, complete, passed, slot_status = {}, False, False, "CRASHED"
            elif generation > 0 and generation in missing_generations and (
                (active_timeout_generation is not None and generation > active_timeout_generation)
                or (active_crash_generation is not None and generation > active_crash_generation)
            ):
                gates, complete, passed, slot_status = {}, False, False, "BLOCKED"
            else:
                gates, complete, passed, slot_status = {}, False, False, "INCONCLUSIVE"
            slot_rows.append({
                "seed": seed,
                "generation": generation,
                "required_pair_count": required_pairs,
                "observed_pair_count": observed_pairs,
                "required_probe_count": 4,
                "observed_probe_count": observed_probes,
                "audit_end_observed": end is not None,
                "generation_progress_observed": progress is not None,
                "slot_complete": complete,
                "slot_status": slot_status,
                "slot_gate_checks": gates,
                "slot_gate_passed": passed,
                "promotion": "DO NOT PROMOTE",
            })

    slot_counts = {}
    for row in slot_rows:
        slot_counts[row["slot_status"]] = slot_counts.get(row["slot_status"], 0) + 1
    all_seed_passed = len(seed_results) == 5 and all(item["seed_gate_passed"] for item in seed_results)
    all_slots_passed = len(slot_rows) == 60 and all(item["slot_status"] == "PASSED" for item in slot_rows)
    scientific_status = "PASSED" if all_seed_passed and all_slots_passed else (
        "FAILED" if len(slot_rows) == 60 and all(item["slot_complete"] for item in slot_rows) else "INCOMPLETE"
    )
    run_status = {
        "schema": "ACSIE.h7.v22_3.qualification_status.v2",
        "infrastructure_status": "ORCHESTRATION_COMPLETE" if len(seed_results) == 5 else "INCOMPLETE",
        "scientific_status": scientific_status,
        "qualification_status": "QUALIFIED" if scientific_status == "PASSED" else "NOT_QUALIFIED",
        "frozen_seed_list": FROZEN_SEEDS,
        "generations_per_seed": GENERATIONS_PER_SEED,
        "expected_seed_generation_slots": 60,
        "manifest_seed_generation_slot_count": len(slot_rows),
        "reported_completed_seed_generation_slots": sum(1 for row in slot_rows if row["slot_complete"]),
        "slot_status_counts": slot_counts,
        "seed_results": seed_results,
        "seed_generation_slots": slot_rows,
        "target_access_during_discovery": False,
        "pair_denominator": "g*(g+1)/2",
        "probe_count_per_generation": 4,
        "per_seed_timeout_seconds": SEED_TIMEOUT_SECONDS,
        "audit_jsonl": str(audit_jsonl),
        "pair_audit_directory": str(pair_dir),
        "elapsed_seconds": round(time.time() - overall_started, 3),
        "source_archive_sha256": EMBEDDED_SOURCE_SHA256,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "promotion": "DO NOT PROMOTE",
    }
    _FINAL_RUN_CONTEXT.update({
        "run_status": run_status,
        "seed_results": seed_results,
        "seed_summaries": seed_summaries,
        "seed_events": seed_events,
        "seed_generation_slots": slot_rows,
        "slot_status_counts": slot_counts,
        "qualification_status": run_status["qualification_status"],
        "scientific_status": scientific_status,
        "completed_epoch_seconds": time.time(),
    })
    (output_dir / "acsie-h7-v22-3-slot-manifest.json").write_text(
        json.dumps({
            "schema": "ACSIE.h7.v22_3.seed_generation_slot_manifest.v1",
            "expected_slot_count": 60,
            "slot_count": len(slot_rows),
            "seed_generation_slots": slot_rows,
            "slot_status_counts": slot_counts,
            "promotion": "DO NOT PROMOTE",
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "acsie-h7-v22-3-qualification-status.json").write_text(
        json.dumps(run_status, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    emit("V22_3_QUALIFICATION_STATUS", **{
        key: value for key, value in run_status.items()
        if key not in ("seed_results", "seed_generation_slots")
    })
    return 0 if scientific_status == "PASSED" else 2

def _write_json_atomic(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_final_manifests(output_dir):
    """Persist provenance and a fail-closed summary even after a child crash."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ctx = _FINAL_RUN_CONTEXT
    now = time.time()
    runner_digest = None
    try:
        runner_digest = sha256(Path(__file__).read_bytes())
    except OSError:
        pass
    status = ctx.get("run_status") if isinstance(ctx.get("run_status"), dict) else {}
    seed_results = list(ctx.get("seed_results") or [])
    summaries = dict(ctx.get("seed_summaries") or {})
    slot_rows = list(ctx.get("seed_generation_slots") or [])
    slot_counts = dict(ctx.get("slot_status_counts") or {})
    observed = {(int(r.get("seed", -1)), int(r.get("generation", -1))): r
                for r in slot_rows if isinstance(r, dict)}
    durable_slots = []
    for seed in FROZEN_SEEDS:
        for generation in range(GENERATIONS_PER_SEED):
            row = observed.get((seed, generation))
            if row is None:
                row = {
                    "seed": seed, "generation": generation,
                    "required_pair_count": generation * (generation + 1) // 2,
                    "observed_pair_count": 0, "required_probe_count": 4,
                    "observed_probe_count": 0, "slot_complete": False,
                    "slot_status": "INCONCLUSIVE", "slot_gate_passed": False,
                    "evidence_present": False, "promotion": "DO NOT PROMOTE",
                }
            durable_slots.append(row)
    qualification_status = status.get("qualification_status", ctx.get("qualification_status", "NOT_QUALIFIED"))
    if qualification_status != "QUALIFIED" or len(durable_slots) != 60 or any(r.get("slot_status") != "PASSED" for r in durable_slots):
        qualification_status = "NOT_QUALIFIED"
    manifest = {
        "schema": "ACSIE.h7.v22_3.run_manifest.v1",
        "kernel_id": KERNEL_POLICY.get("id"),
        "run_started_epoch_seconds": ctx.get("started_epoch_seconds"),
        "run_finished_epoch_seconds": now,
        "elapsed_seconds": round(now - float(ctx.get("started_epoch_seconds", now)), 3),
        "executed_archive_sha256": EMBEDDED_SOURCE_SHA256,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "runner_sha256": runner_digest,
        "frozen_seeds": FROZEN_SEEDS,
        "generations_per_seed": GENERATIONS_PER_SEED,
        "expected_seed_generation_slots": 60,
        "seed_results": seed_results,
        "seed_generation_slots": durable_slots,
        "slot_status_counts": slot_counts,
        "target_access_during_discovery": False,
        "pair_denominator": "g*(g+1)/2",
        "qualification_status": qualification_status,
        "scientific_status": status.get("scientific_status", "INCOMPLETE"),
        "terminal_exception": ctx.get("terminal_exception"),
        "promotion": "DO NOT PROMOTE",
    }
    summary = {
        "schema": "ACSIE.h7.v22_3.foundry_summary.v1",
        "executed_archive_sha256": EMBEDDED_SOURCE_SHA256,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "runner_sha256": runner_digest,
        "target_access_during_discovery": False,
        "frozen_seeds": FROZEN_SEEDS,
        "generations_per_seed": GENERATIONS_PER_SEED,
        "expected_seed_generation_slots": 60,
        "seed_results": seed_results,
        "seed_summaries": summaries,
        "seed_generation_slots": durable_slots,
        "slot_status_counts": slot_counts,
        "qualification_status": qualification_status,
        "terminal_exception": ctx.get("terminal_exception"),
        "promotion": "DO NOT PROMOTE",
    }
    _write_json_atomic(output_dir / "run_manifest.json", manifest)
    _write_json_atomic(output_dir / "foundry-summary.json", summary)
    # The ordinary qualification files are also made durable on exception paths.
    _write_json_atomic(output_dir / "acsie-h7-v22-3-slot-manifest.json", {
        "schema": "ACSIE.h7.v22_3.seed_generation_slot_manifest.v1",
        "expected_slot_count": 60, "slot_count": len(durable_slots),
        "seed_generation_slots": durable_slots, "slot_status_counts": slot_counts,
        "promotion": "DO NOT PROMOTE",
    })
    final_status = dict(status)
    final_status.update({
        "qualification_status": qualification_status,
        "target_access_during_discovery": False,
        "source_archive_sha256": EMBEDDED_SOURCE_SHA256,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "runner_sha256": runner_digest,
        "seed_results": seed_results,
        "seed_generation_slots": durable_slots,
        "slot_status_counts": slot_counts,
        "terminal_exception": ctx.get("terminal_exception"),
        "promotion": "DO NOT PROMOTE",
    })
    _write_json_atomic(output_dir / "acsie-h7-v22-3-qualification-status.json", final_status)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase0-only", action="store_true",
                        help="extract, verify, compile and run local regressions only")
    args, _ = parser.parse_known_args()
    checks = check_frozen_contract()
    emit(
        "V22_3_RUNNER_PREFLIGHT",
        preflight_status="PASSED",
        kernel_id=KERNEL_POLICY["id"],
        policy=KERNEL_POLICY,
        frozen_seeds=FROZEN_SEEDS,
        generations_per_seed=GENERATIONS_PER_SEED,
        seed_generation_slots=60,
        required_pair_denominator="g*(g+1)/2",
        target_access_during_discovery=TARGET_ACCESS_DURING_DISCOVERY,
        gate_changes=False,
        promotion="DO NOT PROMOTE",
        checks=checks,
        archive_sha256=EMBEDDED_SOURCE_SHA256,
        manifest_sha256=SOURCE_MANIFEST_SHA256,
    )

    is_kaggle = Path("/kaggle/working").is_dir()
    if is_kaggle:
        output_dir = Path("/kaggle/working")
        root = output_dir / "acsie-h7-v22-3-source"
        exit_code = 2
        _FINAL_RUN_CONTEXT.update({
            "started_epoch_seconds": time.time(),
            "output_dir": str(output_dir),
            "qualification_status": "NOT_QUALIFIED",
            "promotion": "DO NOT PROMOTE",
        })
        try:
            root.mkdir(parents=True, exist_ok=True)
            _, source_root = extract_verified(root)
            if args.phase0_only:
                raise RuntimeError("--phase0-only is only permitted in local staging")
            exit_code = run_frozen_qualification(root, source_root)
        except BaseException as exc:
            _FINAL_RUN_CONTEXT["terminal_exception"] = {
                "type": type(exc).__name__, "message": str(exc)
            }
            _FINAL_RUN_CONTEXT["qualification_status"] = "NOT_QUALIFIED"
            emit("V22_3_RUN_ABORTED", exception_type=type(exc).__name__,
                 message=str(exc), promotion="DO NOT PROMOTE")
            exit_code = 2
        finally:
            try:
                _write_final_manifests(output_dir)
                emit("V22_3_FINAL_MANIFESTS_WRITTEN",
                     run_manifest=str(output_dir / "run_manifest.json"),
                     foundry_summary=str(output_dir / "foundry-summary.json"),
                     qualification_status=_FINAL_RUN_CONTEXT.get("qualification_status", "NOT_QUALIFIED"),
                     promotion="DO NOT PROMOTE")
            except BaseException as manifest_exc:
                emit("V22_3_FINAL_MANIFEST_WRITE_FAILED",
                     exception_type=type(manifest_exc).__name__,
                     message=str(manifest_exc), promotion="DO NOT PROMOTE")
                exit_code = 2
        raise SystemExit(exit_code)

    with tempfile.TemporaryDirectory(prefix="acsie-h7-v22-3-phase0-") as tmp:
        root = Path(tmp)
        _, source_root = extract_verified(root)
        if args.phase0_only:
            raise SystemExit(run_phase0(root, source_root))
        emit("V22_3_EXECUTION_BLOCKED", reason="local execution requires --phase0-only; frozen qualification only runs in Kaggle",
             promotion="DO NOT PROMOTE")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
'''
    runner = (
        template
        .replace("__EMBEDDED_SOURCE_B64__", repr(base64.b64encode(archive_bytes).decode("ascii")))
        .replace("__ARCHIVE_SHA256__", repr(archive_sha))
        .replace("__SOURCE_MANIFEST__", repr(manifest))
        .replace("__SOURCE_MANIFEST_SHA256__", repr(manifest_sha))
        .replace("__KERNEL_METADATA_SHA256__", repr(metadata_sha))
        .replace("__KERNEL_POLICY__", repr(KERNEL_POLICY))
    ).encode("utf-8")

    STAGING_ROOT.mkdir(parents=True, exist_ok=True)
    runner_path = STAGING_ROOT / KERNEL_POLICY["code_file"]
    runner_path.write_bytes(runner)
    (STAGING_ROOT / "kernel-metadata.json").write_bytes(metadata_bytes)
    (STAGING_ROOT / "source-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report = {
        "schema": "ACSIE.h7.v22_3.staging_report.v1",
        "runner_path": str(runner_path.relative_to(REPO_ROOT)),
        "runner_sha256": sha256(runner),
        "runner_bytes": len(runner),
        "embedded_archive_sha256": archive_sha,
        "embedded_archive_bytes": len(archive_bytes),
        "source_manifest_sha256": manifest_sha,
        "source_file_count": len(file_entries),
        "source_manifest_entries": file_entries,
        "kernel_metadata_sha256": metadata_sha,
        "kernel_id": KERNEL_POLICY["id"],
        "kernel_policy": KERNEL_POLICY,
        "runtime_policy": manifest["runtime_policy"],
        "frozen_contract": manifest["frozen_contract"],
        "target_access_during_discovery": False,
        "phase0_only_local_check_required": True,
        "kaggle_dispatch_performed": False,
        "qualification_status": "NOT_QUALIFIED",
        "promotion": "DO NOT PROMOTE",
    }
    report_path = STAGING_ROOT / "build-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "build_status": "PASSED",
        "runner_path": str(runner_path),
        "runner_sha256": report["runner_sha256"],
        "runner_bytes": report["runner_bytes"],
        "embedded_archive_sha256": archive_sha,
        "embedded_archive_bytes": len(archive_bytes),
        "source_manifest_sha256": manifest_sha,
        "source_file_count": len(file_entries),
        "kernel_metadata_sha256": metadata_sha,
        "phase0_only_local_check_required": True,
        "kaggle_dispatch_performed": False,
        "promotion": "DO NOT PROMOTE",
    }, indent=2, sort_keys=True))
    return report


if __name__ == "__main__":
    build()

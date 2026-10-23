#!/usr/bin/env python3
"""Run the pinned Gen3 Foundry on Kaggle without exporting research data to GitHub.

This source currently exposes one Foundry invocation per seed, not a 12-generation
checkpoint API. The runner preserves those diagnostic outcomes and marks the frozen
5-seed x 12-generation qualification INCONCLUSIVE; it never fabricates generations.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SEEDS = (771221, 771222, 771223, 771224, 771225)
STATUS = {"PASSED", "FAILED", "BLOCKED", "CRASHED", "INVALID", "INCONCLUSIVE"}
REQUIRED_INTEGRITY = (
    "external_model", "pretrained_model", "embeddings", "external_api",
    "hidden_prompt", "task_family_routing", "target_access_during_discovery",
    "holdout_used_for_training", "holdout_used_for_selection",
    "transfer_used_for_selection", "hidden_strategy", "network_dependency",
)
ROOT = Path(__file__).resolve().parent


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


def classify(result: dict[str, Any]) -> str:
    status = result.get("scientific_status")
    if status in STATUS:
        return status
    return "PASSED" if result.get("passed") is True else "FAILED"


def load_source_manifest() -> dict[str, Any]:
    path = ROOT / "source-manifest.json"
    if not path.is_file():
        raise RuntimeError("source-manifest.json missing; submit only through the private Tester- dispatcher")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    sha = manifest.get("source_commit")
    if manifest.get("repository") != "Infrasigma/ACSIE" or not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("invalid ACSIE source manifest")
    if manifest.get("network_during_research") is not False:
        raise RuntimeError("research kernel must keep internet disabled")
    return manifest


def main() -> int:
    manifest = load_source_manifest()
    source_sha = manifest["source_commit"]
    run_id = f"gen3-foundry-{source_sha[:10]}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    working = Path("/kaggle/working")
    if not working.is_dir():
        working = ROOT / "kaggle-output"
    result_dir = working / "seed-results"
    result_dir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(ROOT))
    import_error = None
    try:
        module = importlib.import_module("research.gen3_learning_rule_foundry_v1")
        foundry_run = getattr(module, "run")
        if not callable(foundry_run):
            raise RuntimeError("Foundry module has no callable run(seed)")
    except Exception as exc:
        import_error = {
            "exception_type": type(exc).__name__,
            "exception": str(exc),
            "traceback": traceback.format_exc(),
        }
        foundry_run = None

    results: list[dict[str, Any]] = []
    for seed in SEEDS:
        if import_error is not None:
            result = {
                "version": "gen3-learning-rule-foundry-v1",
                "seed": seed,
                "scientific_status": "CRASHED",
                "passed": False,
                "reason": "foundry_import_or_interface_failure",
                **import_error,
            }
        else:
            try:
                raw = foundry_run(seed)
                if not isinstance(raw, dict):
                    raise TypeError("Foundry run(seed) did not return a JSON-compatible object")
                result = dict(raw)
                result.setdefault("seed", seed)
                result["scientific_status"] = classify(result)
                result["passed"] = result.get("passed") is True and result["scientific_status"] == "PASSED"
            except Exception as exc:
                result = {
                    "version": "gen3-learning-rule-foundry-v1",
                    "seed": seed,
                    "scientific_status": "CRASHED",
                    "passed": False,
                    "reason": "foundry_invocation_exception",
                    "exception_type": type(exc).__name__,
                    "exception": str(exc),
                    "traceback": traceback.format_exc(),
                }
        if result["scientific_status"] not in STATUS:
            result["scientific_status"] = "INVALID"
            result["passed"] = False
            result["reason"] = "unsupported_scientific_status"
        results.append(result)
        write_json(result_dir / f"result-{seed}.json", result)

    failures: list[dict[str, Any]] = []
    for result in results:
        if result["scientific_status"] != "PASSED":
            failures.append({
                "status": result["scientific_status"] if result["scientific_status"] in {"FAILED", "BLOCKED", "CRASHED", "INVALID", "INCONCLUSIVE"} else "FAILED",
                "reason": str(result.get("reason") or f"seed {result['seed']} did not pass"),
                "seed": int(result["seed"]),
            })

    # Preserve only integrity flags actually reported explicitly by every seed.
    integrity: dict[str, bool] = {}
    for flag in REQUIRED_INTEGRITY:
        values = [
            row.get("integrity", {}).get(flag)
            for row in results
            if isinstance(row.get("integrity"), dict) and isinstance(row["integrity"].get(flag), bool)
        ]
        if len(values) == len(results):
            integrity[flag] = any(values)

    if any(row["scientific_status"] == "CRASHED" for row in results):
        foundry_status = "CRASHED"
    elif any(row["scientific_status"] == "INVALID" for row in results):
        foundry_status = "INVALID"
    elif any(row["scientific_status"] != "PASSED" for row in results):
        foundry_status = "FAILED"
    else:
        foundry_status = "PASSED"

    # Empty generation arrays honestly record missing coverage; no 0..11 rows are fabricated.
    seed_results = [
        {"seed": int(row["seed"]), "scientific_status": row["scientific_status"], "generations": []}
        for row in results
    ]
    artifact_records = []
    for path in sorted(result_dir.glob("result-*.json")):
        artifact_records.append({
            "storage": "kaggle-kernel-output",
            "path": path.relative_to(working).as_posix(),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        })

    candidate = {
        "candidate_schema": "ACSIE.kaggle-foundry-candidate.v1",
        "run_id": run_id,
        "created_at_utc": utc_now(),
        "experiment_id": "gen3-learning-rule-foundry-v1",
        "scientific_status": foundry_status,
        "qualification_status": "INCONCLUSIVE",
        "qualification_reason": (
            "The pinned Foundry source exposes one run(seed) invocation, not an explicit "
            "12-generation driver/checkpoint interface. The 5x12 gate is therefore incomplete; "
            "no generation records are fabricated."
        ),
        "source": {"repository": "Infrasigma/ACSIE", "commit_sha": source_sha},
        "execution": {
            "platform": "kaggle",
            "kernel_slug": "memorican/acsie-gen3-foundry",
            "kernel_visibility": "private",
            "internet_enabled": False,
            "entrypoint": "python run_kaggle_foundry.py",
            "dataset_inputs": [],
        },
        "gate": {
            "gate_id": "frozen_5x12",
            "qualification": True,
            "expected_seed_count": 5,
            "expected_generations_per_seed": 12,
        },
        "expected_seed_ids": list(SEEDS),
        "seed_results": seed_results,
        "artifacts": artifact_records,
        "integrity": integrity,
        "failures": failures,
        "diagnostic_results": [
            {"seed": int(row["seed"]), "scientific_status": row["scientific_status"], "passed": row.get("passed") is True,
             "reason": row.get("reason")}
            for row in results
        ],
        "provenance": {
            "workflow_source": "Infrasigma/Tester-",
            "orchestration_commit": manifest.get("orchestration_commit"),
            "requested_acsie_ref": manifest.get("requested_ref"),
            "actual_acsie_commit": source_sha,
        },
    }
    write_json(working / "receipt-candidate.json", candidate)
    summary = {
        "run_id": run_id,
        "source_commit": source_sha,
        "foundry_status": foundry_status,
        "qualification_status": "INCONCLUSIVE",
        "expected_matrix_records": 60,
        "observed_generation_records": sum(len(row["generations"]) for row in seed_results),
        "seed_count": len(results),
        "artifacts": len(artifact_records),
        "reason": candidate["qualification_reason"],
    }
    write_json(working / "foundry-summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if len(results) == len(SEEDS) else 2


if __name__ == "__main__":
    raise SystemExit(main())

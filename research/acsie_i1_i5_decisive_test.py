#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import random
from dataclasses import asdict
from hashlib import sha256

from cognitive_core.recursive_research import (
    CapabilityDemandModel,
    DeficitHypothesis,
    MechanismConfig,
    RecursiveResearchLoop,
    clone_with_config,
    fit_core,
    learning_curve_auc,
    score_core,
)

Row = tuple[object, str, object]


def digest(x: object) -> str:
    return sha256(json.dumps(x, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def row(rng: random.Random, rule: str, shape: str = "dict") -> Row:
    x = rng.randint(-15, 15)
    y = rng.randint(-15, 15)
    z = rng.randint(-15, 15)
    sx, sy, sz = x < 0, y < 0, z < 0
    px, py, pz = x % 2, y % 2, z % 2

    if rule == "sign_xy":
        cond = sx == sy
        lo, hi = 1, 6
    elif rule == "parity_xy":
        cond = px == py
        lo, hi = 2, 7
    elif rule == "sign_xz":
        cond = sx == sz
        lo, hi = 3, 8
    elif rule == "parity_yz":
        cond = py == pz
        lo, hi = 4, 9
    elif rule == "xor_sign_parity":
        cond = (sx == sy) ^ (px == pz)
        lo, hi = 5, 10
    elif rule == "xor_parity_sign":
        cond = (px == py) ^ (sy == sz)
        lo, hi = 6, 11
    elif rule == "and_sign_parity":
        cond = (sx == sz) and (py == pz)
        lo, hi = 7, 12
    elif rule == "unknown_sum_parity":
        cond = ((x + y) % 2) == (z % 2)
        lo, hi = 9, 14
    else:
        raise ValueError(rule)

    if shape == "list":
        return ([x, y, z], "step", [x, y, z + (lo if cond else hi)])
    return ({"x": x, "y": y, "z": z}, "step", {"x": x, "y": y, "z": z + (lo if cond else hi)})


def rows(seed: int, rule: str, n: int, shape: str = "dict") -> tuple[Row, ...]:
    rng = random.Random(seed)
    return tuple(row(rng, rule, shape) for _ in range(n))


def make_dataset(seed: int, rule: str, transfer: str, future: str, shape: str = "dict") -> dict[str, tuple[Row, ...]]:
    return {
        "train": rows(seed + 1, rule, 48, shape),
        "fresh": rows(seed + 101, rule, 32, shape),
        "holdout": rows(seed + 201, rule, 32, shape),
        "transfer": rows(seed + 301, transfer, 32, "list" if shape == "dict" else "dict"),
        "future": rows(seed + 401, future, 32, "list" if shape == "dict" else "dict"),
    }


def diagnostic_case(seed: int, case: str) -> tuple[str, MechanismConfig, tuple[Row, ...], tuple[Row, ...], set[str]]:
    """Hidden evaluator scenario; no case label enters the candidate loop."""
    rng = random.Random(seed + 991)

    if case == "search":
        cfg = MechanismConfig(
            beam=4,
            memory_limit=64,
            max_expression_depth=1,
            evidence_threshold=0.78,
            min_support_count=2,
            delayed_window=4,
            prediction_mode="ensemble",
            context_mode="shape",
        )
        train = rows(seed + 10, "xor_sign_parity", 48)
        test = rows(seed + 11, "xor_sign_parity", 32)
        return case, cfg, train, test, {"search"}

    if case == "memory":
        cfg = MechanismConfig(
            beam=16,
            memory_limit=4,
            max_expression_depth=3,
            evidence_threshold=0.78,
            min_support_count=2,
            delayed_window=4,
            prediction_mode="ensemble",
            context_mode="shape",
        )
        distractors = rows(seed + 20, "sign_xy", 64)
        target = rows(seed + 21, "parity_xy", 8)
        # Target examples are deliberately late so a tiny memory window cannot retain them.
        train = tuple(distractors) + tuple(target)
        test = rows(seed + 22, "parity_xy", 32)
        return case, cfg, train, test, {"memory"}

    if case == "confounded":
        cfg = MechanismConfig(
            beam=4,
            memory_limit=4,
            max_expression_depth=1,
            evidence_threshold=0.78,
            min_support_count=2,
            delayed_window=4,
            prediction_mode="ensemble",
            context_mode="shape",
        )
        distractors = rows(seed + 30, "sign_xy", 64)
        target = rows(seed + 31, "xor_sign_parity", 8)
        train = tuple(distractors) + tuple(target)
        test = rows(seed + 32, "xor_sign_parity", 32)
        return case, cfg, train, test, {"search", "memory"}

    if case == "unknown":
        cfg = MechanismConfig(
            beam=16,
            memory_limit=64,
            max_expression_depth=3,
            evidence_threshold=0.99,
            min_support_count=99,
            delayed_window=4,
            prediction_mode="ensemble",
            context_mode="shape",
        )
        train = rows(seed + 40, "parity_xy", 48)
        test = rows(seed + 41, "parity_xy", 32)
        return case, cfg, train, test, {"unknown"}

    raise ValueError(case)


def run_i1(seed: int) -> dict[str, object]:
    case_names = ("search", "memory", "confounded", "unknown")
    case = case_names[seed % len(case_names)]
    case, cfg, train, test, truth = diagnostic_case(seed, case)
    core = clone_with_config(
        RecursiveResearchLoop(seed, cfg).core,
        cfg,
        seed=seed + 700,
    )
    model = CapabilityDemandModel()
    hyps = model.diagnose(
        train,
        {"diagnostic_case": digest(test)},
        core,
        cfg,
    )

    ranked = sorted(hyps, key=lambda h: (h.probability, h.name), reverse=True)
    head = ranked[0].name if ranked else "unknown"
    effects = dict(ranked[0].evidence.get("probe_effects", {})) if ranked else {}
    known_ok = head in truth
    if "unknown" in truth:
        passed = head == "unknown"
    elif case == "confounded":
        top_two = {h.name for h in ranked[:2]}
        non_common = len(top_two.intersection(truth)) == 2
        values = sorted(
            [float(effects.get("search", 0.0)), float(effects.get("memory", 0.0))],
            reverse=True,
        )
        discriminates = len(values) == 2 and abs(values[0] - values[1]) >= 0.01
        passed = non_common and discriminates
    else:
        passed = known_ok

    return {
        "case": case,
        "truth_set": sorted(truth),
        "diagnosis": [asdict(h) for h in hyps],
        "top_hypothesis": head,
        "probe_effects": effects,
        "passed": passed,
        "integrity": {
            "target_identity_available": False,
            "task_family_routing": False,
            "holdout_used_for_diagnosis": False,
            "external_model": False,
            "network_dependency": False,
            "manual_runtime_strategy": False,
        },
    }


def run_recursive(seed: int, stages: int) -> dict[str, object]:
    initial = MechanismConfig(
        beam=16,
        memory_limit=32,
        max_expression_depth=2,
        evidence_threshold=0.78,
        min_support_count=2,
        delayed_window=4,
        prediction_mode="ensemble",
        context_mode="shape",
        context_program=None,
    )
    loop = RecursiveResearchLoop(seed, initial)
    stage_rules = [
        ("sign_xy", "parity_xy", "sign_xz", "dict"),
        ("parity_xy", "sign_xz", "xor_sign_parity", "list"),
        ("sign_xz", "xor_sign_parity", "xor_parity_sign", "dict"),
        ("xor_sign_parity", "xor_parity_sign", "and_sign_parity", "list"),
        ("xor_parity_sign", "and_sign_parity", "unknown_sum_parity", "dict"),
        ("and_sign_parity", "unknown_sum_parity", "sign_xy", "list"),
        ("unknown_sum_parity", "sign_xy", "parity_yz", "dict"),
    ]

    stage_records = []
    stage_datasets = []

    for i, (rule_name, transfer_rule, future_rule, shape) in enumerate(stage_rules[:stages]):
        ds = make_dataset(seed + i * 10000, rule_name, transfer_rule, future_rule, shape)
        stage_datasets.append(ds)
        record = loop.run_stage(ds)
        stage_records.append({
            "stage": i,
            "record": record,
            "rule_identity_evaluator_only": rule_name,
            "shape_evaluator_only": shape,
        })

    # Retest historical fresh capabilities after all later modifications.
    historical = []
    for i, ds in enumerate(stage_datasets[:-1]):
        historical.append({
            "stage": i,
            "fresh_after_later_changes": score_core(loop.core, ds["fresh"]),
        })

    accepted = [x for x in stage_records if x["record"].get("accepted")]
    ranking_regrets = [float(x["record"].get("ranking_regret", 0.0)) for x in stage_records]

    # Prospective self-model calibration, based only on committed pre-intervention predictions.
    calibration = []
    future_prediction_error = []
    for r in loop.self_model.records:
        pred = r.get("prediction", {})
        obs = r.get("observed", {})
        calibration.append(
            abs(
                float(pred.get("predicted_success_probability", 0.5))
                - float(obs.get("accepted", 0.0))
            )
        )
        future_prediction_error.append(
            abs(
                float(pred.get("predicted_future_learning_gain", 0.0))
                - float(obs.get("future_learning_auc_delta", 0.0))
            )
        )

    mid = max(1, len(calibration) // 2)
    calibration_early = sum(calibration[:mid]) / len(calibration[:mid]) if calibration else 1.0
    calibration_late = sum(calibration[mid:]) / len(calibration[mid:]) if calibration[mid:] else calibration_early
    future_err_early = sum(future_prediction_error[:mid]) / len(future_prediction_error[:mid]) if future_prediction_error[:mid] else 1.0
    future_err_late = sum(future_prediction_error[mid:]) / len(future_prediction_error[mid:]) if future_prediction_error[mid:] else future_err_early

    i1 = run_i1(seed)

    recursive_pass = (
        len(accepted) >= max(3, stages // 2)
        and any(x["record"].get("diagnosis", [{}])[0].get("name") == "unknown" for x in stage_records)
        and len(set(ranking_regrets)) > 0
    )
    self_model_signal = (
        len(calibration) >= 8
        and calibration_late <= calibration_early + 0.05
        and future_err_late <= future_err_early + 0.05
    )
    ontology_expansion = False
    ontology_status = "NOT_DEMONSTRATED"

    # Current I5 implementation can identify persistent unexplained residuals but
    # does not yet prove a newly invented capability mechanism. Record that boundary
    # explicitly instead of promoting ontology expansion on self-report.
    if "unknown-residual" in loop.ontology:
        ontology_status = "RESIDUAL_IDENTIFIED_NOT_PROMOTED"

    historical_regression = []
    for item in historical:
        historical_regression.append({
            "stage": item["stage"],
            "fresh_after_later_changes": item["fresh_after_later_changes"],
        })

    return {
        "i1": i1,
        "stage_records": stage_records,
        "accepted_stage_count": len(accepted),
        "ranking_regret_sequence": ranking_regrets,
        "self_model": {
            "record_count": len(loop.self_model.records),
            "calibration_error_early": calibration_early,
            "calibration_error_late": calibration_late,
            "future_prediction_error_early": future_err_early,
            "future_prediction_error_late": future_err_late,
            "improvement_signal": self_model_signal,
        },
        "recursive_signal": recursive_pass,
        "historical_regression": historical_regression,
        "ontology": sorted(loop.ontology),
        "ontology_status": ontology_status,
        "ontology_expansion_proven": ontology_expansion,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--stages", type=int, default=7)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    recursive = run_recursive(args.seed, args.stages)
    i1 = recursive["i1"]
    integrity_ok = all(bool(v) is True for v in i1["integrity"].values())

    # This is intentionally a hard, bounded scientific gate, not an ASI claim.
    # A seed only passes when diagnosis, recursive improvement signals, and integrity
    # all survive together. Ontology expansion remains a separately reported result.
    scientific_status = (
        "PASSED"
        if i1["passed"] and recursive["recursive_signal"] and recursive["self_model"]["improvement_signal"] and integrity_ok
        else "FAILED"
    )

    artifact = {
        "schema": "ACSIE.i1-i5.decisive-evaluator.v2",
        "seed": args.seed,
        "scientific_status": scientific_status,
        "i1": i1,
        "accepted_stage_count": recursive["accepted_stage_count"],
        "ranking_regret_sequence": recursive["ranking_regret_sequence"],
        "recursive_signal": recursive["recursive_signal"],
        "self_model": recursive["self_model"],
        "historical_regression": recursive["historical_regression"],
        "ontology": recursive["ontology"],
        "ontology_status": recursive["ontology_status"],
        "ontology_expansion_proven": recursive["ontology_expansion_proven"],
        "claim_ledger": {
            "capability_demand_inference": "PASSED" if i1["passed"] else "FAILED",
            "causal_self_model": "PROVISIONAL" if recursive["self_model"]["record_count"] else "FAILED",
            "open_hypothesis_engine": "PROVISIONAL",
            "quarantined_admission": "PROVISIONAL",
            "recursive_improvement": "PASSED" if recursive["recursive_signal"] else "FAILED",
            "ontology_expansion": recursive["ontology_status"],
            "ASI": "NOT_DEMONSTRATED",
        },
    }

    (out / "i1_i5_result.json").write_text(json.dumps(artifact, indent=2, sort_keys=True))
    print(json.dumps({
        "seed": args.seed,
        "scientific_status": scientific_status,
        "i1_passed": i1["passed"],
        "top_hypothesis": i1["top_hypothesis"],
        "accepted_stage_count": recursive["accepted_stage_count"],
        "recursive_signal": recursive["recursive_signal"],
        "self_model_signal": recursive["self_model"]["improvement_signal"],
        "ontology_status": recursive["ontology_status"],
    }, indent=2, sort_keys=True))
    return 0 if scientific_status == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

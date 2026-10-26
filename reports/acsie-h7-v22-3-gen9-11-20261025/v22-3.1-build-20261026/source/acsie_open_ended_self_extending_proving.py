#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from hashlib import sha256
from typing import Any

from cognitive_core.open_ended_growth import (
    OpenEndedRecursiveCognitiveCompiler,
    canonical_parent_generation_details,
)
from lab.exact_checkpoint import load_checkpoint, restore_checkpoint, save_checkpoint
from cognitive_core.recursive_cognitive_compiler import (
    RecursiveCognitiveCompiler,
    ProcessCandidate,
    Trace,
    eval_expr,
    ast_depth,
)
from research.h7_generation_pair_summary import (
    audit_generation_pair_summary,
    build_generation_pair_summary,
)
from lab.h7_exact_audit import memoized_eval_expr


BASE_BIN_OPS = ("add", "sub", "mul", "max", "min")
UNARY_OPS = ("abs", "neg")
KEYS = ("x", "y", "z")
_H7_ACTIVE_GENERATION_CONTEXT: dict[str, Any] = {}


@dataclass(frozen=True)
class HiddenCapability:
    hidden_id: str
    primitive_id: str
    expression: dict[str, Any]
    depth: int
    generation: int
    parent_hidden_id: str | None = None
    parent_hidden_ids: tuple[str, ...] = ()


def stable_int(text: str) -> int:
    return int.from_bytes(sha256(text.encode()).digest()[:4], "big")


def random_base_expr(rng: random.Random, depth: int) -> dict[str, Any]:
    if depth <= 1:
        if rng.random() < 0.75:
            return {"op": "get", "key": rng.choice(KEYS)}
        return {"op": "const", "value": rng.choice((-2, -1, 0, 1, 2, 3, 4))}
    if rng.random() < 0.20:
        return {"op": rng.choice(UNARY_OPS), "arg": random_base_expr(rng, depth - 1)}
    return {
        "op": rng.choice(BASE_BIN_OPS),
        "left": random_base_expr(rng, depth - 1),
        "right": random_base_expr(rng, depth - 1),
    }


def hard_bootstrap_expr(rng: random.Random) -> dict[str, Any]:
    """Generate a neutral, nontrivial depth-3 bootstrap capability."""
    def leaf() -> dict[str, Any]:
        if rng.random() < 0.8:
            return {"op": "get", "key": rng.choice(KEYS)}
        # Keep hard bootstrap inside the same neutral expression vocabulary
        # that ACSIE's generic search substrate can actually enumerate.
        return {"op": "const", "value": rng.choice((-2, -1, 0, 1, 2, 3, 4))}

    unary_child = {"op": rng.choice(UNARY_OPS), "arg": leaf()}
    binary_child = {
        "op": rng.choice(BASE_BIN_OPS),
        "left": leaf(),
        "right": leaf(),
    }
    return {
        "op": rng.choice(BASE_BIN_OPS),
        "left": unary_child,
        "right": binary_child,
    }


def wrap_parent(rng: random.Random, parent: dict[str, Any]) -> dict[str, Any]:
    op = rng.choice(BASE_BIN_OPS + UNARY_OPS)
    if op in UNARY_OPS:
        return {"op": op, "arg": parent}
    if rng.random() < 0.5:
        rhs = {"op": "get", "key": rng.choice(KEYS)}
    else:
        rhs = {"op": "const", "value": rng.choice((-2, -1, 0, 1, 2, 3, 4))}
    return {"op": op, "left": parent, "right": rhs}


def combine_parents(
    rng: random.Random,
    parents: tuple[HiddenCapability, ...],
) -> dict[str, Any]:
    if len(parents) == 1:
        return wrap_parent(rng, parents[0].expression)
    op = rng.choice(("add", "sub", "mul", "max", "min"))
    return {
        "op": op,
        "left": parents[0].expression,
        "right": parents[1].expression,
    }


def eval_hidden(
    expr: dict[str, Any],
    row: dict[str, float],
    macros: dict[str, dict[str, Any]],
) -> float:
    return float(eval_expr(expr, row, macros))


def expanded_depth(
    expr: dict[str, Any],
    macros: dict[str, dict[str, Any]],
    stack: tuple[str, ...] = (),
) -> int:
    op = expr["op"]
    if op == "macro":
        mid = str(expr["id"])
        if mid in stack or mid not in macros:
            return 1
        return expanded_depth(macros[mid], macros, stack + (mid,))
    if op in {"get", "const"}:
        return 1
    if op in {"abs", "neg", "threshold"}:
        return 1 + expanded_depth(expr["arg"], macros, stack)
    return 1 + max(
        expanded_depth(expr["left"], macros, stack),
        expanded_depth(expr["right"], macros, stack),
    )


def make_traces(expr, seed, generation, split, count, shift, macros):
    rng = random.Random(seed * 1000003 + generation * 9176 + stable_int(split))
    base_split = split.rsplit("_", 1)[-1]
    span = {
        "train": 2.0,
        "selection": 2.5,
        "holdout": 3.0,
        "transfer": 4.0,
        "ood": 5.0,
    }[base_split]
    rows = []
    for i in range(count):
        inputs = {k: rng.uniform(-span, span) + shift for k in KEYS}
        rows.append(
            Trace(
                inputs=inputs,
                target=eval_hidden(expr, inputs, macros),
                family="opaque",
                context={"risk": 0.0, "ambiguity": 0.0},
                task_id=f"opaque-{seed}-{generation}-{split}-{i}",
            )
        )
    return tuple(rows)


def mae(expr, rows, macros):
    if not rows:
        return float("inf")
    vals = []
    for row in rows:
        try:
            vals.append(abs(float(eval_expr(expr, row.inputs, macros)) - row.target))
        except Exception:
            return float("inf")
    return statistics.fmean(vals)


def semantic_parent_match_count(
    learner: RecursiveCognitiveCompiler,
    expected_caps: tuple[HiddenCapability, ...],
    used_primitive_ids: tuple[str, ...],
    rows: tuple[Trace, ...],
    hidden_macros: dict[str, dict[str, Any]],
) -> int:
    if not expected_caps or not used_primitive_ids:
        return 0
    pmap = learner._pmap()
    used_vectors: dict[str, tuple[float, ...]] = {}
    for pid in used_primitive_ids:
        primitive = learner.primitives.get(pid)
        if primitive is None:
            continue
        try:
            used_vectors[pid] = tuple(
                float(eval_expr(primitive.expression, row.inputs, pmap))
                for row in rows
            )
        except Exception:
            continue

    expected_vectors: list[tuple[float, ...]] = []
    for cap in expected_caps:
        try:
            expected_vectors.append(
                tuple(
                    float(eval_hidden(cap.expression, row.inputs, hidden_macros))
                    for row in rows
                )
            )
        except Exception:
            expected_vectors.append(())

    matched: set[str] = set()
    count = 0
    for expected_vector in expected_vectors:
        for pid, vector in used_vectors.items():
            if pid in matched:
                continue
            if vector == expected_vector:
                matched.add(pid)
                count += 1
                break
    return count


def retained_representation_error(
    learner: RecursiveCognitiveCompiler,
    cap: HiddenCapability,
    rows: tuple[Trace, ...],
    hidden_macros: dict[str, dict[str, Any]],
    *,
    primitive_macros=None,
    evaluation_cache: dict | None = None,
    evaluation_cache_stats: dict[str, int] | None = None,
) -> float:
    """Compare retained executable behavior with the hidden capability exactly.

    Optional pass-local node memoization avoids recomputing shared primitive and
    hidden-expression subtrees during the target-parent audit. With no cache the
    historical evaluator path is preserved exactly.
    """
    primitive = learner.primitives.get(cap.primitive_id)
    if primitive is None:
        return float("inf")
    pmap = learner._pmap() if primitive_macros is None else primitive_macros
    if not rows:
        return float("inf")
    deltas = []
    for row in rows:
        try:
            if evaluation_cache is None:
                retained_value = float(eval_expr(primitive.expression, row.inputs, pmap))
                hidden_value = float(eval_hidden(cap.expression, row.inputs, hidden_macros))
            else:
                retained_value = float(memoized_eval_expr(
                    primitive.expression, row.inputs, pmap, evaluation_cache,
                    evaluation_cache_stats,
                ))
                hidden_value = float(memoized_eval_expr(
                    cap.expression, row.inputs, hidden_macros, evaluation_cache,
                    evaluation_cache_stats,
                ))
        except Exception:
            return float("inf")
        deltas.append(abs(retained_value - hidden_value))
    return statistics.fmean(deltas)


def synthesize_discovery_only(
    compiler: RecursiveCognitiveCompiler,
    rows: tuple[Trace, ...],
    transfer: tuple[Trace, ...],
) -> Any:
    """Baseline process selection that never observes OOD during search."""
    keys = sorted(set().union(*(trace.inputs.keys() for trace in rows)))
    pids = tuple(compiler.primitives)
    candidates = []
    pmap = compiler._pmap()
    for policy in compiler.propose_search_policies():
        for expr in compiler._exprs(keys, pids, min(3, int(policy['max_depth']))):
            try:
                train_error = sum(
                    abs(eval_expr(expr, trace.inputs, pmap) - trace.target)
                    for trace in rows
                ) / len(rows)
                if train_error > 1e-9:
                    continue
                # Baseline candidate generation sees discovery rows only.
                # Transfer/OOD remain post-selection evaluation evidence.
                used = tuple(sorted({str(node['id']) for node in compiler._walk(expr) if node.get('op') == 'macro'}))
                novelty = 1.0 / (1 + len(json.dumps(expr, sort_keys=True)))
                candidates.append((len(used), novelty, -len(json.dumps(expr, sort_keys=True)), json.dumps(expr, sort_keys=True), expr, used, policy))
            except Exception:
                continue
    if not candidates:
        return None
    _, _, _, _, expr, used, policy = max(
        candidates,
        key=lambda c: (c[0], c[1], c[2], c[3]),
    )
    process_id = 'baseline-proc:' + sha256(json.dumps((expr, policy, compiler.generation), sort_keys=True).encode()).hexdigest()[:20]
    proc = ProcessCandidate(
        process_id, expr, used, compiler.generation, tuple(used), dict(policy),
        tuple(sorted({trace.family for trace in list(rows) + list(transfer)})),
        len(json.dumps(expr, sort_keys=True)),
        {'origin': 'discovery_only_baseline', 'external_model': False, 'ood_used_for_selection': False},
    )
    compiler.processes[proc.process_id] = proc
    return proc

def provenance_lineage_ids(
    learner: RecursiveCognitiveCompiler,
    primitive_ids: tuple[str, ...],
) -> set[str]:
    lineage: set[str] = set()
    method = getattr(learner, "primitive_lineage", None)
    for pid in primitive_ids:
        if method is None:
            lineage.add(str(pid))
        else:
            lineage.update(str(x) for x in method(str(pid)))
    return lineage


def executable_lineage_ids(
    learner: RecursiveCognitiveCompiler,
    primitive_ids: tuple[str, ...],
) -> set[str]:
    """Runtime-independent executable lineage evaluator.

    This deliberately does not call a runtime lineage helper. The evaluator
    follows only actual executable macro references in primitive expressions,
    so pre-PR110 and PR110 runtimes are judged by exactly the same semantics.
    """
    lineage: set[str] = set()
    stack = [str(pid) for pid in primitive_ids]
    seen: set[str] = set()

    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        lineage.add(pid)
        primitive = learner.primitives.get(pid)
        if primitive is None:
            continue
        for node in learner._walk(primitive.expression):
            if node.get("op") == "macro":
                stack.append(str(node["id"]))
    return lineage


def select_discovery_ranked_candidate(frontier):
    """Select by discovery-ranked frontier order, before validation metrics are read."""
    return frontier[0] if frontier else None


def selected_closure_reuse_gate(
    selected_competence: bool,
    selected_executable_lineage: set[str],
    expected_parent_ids: set[str],
) -> tuple[bool, bool, bool]:
    """Return (competence, reuse_ok, closure_trap) for the selected candidate only."""
    competence = bool(selected_competence)
    reuse_ok = bool(competence and expected_parent_ids.issubset(selected_executable_lineage))
    closure_trap = bool(competence and not reuse_ok)
    return competence, reuse_ok, closure_trap


def primary_pair_recency_gate(
    generation: int,
    pair_gens: list[int] | tuple[int, ...],
    pair_ids: list[str] | tuple[str, ...] | None = None,
    primary_macro_ids: list[str] | tuple[str, ...] | None = None,
) -> bool | None:
    """Mirror the frozen V22.2 Gen9-11 primary-pair eligibility predicate."""
    generation = int(generation)
    if generation not in (9, 10, 11):
        return None
    values = [int(value) for value in pair_gens]
    if len(values) != 2 or min(values) < 0 or max(values) < generation - 1:
        return False
    if pair_ids is not None and primary_macro_ids is not None:
        direct = set(map(str, pair_ids))
        if len(direct) != 2 or not direct.issubset(set(map(str, primary_macro_ids))):
            return False
    legacy_primary_pair_generations = {
        9: frozenset((4, 7)),
        10: frozenset((1, 4)),
        11: frozenset((3, 4)),
    }
    if legacy_primary_pair_generations.get(generation) == frozenset(values):
        return False
    return True


def compact_search_stats(search_stats: dict[str, Any]) -> dict[str, Any]:
    """Keep evidence useful without serializing tens of thousands of lineage strings."""
    out = dict(search_stats)
    signatures = tuple(str(x) for x in out.pop("target_candidate_lineage_signatures", ()))
    out["target_candidate_lineage_signature_count"] = len(signatures)
    out["target_candidate_lineage_signature_sample"] = list(signatures[:16])
    return out

def _h7_json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    return repr(value)


def _h7_runtime_metrics(learner: Any) -> dict[str, Any]:
    primary_ids = [str(pid) for pid in getattr(learner, "_h7_primary_macro_ids", ())]
    try:
        state = learner.export_state()
        state_bytes = len(json.dumps(state, sort_keys=True, default=_h7_json_default).encode("utf-8"))
    except Exception:
        state_bytes = None
    try:
        archive = getattr(learner, "archive", {})
        archive_payload = {
            str(pid): (asdict(record) if is_dataclass(record) else repr(record))
            for pid, record in archive.items()
        }
        archive_bytes = len(json.dumps(archive_payload, sort_keys=True, default=_h7_json_default).encode("utf-8"))
    except Exception:
        archive_bytes = None
    process_frontier = getattr(learner, "last_process_candidate_frontier", ()) or ()
    primitive_frontier = getattr(learner, "last_primitive_candidate_frontier", ()) or ()
    generic_frontier = getattr(learner, "process_frontier", ()) or ()
    return {
        "primary_macro_count": len(primary_ids),
        "primary_macro_ids_sha256": sha256(json.dumps(primary_ids, separators=(",", ":")).encode("utf-8")).hexdigest(),
        "primitive_count": len(getattr(learner, "primitives", {})),
        "frontier_count": len(process_frontier or primitive_frontier or generic_frontier),
        "archive_bytes_estimate": archive_bytes,
        "state_bytes_estimate": state_bytes,
    }


def _h7_emit_event(event: str, **fields: Any) -> None:
    record = {"event": event, **fields}
    line = json.dumps(record, sort_keys=True, default=_h7_json_default, separators=(",", ":"))
    print(line, flush=True)
    # Best-effort line-buffered durability: a later timeout does not erase the
    # completed pair records already written to the working directory.
    event_path = os.environ.get("ACSIE_H7_AUDIT_JSONL", "acsie-h7-audit-events.jsonl")
    try:
        with open(event_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
    except OSError:
        pass


def _h7_write_pair_summary(seed: int, generation: int, summary: dict[str, Any]) -> str | None:
    output_dir = Path(os.environ.get("ACSIE_H7_PAIR_AUDIT_DIR", "h7-pair-audit-summaries"))
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"seed-{seed}-generation-{generation:02d}.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(summary, sort_keys=True, indent=2, default=_h7_json_default) + "\n", encoding="utf-8")
        temporary.replace(target)
        return str(target)
    except OSError:
        return None


def _h7_write_incomplete_pair_summary(seed, generation, required_pair_count, pair_rows, reason, errors=None, invention_rejection_reason=None, invention_candidate_id=None):
    """Atomically persist an explicitly incomplete pair audit; never label it valid."""
    summary = {
        "schema": "ACSIE.h7.generation_pair_summary.incomplete.v1",
        "seed": int(seed),
        "generation": int(generation),
        "required_pair_count": int(required_pair_count),
        "observed_pair_count": len(pair_rows),
        "missing_pair_count": max(0, int(required_pair_count) - len(pair_rows)),
        "pair_rows": pair_rows,
        "audit_status": "INCOMPLETE",
        "incomplete_reason": str(reason),
        "errors": list(errors or []),
        "primary_invention_rejection_reason": invention_rejection_reason,
        "primary_invention_candidate_id": invention_candidate_id,
        "target_access_during_discovery": False,
        "promotion": "DO NOT PROMOTE",
    }
    output_dir = Path(os.environ.get("ACSIE_H7_PAIR_AUDIT_DIR", "h7-pair-audit-summaries"))
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"seed-{seed}-generation-{generation:02d}.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(summary, sort_keys=True, indent=2, default=_h7_json_default) + "\n", encoding="utf-8")
        temporary.replace(target)
        return str(target), summary
    except OSError as exc:
        summary["errors"].append("incomplete_pair_audit_write_error: " + str(exc))
        return None, summary


def _h7_unhandled_generation_exception(exc_type, exc_value, exc_traceback):
    context = dict(_H7_ACTIVE_GENERATION_CONTEXT)
    try:
        if context.get("seed") is not None and context.get("generation") is not None:
            seed = int(context["seed"])
            generation = int(context["generation"])
            required = int(context.get("required_pair_count", generation * (generation + 1) // 2))
            output_dir = Path(os.environ.get("ACSIE_H7_PAIR_AUDIT_DIR", "h7-pair-audit-summaries"))
            existing = output_dir / f"seed-{seed}-generation-{generation:02d}.json"
            complete_already_written = False
            try:
                prior = json.loads(existing.read_text(encoding="utf-8"))
                complete_already_written = (
                    prior.get("schema") == "ACSIE.h7.generation_pair_summary.v1"
                    and prior.get("required_pair_count") == required
                    and prior.get("observed_pair_count") == required
                )
            except Exception:
                pass
            if not complete_already_written:
                message = type(exc_value).__name__ + ": " + str(exc_value)
                _h7_write_incomplete_pair_summary(
                    seed, generation, required,
                    list(context.get("pair_rows") or []),
                    "unhandled_generation_exception",
                    errors=[message],
                    invention_rejection_reason=context.get("invention_rejection_reason"),
                    invention_candidate_id=context.get("invention_candidate_id"),
                )
            _h7_emit_event(
                "GENERATION_UNHANDLED_EXCEPTION", seed=seed, generation=generation,
                exception_type=exc_type.__name__, message=str(exc_value),
                complete_pair_audit_already_written=complete_already_written,
                promotion="DO NOT PROMOTE",
            )
    except BaseException:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


sys.excepthook = _h7_unhandled_generation_exception


def run_seed(
    seed: int,
    generations: int,
    *,
    checkpoint_path: str | None = None,
    resume_from: str | None = None,
    stop_after: int | None = None,
    checkpoint_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if generations <= 0:
        raise ValueError("generations must be positive")
    if stop_after is not None and not 0 < stop_after <= generations:
        raise ValueError("stop_after must be in the range 1..generations")
    if resume_from and checkpoint_path and resume_from != checkpoint_path:
        raise ValueError("resume_from and checkpoint_path must match when both are supplied")

    resumed = bool(resume_from)
    last_checkpoint_digest = None
    if resume_from:
        envelope = load_checkpoint(
            resume_from,
            expected_seed=seed,
            expected_metadata=checkpoint_metadata,
        )
        restored = restore_checkpoint(
            envelope,
            expected_metadata=checkpoint_metadata,
        )
        rng = restored["local_rng"]
        learner = restored["learner"]
        retained = list(restored["retained"])
        generations_out = list(restored["generations_out"])
        initial_depth = restored["initial_depth"]
        start_generation = restored["generation_next"]
        last_checkpoint_digest = restored["state_digest"]
        if start_generation > generations:
            raise ValueError(
                f"checkpoint resumes at generation {start_generation}, beyond requested {generations}"
            )
        print(
            json.dumps(
                {
                    "event": "SEED_RESUME",
                    "seed": seed,
                    "generations": generations,
                    "generation_next": start_generation,
                    "checkpoint_digest": last_checkpoint_digest,
                },
                sort_keys=True,
            ),
            flush=True,
        )
    else:
        rng = random.Random(seed)
        learner = OpenEndedRecursiveCognitiveCompiler(max_depth=2, population=24, seed=seed)
        retained = []
        generations_out = []
        initial_depth = learner.meta_policy["max_depth"]
        start_generation = 0
        print(
            json.dumps(
                {
                    "event": "SEED_START",
                    "seed": seed,
                    "generations": generations,
                },
                sort_keys=True,
            ),
            flush=True,
        )

    def hidden_library() -> dict[str, dict[str, Any]]:
        return {cap.hidden_id: cap.expression for cap in retained}

    def capability_macro(cap: HiddenCapability) -> dict[str, Any]:
        return {"op": "macro", "id": cap.hidden_id}

    for generation in range(start_generation, generations):
        _H7_ACTIVE_GENERATION_CONTEXT.clear()
        _H7_ACTIVE_GENERATION_CONTEXT.update({
            "seed": seed,
            "generation": generation,
            "required_pair_count": generation * (generation + 1) // 2,
            "pair_rows": [],
            "invention_candidate_id": None,
            "invention_rejection_reason": None,
        })
        generation_wall_started = time.perf_counter()
        learner.generation = generation
        generation_begin_metrics = _h7_runtime_metrics(learner)
        _h7_emit_event(
            "GENERATION_BEGIN",
            seed=seed,
            generation=generation,
            timestamp_monotonic_seconds=time.monotonic(),
            **generation_begin_metrics,
        )
        # Emit an audit entry before the expensive discovery/admission work so a
        # bounded timeout still leaves a durable trace even if no pair starts.
        _h7_emit_event(
            "AUDIT_BEGIN",
            seed=seed,
            generation=generation,
            phase="GENERATION_ENTRY_PRE_DISCOVERY",
            required_pair_count=generation * (generation + 1) // 2,
            planned_pair_count=None,
            audit_complete=False,
            **generation_begin_metrics,
        )
        hidden_macros = hidden_library()

        target_parents: tuple[HiddenCapability, ...]
        if not retained:
            target_parents = ()
            target = hard_bootstrap_expr(rng)
        elif len(retained) == 1:
            target_parents = (retained[0],)
            target = {
                "op": rng.choice(("add", "sub", "mul", "max", "min")),
                "left": capability_macro(retained[0]),
                "right": {"op": "get", "key": rng.choice(KEYS)},
            }
        else:
            target_parents = tuple(rng.sample(retained, 2))
            target = {
                "op": rng.choice(("add", "sub", "mul", "max", "min")),
                "left": capability_macro(target_parents[0]),
                "right": capability_macro(target_parents[1]),
            }

        target_depth = expanded_depth(target, hidden_macros)

        train = make_traces(
            target, seed, generation, "train", 12, 0.0, hidden_macros
        )
        selection = make_traces(
            target, seed, generation, "selection", 8, 0.17, hidden_macros
        )
        hold = make_traces(
            target, seed, generation, "holdout", 6, 0.31, hidden_macros
        )
        transfer = make_traces(
            target, seed, generation, "transfer", 8, -0.57, hidden_macros
        )
        ood = make_traces(
            target, seed, generation, "ood", 8, 0.93, hidden_macros
        )

        discovery_train = tuple(train) + tuple(selection)

        parent_audit_started = time.perf_counter()
        parent_audit_cache: dict = {}
        parent_audit_cache_stats: dict[str, int] = {}
        parent_audit_primitive_macros = learner._pmap()
        _h7_emit_event(
            "TARGET_PARENT_FIDELITY_AUDIT_BEGIN",
            seed=seed,
            generation=generation,
            target_parent_ids=[p.primitive_id for p in target_parents],
            parent_count=len(target_parents),
            train_row_count=len(train),
            cache_scope="single_generation_target_parent_audit",
            cache_key_schema="macro-map-identity+ast-node-identity+exact-input-signature",
        )
        parent_fidelity_audit = {}
        for parent in target_parents:
            parent_fidelity_audit[parent.primitive_id] = retained_representation_error(
                learner,
                parent,
                tuple(train),
                hidden_macros=hidden_macros,
                primitive_macros=parent_audit_primitive_macros,
                evaluation_cache=parent_audit_cache,
                evaluation_cache_stats=parent_audit_cache_stats,
            )
        print(
            json.dumps(
                {
                    "event": "TARGET_PARENT_FIDELITY_AUDIT",
                    "seed": seed,
                    "generation": generation,
                    "target_parent_ids": [p.primitive_id for p in target_parents],
                    "errors": parent_fidelity_audit,
                    "elapsed_seconds": round(time.perf_counter() - parent_audit_started, 6),
                    "memoized_node_cache_entries": len(parent_audit_cache),
                    "memoized_node_cache_stats": parent_audit_cache_stats,
                    "decisions_unchanged": True,
                },
                sort_keys=True,
            ),
            flush=True,
        )

        primitive_invention_started = time.perf_counter()
        _h7_emit_event(
            "PRIMARY_PRIMITIVE_INVENTION_BEGIN",
            seed=seed,
            generation=generation,
            discovery_row_count=len(discovery_train),
            train_row_count=len(train),
            selection_row_count=len(selection),
            primitive_inventory_count=len(learner.primitives),
            primary_chain_length=len(getattr(learner, "_h7_primary_macro_ids", ())),
            expression_cap=3000,
        )
        primitive = learner.invent_primitive(discovery_train, hold, transfer)
        invention_elapsed_seconds = round(time.perf_counter() - primitive_invention_started, 6)
        # This is the unvalidated, discovery-ranked invention candidate only.
        # Final accepted selection is logged after post-selection admission so a
        # single "selected" field cannot ambiguously name two different stages.
        discovery_ranked_invention_summary = dict(
            getattr(learner, "_h7_primitive_invention_summary", {}) or {}
        )
        discovery_ranked_candidate_id = (
            discovery_ranked_invention_summary.get("selected_primitive_id")
            or getattr(primitive, "primitive_id", None)
        )
        discovery_ranked_candidate_parent_details = canonical_parent_generation_details(
            learner.primitives,
            getattr(primitive, "parent_ids", ()) if primitive is not None else (),
        )
        _H7_ACTIVE_GENERATION_CONTEXT["invention_candidate_id"] = discovery_ranked_candidate_id
        accepted = False
        transfer_error = float("inf")
        ood_error = float("inf")
        parent_used = tuple()
        acceptance_reason = "NO_VALID_PRIMITIVE"
        novelty = 0.0
        resource_cost = 0
        frontier_admission = None
        frontier_validation = []
        primitive_candidate_count = len(getattr(learner, "last_primitive_candidate_frontier", ()))
        discovery_perfect_candidate_count = sum(
            1 for candidate in getattr(learner, "last_primitive_candidate_frontier", ())
            if float(candidate.train_error) <= 1e-9
        )

        expected_parent_ids = {p.primitive_id for p in target_parents}
        selected_primitive = primitive
        if primitive is not None:
            frontier = tuple(getattr(learner, "last_primitive_candidate_frontier", ()))
            if frontier:
                novelty = 1.0 / max(1, frontier[0].complexity)
                resource_cost = max(1, frontier[0].complexity)
                frontier_admission = learner.accept_primitive_frontier(
                    transfer_rows=transfer,
                    ood_rows=ood,
                    novelty=novelty,
                    resource_cost=resource_cost,
                )
                accepted = bool(frontier_admission.get("accepted", False))
                frontier_validation = list(frontier_admission.get("validation", []))
                admitted = frontier_admission.get("primary_primitive")
                if admitted is not None:
                    selected_primitive = admitted
                    transfer_error = float(admitted.transfer_error)
                    matching = next(
                        (
                            item for item in frontier_validation
                            if item["primitive_id"] == admitted.primitive_id
                        ),
                        None,
                    )
                    ood_error = (
                        float(matching["ood_error"])
                        if matching is not None
                        else float("inf")
                    )
                    novelty = 1.0 / max(1, admitted.complexity)
                    resource_cost = max(1, admitted.complexity)
                else:
                    transfer_error = float(frontier[0].transfer_error)
                    first_validation = frontier_validation[0] if frontier_validation else None
                    ood_error = (
                        float(first_validation["ood_error"])
                        if first_validation is not None
                        else float("inf")
                    )
                if accepted:
                    acceptance_reason = "ACCEPTED_FRONTIER"
                elif not frontier_validation:
                    acceptance_reason = "NO_VALID_PRIMITIVE"
                elif all(float(item["transfer_error"]) > 1e-9 for item in frontier_validation):
                    acceptance_reason = "TRANSFER_FAILURE"
                elif all(float(item["ood_error"]) > 1e-9 for item in frontier_validation):
                    acceptance_reason = "OOD_FAILURE"
                else:
                    acceptance_reason = "FRONTIER_ALL_REJECTED"
            else:
                acceptance_reason = "EMPTY_FRONTIER"
        _H7_ACTIVE_GENERATION_CONTEXT["invention_rejection_reason"] = None if accepted else acceptance_reason
        parent_used = selected_primitive.parent_ids if selected_primitive is not None else tuple()
        selected_parent_details = canonical_parent_generation_details(learner.primitives, parent_used)
        selected_primary_parent_ids = selected_parent_details["parent_ids"]
        selected_primary_parent_generations = selected_parent_details["parent_generations"]
        discovery_ranked_parent_ids = discovery_ranked_candidate_parent_details["parent_ids"]
        discovery_ranked_parent_generations = discovery_ranked_candidate_parent_details["parent_generations"]
        selected_primary_pair_recency_gate_passed = primary_pair_recency_gate(
            generation,
            selected_primary_parent_generations,
            selected_primary_parent_ids,
            list(getattr(learner, "_h7_primary_macro_ids", ())),
        )
        # Keep discovery-ranked proposal and post-validation selection separate,
        # while binding the legacy selected_* fields to the canonical accepted row.
        primary_invention_summary = dict(discovery_ranked_invention_summary)
        primary_invention_summary.update({
            "summary_stage": "DISCOVERY_PROPOSAL_PLUS_POST_VALIDATION_SELECTION",
            "discovery_ranked_candidate_id": discovery_ranked_candidate_id,
            "discovery_ranked_candidate_parent_ids": discovery_ranked_parent_ids,
            "discovery_ranked_candidate_parent_generations": discovery_ranked_parent_generations,
            "selected_primitive_id": getattr(selected_primitive, "primitive_id", None),
            "selected_direct_parent_ids": selected_primary_parent_ids,
            "selected_direct_parent_generations": selected_primary_parent_generations,
            "selected_pair_recency_gate_passed": bool(selected_primary_pair_recency_gate_passed),
            "acceptance_status": "ACCEPTED" if accepted else "REJECTED",
            "acceptance_rejection_reason": None if accepted else acceptance_reason,
        })
        _h7_emit_event(
            "PRIMARY_PRIMITIVE_INVENTION_COMPLETE",
            seed=seed,
            generation=generation,
            elapsed_seconds=invention_elapsed_seconds,
            primitive_found=primitive is not None,
            discovery_candidate_count=len(getattr(learner, "last_primitive_candidate_frontier", ())),
            discovery_ranked_candidate_id=discovery_ranked_candidate_id,
            discovery_ranked_candidate_parent_ids=discovery_ranked_parent_ids,
            discovery_ranked_candidate_parent_generations=discovery_ranked_parent_generations,
            selected_primitive_id=getattr(selected_primitive, "primitive_id", None),
            selected_direct_parent_ids=selected_primary_parent_ids,
            selected_direct_parent_generations=selected_primary_parent_generations,
            selected_pair_recency_gate_passed=bool(selected_primary_pair_recency_gate_passed),
            accepted=bool(accepted),
            acceptance_rejection_reason=None if accepted else acceptance_reason,
            expression_enumeration_summary=dict(getattr(learner, "_expr_enumeration_summary", {}) or {}),
            primary_invention_summary=primary_invention_summary,
        )
        if not accepted:
            _h7_emit_event(
                "PRIMARY_PRIMITIVE_INVENTION_REJECTED",
                seed=seed,
                generation=generation,
                primary_invention_rejection_reason=acceptance_reason,
                discovery_ranked_candidate_id=discovery_ranked_candidate_id,
                discovery_ranked_candidate_parent_ids=discovery_ranked_parent_ids,
                discovery_ranked_candidate_parent_generations=discovery_ranked_parent_generations,
                selected_primitive_id=getattr(selected_primitive, "primitive_id", None),
                selected_direct_parent_ids=selected_primary_parent_ids,
                selected_direct_parent_generations=selected_primary_parent_generations,
                frontier_validation=frontier_validation,
                candidate_count=primitive_candidate_count,
                expression_enumeration_summary=dict(getattr(learner, "_expr_enumeration_summary", {}) or {}),
                search_stats=compact_search_stats(dict(getattr(learner, "last_search_stats", {}) or {})),
                promotion="DO NOT PROMOTE",
            )
        candidate_lineage_ids = (
            executable_lineage_ids(learner, (selected_primitive.primitive_id,))
            if selected_primitive is not None and selected_primitive.primitive_id in learner.primitives
            else set()
        )
        recursive_reuse_ok = expected_parent_ids.issubset(candidate_lineage_ids) if selected_primitive is not None else False
        if accepted and selected_primitive is not None:
            hidden_id = f"hidden:{generation}:{len(retained)}"
            retained.append(
                HiddenCapability(
                    hidden_id=hidden_id,
                    primitive_id=selected_primitive.primitive_id,
                    expression=target,
                    depth=target_depth,
                    generation=generation,
                    parent_hidden_id=target_parents[0].hidden_id if target_parents else None,
                    parent_hidden_ids=tuple(p.hidden_id for p in target_parents),
                )
            )

        # Bootstrap provenance is explicit, ordered runtime state; preserve IDs
        # from the checkpoint metadata even when they are not members of the
        # accepted-primary chain. Generation zero is only used to add a primary
        # chain member to the bootstrap list, never to infer arbitrary inventory IDs.
        bootstrap_ids = list(learner._h7_explicit_bootstrap_macro_ids(tuple(learner.primitives)))
        for pid in getattr(learner, "_h7_primary_macro_ids", ()):
            pid = str(pid)
            if (
                pid in learner.primitives
                and int(getattr(learner.primitives.get(pid), "generation", -1)) == 0
                and pid not in bootstrap_ids
            ):
                bootstrap_ids.append(pid)
        learner.bootstrap_primitives = bootstrap_ids

        # Fresh direct-task control: it gets the same observations for this
        # generation but cannot carry prior archive state forward.
        baseline_direct = RecursiveCognitiveCompiler(
            max_depth=2, population=24, seed=seed + 10091 + generation
        )
        baseline_direct.generation = 0
        bprim = baseline_direct.invent_primitive(discovery_train, hold, transfer)
        baseline_accepted = False
        if bprim is not None:
            b_ood = mae(bprim.expression, ood, baseline_direct._pmap())
            baseline_accepted = (
                bprim.transfer_error <= 1e-9 and b_ood <= 1e-9
            )

        # Fresh non-recursive control for closure/probe tests. It has no
        # retained ACSIE capabilities and is reset independently each
        # generation, so longitudinal gains cannot come from baseline memory.
        baseline = RecursiveCognitiveCompiler(
            max_depth=2, population=24, seed=seed + 21091 + generation
        )

        closure_rates = []
        baseline_closure_rates = []
        closure_reuse_rates = []
        semantic_closure_reuse_rates = []
        closure_parent_fidelity = []
        closure_trap_count = 0
        closure_pair_outcomes = []
        _H7_ACTIVE_GENERATION_CONTEXT["pair_rows"] = closure_pair_outcomes
        required_pairs_this_generation = generation * (generation + 1) // 2
        closure_fidelity_started = time.perf_counter()
        closure_fidelity_cache: dict = {}
        closure_fidelity_cache_stats: dict[str, int] = {}
        closure_fidelity_primitive_macros = learner._pmap()
        closure_fidelity_hidden_macros = hidden_library()
        closure_parent_fidelity_checks = 0
        closure_parent_fidelity_rows = 0
        _h7_emit_event(
            "CLOSURE_PARENT_FIDELITY_AUDIT_BEGIN",
            seed=seed,
            generation=generation,
            planned_pair_count=len(retained) * max(0, len(retained) - 1) // 2,
            retained_count=len(retained),
            cache_scope="single_generation_all_closure_pairs",
            cache_key_schema="macro-map-identity+ast-node-identity+exact-input-signature",
        )
        if len(retained) >= 2:
            pairs = [
                (retained[i], retained[j])
                for i in range(len(retained))
                for j in range(i + 1, len(retained))
            ]
            _h7_emit_event(
                "CLOSURE_PAIR_EVALUATION_BEGIN",
                seed=seed,
                generation=generation,
                required_pair_count=required_pairs_this_generation,
                planned_pair_count=len(pairs),
                **_h7_runtime_metrics(learner),
            )
            for pair_idx, (left_parent, right_parent) in enumerate(pairs):
                closure_expr = {
                    "op": "add",
                    "left": capability_macro(left_parent),
                    "right": capability_macro(right_parent),
                }
                closure_macros = closure_fidelity_hidden_macros
                ctr = make_traces(closure_expr, seed + 1700 + pair_idx, generation, 'closure_train', 8, 0.13, closure_macros)
                parent_fidelities = {
                    left_parent.primitive_id: retained_representation_error(
                        learner, left_parent, tuple(ctr), hidden_macros=closure_macros,
                        primitive_macros=closure_fidelity_primitive_macros,
                        evaluation_cache=closure_fidelity_cache,
                        evaluation_cache_stats=closure_fidelity_cache_stats,
                    ),
                    right_parent.primitive_id: retained_representation_error(
                        learner, right_parent, tuple(ctr), hidden_macros=closure_macros,
                        primitive_macros=closure_fidelity_primitive_macros,
                        evaluation_cache=closure_fidelity_cache,
                        evaluation_cache_stats=closure_fidelity_cache_stats,
                    ),
                }
                cs = make_traces(closure_expr, seed + 1700 + pair_idx, generation, 'closure_selection', 6, 0.07, closure_macros)
                parent_selection_fidelities = {
                    left_parent.primitive_id: retained_representation_error(
                        learner, left_parent, tuple(cs), hidden_macros=closure_macros,
                        primitive_macros=closure_fidelity_primitive_macros,
                        evaluation_cache=closure_fidelity_cache,
                        evaluation_cache_stats=closure_fidelity_cache_stats,
                    ),
                    right_parent.primitive_id: retained_representation_error(
                        learner, right_parent, tuple(cs), hidden_macros=closure_macros,
                        primitive_macros=closure_fidelity_primitive_macros,
                        evaluation_cache=closure_fidelity_cache,
                        evaluation_cache_stats=closure_fidelity_cache_stats,
                    ),
                }
                closure_parent_fidelity_checks += 4
                closure_parent_fidelity_rows += 2 * (len(ctr) + len(cs))
                ch = make_traces(closure_expr, seed + 1700 + pair_idx, generation, 'closure_holdout', 5, 0.23, closure_macros)
                cv = make_traces(closure_expr, seed + 1700 + pair_idx, generation, 'closure_transfer', 5, -0.19, closure_macros)
                co = make_traces(closure_expr, seed + 1700 + pair_idx, generation, 'closure_ood', 5, 0.29, closure_macros)
                closure_discovery_rows = tuple(ctr) + tuple(cs)
                # Do not re-run an exhaustive generic expression enumeration here.
                # This block is diagnostic-only; the scientific closure gate below
                # performs the real discovery/selection search. The prior audit
                # duplicated that work for every retained pair and dominated wall time.
                if hasattr(learner, "synthesize_process_frontier"):
                    cprocs = tuple(
                        learner.synthesize_process_frontier(
                            closure_discovery_rows,
                            cv,
                            co,
                            max_candidates=32,
                        )
                    )
                else:
                    fallback = learner.synthesize_process(closure_discovery_rows, cv, co)
                    cprocs = (fallback,) if fallback is not None else ()

                expected = {left_parent.primitive_id, right_parent.primitive_id}
                search_stats_full = dict(getattr(learner, "last_search_stats", {}))
                lineage_signatures = tuple(
                    str(sig)
                    for sig in search_stats_full.get("target_candidate_lineage_signatures", ())
                )
                expected_signature_count = sum(
                    expected.issubset(set(sig.split("|")))
                    for sig in lineage_signatures
                )
                search_stats = compact_search_stats(search_stats_full)
                print(
                    json.dumps(
                        {
                            "event": "CLOSURE_CANDIDATE_AUDIT",
                            "seed": seed,
                            "generation": generation,
                            "expected_parent_ids": sorted(expected),
                            "audit": {
                                "expected_lineage_candidate_count": int(expected_signature_count),
                                "perfect_candidate_count": int(search_stats.get("target_candidate_count", 0)),
                                "selection_qualified_candidate_count": int(search_stats.get("target_candidate_count", 0)),
                                "expected_lineage_expressions": [],
                                "preselection_validation_used": False,
                                "source": "post_search_telemetry",
                            },
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )

                competence = False
                reuse_ok = False
                expected = {left_parent.primitive_id, right_parent.primitive_id}
                # Selection is fixed by the discovery-ranked frontier before any
                # holdout/transfer/OOD evaluation. Never select the first candidate
                # that happens to pass validation: that would turn validation into
                # candidate search and could label a non-lineage selection as reuse.
                selected_proc = select_discovery_ranked_candidate(cprocs)
                selected_candidate_lineage = set()
                selected_lineage_match = False
                frontier_lineage_matches = 0
                candidate_in_frontier = False
                lineage_compatible = False
                candidate_details = []
                for candidate_index, candidate_proc in enumerate(cprocs):
                    ceval = learner.evaluate(candidate_proc, ctr, ch, cv, co, ())
                    candidate_competence = bool(
                        ceval.accepted and ceval.ood_error <= 1e-9
                    )
                    candidate_lineage = executable_lineage_ids(
                        learner,
                        tuple(candidate_proc.used_primitives),
                    )
                    direct_pair_match = expected.issubset(set(str(pid) for pid in candidate_proc.used_primitives))
                    candidate_lineage_match = expected.issubset(candidate_lineage)
                    candidate_in_frontier = candidate_in_frontier or direct_pair_match
                    lineage_compatible = lineage_compatible or candidate_lineage_match
                    candidate_details.append({
                        "frontier_rank": candidate_index,
                        "process_id": getattr(candidate_proc, "process_id", None),
                        "expression": candidate_proc.expression,
                        "used_primitives": list(getattr(candidate_proc, "used_primitives", ())),
                        "executable_lineage_ids": sorted(candidate_lineage),
                        "candidate_in_frontier": bool(direct_pair_match),
                        "lineage_compatible": bool(candidate_lineage_match),
                        "competence_ok": bool(candidate_competence),
                        "reuse_ok": bool(candidate_competence and candidate_lineage_match),
                        "transfer_error": getattr(ceval, "transfer_error", None),
                        "ood_error": getattr(ceval, "ood_error", None),
                    })
                    if candidate_competence and candidate_lineage_match:
                        frontier_lineage_matches += 1
                    if candidate_proc is selected_proc:
                        competence = candidate_competence
                        selected_candidate_lineage = candidate_lineage
                        selected_lineage_match = candidate_lineage_match
                        reuse_ok = bool(candidate_competence and candidate_lineage_match)

                cproc = selected_proc
                competence, reuse_ok, closure_trap = selected_closure_reuse_gate(
                    competence, selected_candidate_lineage, expected
                )
                print(
                    json.dumps(
                        {
                            "event": "PROCESS_FRONTIER_CLOSURE_AUDIT",
                            "seed": seed,
                            "generation": generation,
                            "expected_parent_ids": sorted(expected),
                            "frontier_size": len(cprocs),
                            "frontier_lineage_matches": frontier_lineage_matches,
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
                # Explicit boolean telemetry even when cprocs/candidate_details are empty.
                pair_search_summary = dict(getattr(learner, "last_process_candidate_selection_summary", {}) or {})
                pair_key = "|".join(sorted(expected))
                archived_signatures = set(pair_search_summary.get("v22_2_pair_signature_archive_signatures", ()))
                returned_signatures = set(pair_search_summary.get("v22_2_frontier_direct_signatures", ()))
                dominance_pruned = bool(pair_key in archived_signatures and pair_key not in returned_signatures)
                merge_counts = dict(pair_search_summary.get("v22_2_pair_signature_merge_counts", {}) or {})
                canonicalization_merged = int(merge_counts.get(pair_key, 0) or 0) > 0
                expression_budget = dict(getattr(learner, "_expr_enumeration_summary", {}) or {})
                search_budget_exhausted = bool(
                    expected.issubset(set(str(pid) for pid in getattr(learner, "_h7_primary_macro_ids", ())))
                    and expression_budget.get("primary_pair_prefix_exceeds_limit", False)
                )
                if reuse_ok:
                    rejection_reasons = []
                elif search_budget_exhausted and not candidate_in_frontier:
                    rejection_reasons = ["search_budget_exhausted"]
                elif (
                    pair_key in set(pair_search_summary.get("primary_pair_add_generated_signatures", ()))
                    and pair_key in set(pair_search_summary.get("primary_pair_add_not_discovery_qualified_signatures", ()))
                ):
                    rejection_reasons = ["primary_pair_add_not_discovery_qualified"]
                elif not candidate_in_frontier:
                    rejection_reasons = ["candidate_missing"]
                elif not competence:
                    rejection_reasons = ["competence_failure"]
                elif closure_trap:
                    rejection_reasons = ["closure_trap"]
                elif not lineage_compatible:
                    rejection_reasons = ["lineage_break"]
                else:
                    rejection_reasons = ["lineage_break"]
                pair_outcome = {
                    "pair_index": pair_idx,
                    "macro_pair": [left_parent.primitive_id, right_parent.primitive_id],
                    "eligible": True,
                    "attempted": True,
                    "accepted": bool(reuse_ok),
                    "rejected": not bool(reuse_ok),
                    "skipped": False,
                    "rejection_reasons": rejection_reasons,
                    "candidate_details": candidate_details,
                    "selection_source": "first_discovery_ranked_frontier_candidate_v1",
                    "selected_process_id": getattr(cproc, "process_id", None) if cproc is not None else None,
                    "selected_expression": getattr(cproc, "expression", None) if cproc is not None else None,
                    "selected_used_primitives": list(getattr(cproc, "used_primitives", ())) if cproc is not None else [],
                    "selected_executable_lineage_ids": sorted(selected_candidate_lineage),
                    "selected_lineage_match": bool(selected_lineage_match),
                    "selected_primary_macro_ids": list(pair_search_summary.get("v22_3_selected_frontier_primary_macro_ids", ())),
                    "selected_pair_gens": list(pair_search_summary.get("v22_3_selected_frontier_pair_gens", ())),
                    "selected_pair_recency_gate_applicable": pair_search_summary.get("v22_3_selected_frontier_recency_gate_applicable"),
                    "selected_pair_recency_gate_passed": pair_search_summary.get("v22_3_selected_frontier_recency_gate_passed"),
                    "candidate_in_frontier": bool(candidate_in_frontier),
                    "frontier_lineage_matches": int(frontier_lineage_matches),
                    "direct_pair_generated": (
                        pair_key in set(pair_search_summary.get("primary_pair_add_generated_signatures", ()))
                    ),
                    "discovery_fit_passed": (
                        pair_key in set(pair_search_summary.get("primary_pair_add_discovery_qualified_signatures", ()))
                    ),
                    "primary_pair_add_expression_generated": (
                        pair_key in set(pair_search_summary.get("primary_pair_add_generated_signatures", ()))
                    ),
                    "primary_pair_add_discovery_qualified": (
                        pair_key in set(pair_search_summary.get("primary_pair_add_discovery_qualified_signatures", ()))
                    ),
                    "parent_fidelity_error": {
                        "closure_train": {
                            str(left_parent.primitive_id): float(parent_fidelities.get(left_parent.primitive_id, float("inf"))),
                            str(right_parent.primitive_id): float(parent_fidelities.get(right_parent.primitive_id, float("inf"))),
                        },
                        "closure_selection": {
                            str(left_parent.primitive_id): float(parent_selection_fidelities.get(left_parent.primitive_id, float("inf"))),
                            str(right_parent.primitive_id): float(parent_selection_fidelities.get(right_parent.primitive_id, float("inf"))),
                        },
                    },
                    "parent_fidelity_errors": {
                        str(left_parent.primitive_id): float(parent_fidelities.get(left_parent.primitive_id, float("inf"))),
                        str(right_parent.primitive_id): float(parent_fidelities.get(right_parent.primitive_id, float("inf"))),
                    },
                    "parent_fidelity_errors_selection": {
                        str(left_parent.primitive_id): float(parent_selection_fidelities.get(left_parent.primitive_id, float("inf"))),
                        str(right_parent.primitive_id): float(parent_selection_fidelities.get(right_parent.primitive_id, float("inf"))),
                    },
                    "dominance_pruned": bool(dominance_pruned),
                    "canonicalization_merged": bool(canonicalization_merged),
                    "lineage_compatible": bool(lineage_compatible),
                    "competence_ok": bool(competence),
                    "closure_trap": bool(closure_trap),
                    "reuse_ok": bool(reuse_ok),
                    "candidate_detail_count": len(candidate_details),
                    "search_budget_exhausted": bool(search_budget_exhausted),
                    "flag_observability": {
                        "candidate_in_frontier": "OBSERVED_FRONTIER_CANDIDATE_SIGNATURES",
                        "dominance_pruned": (
                            "OBSERVED_ARCHIVE_TO_FRONTIER_DROP"
                            if pair_key in archived_signatures
                            else "NOT_OBSERVED_BEFORE_PAIR_ARCHIVE"
                        ),
                        "canonicalization_merged": (
                            "OBSERVED_PER_DIRECT_SIGNATURE_REPRESENTATIVE_REDUCTION"
                            if pair_key in merge_counts
                            else "NO_EXACT_PAIR_SIGNATURE_COUNT_AVAILABLE"
                        ),
                        "lineage_compatible": "OBSERVED_EXECUTABLE_LINEAGE_FOR_RETURNED_CANDIDATES" if cprocs else "UNOBSERVED_EMPTY_FRONTIER",
                        "competence_ok": "OBSERVED_POST_SELECTION_EVALUATION" if cprocs else "UNOBSERVED_EMPTY_FRONTIER",
                        "closure_trap": "OBSERVED_DERIVED_GATE_OUTCOME",
                        "reuse_ok": "OBSERVED_DERIVED_GATE_OUTCOME" if cprocs else "UNOBSERVED_EMPTY_FRONTIER",
                    },
                    "search_budget_telemetry": expression_budget,
                }
                closure_pair_outcomes.append(pair_outcome)
                _h7_emit_event(
                    "H7_PAIR_OUTCOME",
                    seed=seed,
                    generation=generation,
                    **pair_outcome,
                )
                closure_rates.append(float(competence))
                closure_reuse_rates.append(float(reuse_ok))
                semantic_matches = semantic_parent_match_count(
                    learner,
                    (left_parent, right_parent),
                    tuple(cproc.used_primitives) if cproc is not None else tuple(),
                    tuple(ctr),
                    closure_macros,
                )
                semantic_closure_reuse_rates.append(
                    float(
                        semantic_matches == len((left_parent, right_parent))
                        and competence
                    )
                )
                closure_parent_fidelity.append(
                    statistics.fmean(parent_fidelities.values())
                )
                if competence and not reuse_ok:
                    print(
                        json.dumps(
                            {
                                "event": "CLOSURE_LINEAGE_MISMATCH",
                                "seed": seed,
                                "generation": generation,
                                "expected_parent_ids": sorted(expected),
                                "used_primitives": list(cproc.used_primitives) if cproc is not None else [],
                                "candidate_lineage": sorted(selected_candidate_lineage),
                                "selected_process_id": getattr(cproc, "process_id", None) if cproc is not None else None,
                                "expression": cproc.expression if cproc is not None else None,
                                "search_stats": compact_search_stats(dict(getattr(learner, "last_search_stats", {}))),
                                "target_candidate_frontier": list(
                                    getattr(learner, "last_search_stats", {}).get(
                                        "target_candidate_frontier", []
                                    )
                                ),
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
                    closure_trap_count += 1

                bproc = synthesize_discovery_only(baseline, tuple(ctr) + tuple(cs), cv)
                bcompetence = False
                if bproc is not None:
                    beval = baseline.evaluate(bproc, ctr, ch, cv, co, ())
                    bcompetence = bool(beval.accepted and beval.ood_error <= 1e-9)
                baseline_closure_rates.append(float(bcompetence))
        else:
            pairs = []
            _h7_emit_event(
                "CLOSURE_PAIR_EVALUATION_BEGIN",
                seed=seed,
                generation=generation,
                required_pair_count=required_pairs_this_generation,
                planned_pair_count=0,
                **_h7_runtime_metrics(learner),
            )

        _h7_emit_event(
            "CLOSURE_PARENT_FIDELITY_AUDIT_COMPLETE",
            seed=seed,
            generation=generation,
            elapsed_seconds=round(time.perf_counter() - closure_fidelity_started, 6),
            planned_pair_count=len(retained) * max(0, len(retained) - 1) // 2,
            observed_pair_count=len(closure_pair_outcomes),
            parent_fidelity_checks=closure_parent_fidelity_checks,
            parent_fidelity_rows=closure_parent_fidelity_rows,
            memoized_node_cache_entries=len(closure_fidelity_cache),
            memoized_node_cache_stats=closure_fidelity_cache_stats,
            decisions_unchanged=True,
        )

        # Build the strict schema only when the frozen all-pairs denominator and
        # the generation's primary-chain length are fully present. Partial rows are
        # still flushed individually and explicitly marked incomplete.
        pair_audit_status = "INCOMPLETE"
        pair_audit_sha256 = None
        pair_audit_path = None
        pair_audit_errors = []
        pair_summary = None
        complete_pair_denominator = (
            len(retained) == generation + 1
            and len(closure_pair_outcomes) == required_pairs_this_generation
        )
        if complete_pair_denominator:
            try:
                state_before_roundtrip = learner.export_state()
                serialized_state = json.loads(json.dumps(state_before_roundtrip, sort_keys=True, default=_h7_json_default))
                roundtripped_learner = RecursiveCognitiveCompiler.from_state(serialized_state)
                state_after_roundtrip = roundtripped_learner.export_state()
                pair_summary = build_generation_pair_summary(
                    generation,
                    closure_pair_outcomes,
                    primary_macro_ids=list(getattr(learner, "_h7_primary_macro_ids", ())),
                    bootstrap_primitives=list(getattr(learner, "bootstrap_primitives", ())),
                    checkpoint_before=state_before_roundtrip,
                    checkpoint_after=state_after_roundtrip,
                )
                pair_audit = audit_generation_pair_summary(pair_summary)
                pair_audit_status = str(pair_audit.get("audit_status", pair_audit.get("status", "VALIDATED")))
                pair_audit_sha256 = sha256(
                    json.dumps(pair_summary, sort_keys=True, separators=(",", ":"), default=_h7_json_default).encode("utf-8")
                ).hexdigest()
                pair_audit_path = _h7_write_pair_summary(seed, generation, pair_summary)
                if pair_audit_status not in ("CONSISTENT", "PASSED", "VALID", "VERIFIED", "OK"):
                    pair_audit_errors = list(pair_audit.get("errors", []))
            except Exception as exc:
                pair_audit_status = "INVALID"
                pair_audit_errors = [type(exc).__name__ + ": " + str(exc)]
                pair_audit_path, pair_summary = _h7_write_incomplete_pair_summary(
                    seed, generation, required_pairs_this_generation,
                    closure_pair_outcomes, "full_generation_pair_audit_exception",
                    errors=pair_audit_errors,
                    invention_rejection_reason=None if accepted else acceptance_reason,
                    invention_candidate_id=discovery_ranked_candidate_id,
                )
                pair_audit_sha256 = sha256(
                    json.dumps(pair_summary, sort_keys=True, separators=(",", ":"), default=_h7_json_default).encode("utf-8")
                ).hexdigest()
        else:
            incomplete_errors = [
                f"required_pair_count={required_pairs_this_generation}",
                f"observed_pair_count={len(closure_pair_outcomes)}",
                f"retained_count={len(retained)}",
                f"expected_primary_chain_length={generation + 1}",
            ]
            if not accepted:
                incomplete_errors.append("primary_invention_rejection_reason=" + str(acceptance_reason))
            pair_audit_status = "INCOMPLETE"
            pair_audit_errors = list(incomplete_errors)
            pair_audit_path, pair_summary = _h7_write_incomplete_pair_summary(
                seed, generation, required_pairs_this_generation,
                closure_pair_outcomes, "frozen_all_pairs_denominator_not_reached",
                errors=incomplete_errors,
                invention_rejection_reason=None if accepted else acceptance_reason,
                invention_candidate_id=discovery_ranked_candidate_id,
            )
            pair_audit_sha256 = sha256(
                json.dumps(pair_summary, sort_keys=True, separators=(",", ":"), default=_h7_json_default).encode("utf-8")
            ).hexdigest()
        _h7_emit_event(
            "AUDIT_END",
            seed=seed,
            generation=generation,
            phase="CLOSURE_PAIR_EVALUATION",
            required_pair_count=required_pairs_this_generation,
            observed_pair_count=len(closure_pair_outcomes),
            missing_pair_count=max(0, required_pairs_this_generation - len(closure_pair_outcomes)),
            closure_pair_audit_status=pair_audit_status,
            closure_pair_summary_sha256=pair_audit_sha256,
            closure_pair_summary_path=pair_audit_path,
            errors=pair_audit_errors,
            **_h7_runtime_metrics(learner),
        )
        if pair_summary is not None and pair_summary.get("schema") == "ACSIE.h7.generation_pair_summary.v1":
            _h7_emit_event(
                "H7_GENERATION_PAIR_SUMMARY",
                seed=seed,
                generation=generation,
                schema=pair_summary.get("schema"),
                required_pair_count=pair_summary.get("required_pair_count"),
                observed_pair_count=pair_summary.get("observed_pair_count"),
                accepted_pair_count=pair_summary.get("accepted_pair_count"),
                rejected_pair_count=pair_summary.get("rejected_pair_count"),
                first_failing_pair=pair_summary.get("first_failing_pair"),
                checkpoint_fidelity=pair_summary.get("checkpoint_fidelity"),
                audit_status=pair_audit_status,
                summary_sha256=pair_audit_sha256,
                summary_path=pair_audit_path,
            )

        probe_rates = []
        baseline_probe_rates = []
        probe_reuse_rates = []
        semantic_probe_reuse_rates = []
        probe_parent_fidelity = []
        probe_trap_count = 0
        probe_diagnostics = []
        for probe_idx in range(4):
            probe_parents = tuple(rng.sample(retained, 2)) if len(retained) >= 2 else tuple(retained[:1])
            probe_macros = hidden_library()
            if probe_parents:
                if len(probe_parents) == 1:
                    probe = {'op': 'add', 'left': capability_macro(probe_parents[0]), 'right': {'op': 'get', 'key': KEYS[probe_idx % len(KEYS)]}}
                else:
                    probe = {'op': 'add', 'left': capability_macro(probe_parents[0]), 'right': capability_macro(probe_parents[1])}
            else:
                probe = random_base_expr(random.Random(seed * 193 + generation * 17 + probe_idx), 3)

            ptrain = make_traces(probe, seed + 700 + probe_idx, generation, 'probe_train', 8, 0.17, probe_macros)
            pselection = make_traces(probe, seed + 700 + probe_idx, generation, 'probe_selection', 6, 0.05, probe_macros)
            pholdout = make_traces(probe, seed + 700 + probe_idx, generation, 'probe_holdout', 5, 0.27, probe_macros)
            ptransfer = make_traces(probe, seed + 700 + probe_idx, generation, 'probe_transfer', 5, -0.22, probe_macros)
            pood = make_traces(probe, seed + 700 + probe_idx, generation, 'probe_ood', 5, 0.41, probe_macros)
            proc = learner.synthesize_process(tuple(ptrain) + tuple(pselection), ptransfer, pood)
            print(
                json.dumps(
                    {
                        "event": "PRIMARY_PROCESS_OOD_CANDIDATE_AUDIT",
                        "seed": seed,
                        "generation": generation,
                        "candidate_selection_summary": getattr(
                            learner,
                            "last_process_candidate_selection_summary",
                            {},
                        ),
                        "selection_source": "discovery_and_selection_only",
                        "selected_process_id": getattr(proc, "process_id", None),
                        "selected_process_used_primitives": (
                            list(getattr(proc, "used_primitives", ())) if proc is not None else []
                        ),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            competence = False
            reuse_ok = False
            expected = {p.primitive_id for p in probe_parents}
            used_primitives = list(proc.used_primitives) if proc is not None else []
            candidate_lineage = set()
            if proc is not None:
                peval = learner.evaluate(proc, ptrain, pholdout, ptransfer, pood, ())
                competence = bool(peval.accepted and peval.ood_error <= 1e-9)
                candidate_lineage = executable_lineage_ids(
                    learner,
                    tuple(proc.used_primitives),
                )
                reuse_ok = competence and (
                    not expected or expected.issubset(candidate_lineage)
                )
            # Observation only: record all probe attempts, including failures for which
            # the original mismatch event was silent because competence was false.
            probe_diag = {
                "probe_index": probe_idx,
                "expected_parent_ids": sorted(expected),
                "used_primitives": used_primitives,
                "candidate_executable_lineage": sorted(candidate_lineage),
                "competence": bool(competence),
                "reuse_ok": bool(reuse_ok),
                "missing_expected_direct": sorted(expected - set(used_primitives)),
                "missing_expected_executable_lineage": sorted(expected - set(candidate_lineage)),
                "search_stats": {
                    key: (getattr(learner, "last_search_stats", {}) or {}).get(key)
                    for key in (
                        "selected_executable_lineage_ids",
                        "target_alternatives_pre_cap_count",
                        "target_alternatives_pre_cap_signature_count",
                        "target_alternatives_post_cap_count",
                        "target_alternatives_post_cap_signature_count",
                        "passive_alias_archive_cap",
                        "passive_alias_archive_max",
                        "congruence_variants_registered",
                        "congruence_child_contexts_with_aliases",
                        "congruence_child_archive_direct_macro_ids",
                        "congruence_child_archive_lineage_macro_ids",
                        "congruence_root_archive_direct_macro_ids",
                        "congruence_root_archive_lineage_macro_ids",
                    )
                },
            }
            probe_diagnostics.append(probe_diag)
            print(json.dumps({
                "event": "H7_PROBE_DIAGNOSTIC",
                "seed": seed,
                "generation": generation,
                **probe_diag,
            }, sort_keys=True), flush=True)
            probe_rates.append(float(competence))
            probe_reuse_rates.append(float(reuse_ok))
            semantic_probe_matches = semantic_parent_match_count(
                learner,
                probe_parents,
                tuple(proc.used_primitives) if proc is not None else tuple(),
                tuple(ptrain),
                probe_macros,
            )
            semantic_probe_reuse_rates.append(
                float(
                    competence
                    and (
                        not probe_parents
                        or semantic_probe_matches == len(probe_parents)
                    )
                )
            )
            if probe_parents:
                probe_parent_fidelity.append(
                    statistics.fmean(
                        retained_representation_error(
                            learner, p, tuple(ptrain), hidden_macros=probe_macros
                        )
                        for p in probe_parents
                    )
                )
            if competence and not reuse_ok and probe_parents:
                print(
                    json.dumps(
                        {
                            "event": "PROBE_LINEAGE_MISMATCH",
                            "seed": seed,
                            "generation": generation,
                            "expected_parent_ids": sorted(expected),
                            "used_primitives": list(proc.used_primitives) if proc is not None else [],
                            "candidate_lineage": sorted(candidate_lineage),
                            "expression": proc.expression if proc is not None else None,
                            # Diagnostic-only archive/readout evidence for the failed probe.
                            # These IDs are telemetry only; they never affect discovery or selection.
                            "probe_search_stats": {
                                key: (getattr(learner, "last_search_stats", {}) or {}).get(key)
                                for key in (
                                    "selected_executable_lineage_ids",
                                    "target_alternatives_pre_cap_count",
                                    "target_alternatives_pre_cap_signature_count",
                                    "target_alternatives_post_cap_count",
                                    "target_alternatives_post_cap_signature_count",
                                    "congruence_variants_registered",
                                    "congruence_child_contexts_with_aliases",
                                    "congruence_child_archive_direct_macro_ids",
                                    "congruence_child_archive_lineage_macro_ids",
                                    "congruence_root_archive_direct_macro_ids",
                                    "congruence_root_archive_lineage_macro_ids",
                                )
                            },
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
                probe_trap_count += 1

            bproc = synthesize_discovery_only(baseline, ptrain, ptransfer)
            bcompetence = False
            if bproc is not None:
                beval = baseline.evaluate(bproc, ptrain, pholdout, ptransfer, pood, ())
                bcompetence = bool(beval.accepted and beval.ood_error <= 1e-9)
            baseline_probe_rates.append(float(bcompetence))
        previous_runtime_depth = (
            initial_depth
            if not generations_out
            else generations_out[-1]["runtime_max_depth"]
        )
        selected_pair_gens_detail = [
            {
                "pair_index": outcome.get("pair_index"),
                "selected_primary_macro_ids": outcome.get("selected_primary_macro_ids", []),
                "pair_gens": outcome.get("selected_pair_gens", []),
                "recency_gate_passed": outcome.get("selected_pair_recency_gate_passed"),
            }
            for outcome in closure_pair_outcomes
            if outcome.get("selected_pair_recency_gate_applicable") is True
        ]
        generations_out.append(
            {
                "generation": generation,
                "selected_pair_gens": selected_pair_gens_detail,
                "primary_pair_recency_gate_checks": len(selected_pair_gens_detail),
                "primary_pair_recency_gate_failures": sum(
                    1 for item in selected_pair_gens_detail
                    if item.get("recency_gate_passed") is not True
                ),
                "generation_wall_seconds": round(time.perf_counter() - generation_wall_started, 6),
                "target_depth": target_depth,
                "target_digest": sha256(json.dumps(target, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
                "accepted": accepted,
                "baseline_accepted": baseline_accepted,
                "parent_used": bool(recursive_reuse_ok),
                "parent_ids": list(parent_used),
                "expected_parent_ids": sorted(expected_parent_ids),
                "primary_target_parent_ids": [p.primitive_id for p in target_parents],
                "primary_target_parent_generations": [
                    int(getattr(learner.primitives.get(p.primitive_id), "generation", -1))
                    if learner.primitives.get(p.primitive_id) is not None else -1
                    for p in target_parents
                ],
                "selected_primary_parent_ids": selected_primary_parent_ids,
                "selected_primary_parent_generations": selected_primary_parent_generations,
                "primary_pair_recency_gate_applicable": generation in (9, 10, 11),
                "selected_primary_parent_ids_in_primary_chain": (
                    set(selected_primary_parent_ids).issubset(set(map(str, getattr(learner, "_h7_primary_macro_ids", ()))))
                    and len(selected_primary_parent_ids) == 2
                ),
                "primary_pair_recency_gate_passed": selected_primary_pair_recency_gate_passed,
                "recursive_reuse_ok": bool(recursive_reuse_ok),
                "multi_parent_used": len(target_parents) >= 2 and recursive_reuse_ok,
                "closure_success_rate": statistics.fmean(closure_rates) if closure_rates else 0.0,
                "baseline_closure_success_rate": statistics.fmean(baseline_closure_rates) if baseline_closure_rates else 0.0,
                "closure_reuse_rate": statistics.fmean(closure_reuse_rates) if closure_reuse_rates else 0.0,
                "semantic_closure_reuse_rate": statistics.fmean(semantic_closure_reuse_rates) if semantic_closure_reuse_rates else 0.0,
                "closure_pair_count": len(closure_rates),
                "closure_pair_audit_status": pair_audit_status,
                "closure_pair_summary_sha256": pair_audit_sha256,
                "closure_pair_summary_path": pair_audit_path,
                "closure_success_count": int(sum(closure_rates)),
                "closure_reuse_success_count": int(sum(closure_reuse_rates)),
                "closure_trap_count": int(closure_trap_count),
                "baseline_closure_success_count": int(sum(baseline_closure_rates)),
                "retained_count": len(retained),
                "runtime_max_depth": int(learner.meta_policy["max_depth"]),
                "growth_delta": int(learner.meta_policy["max_depth"]) - int(previous_runtime_depth),
                "transfer_error": transfer_error,
                "ood_error": ood_error,
                "acceptance_reason": acceptance_reason,
                "primitive_found": primitive is not None,
                "primitive_id": primitive.primitive_id if primitive is not None else None,
                "primitive_candidate_count": primitive_candidate_count,
                "discovery_perfect_candidate_count": discovery_perfect_candidate_count,
                "selection_candidate_count": primitive_candidate_count,
                "frontier_validated_candidate_count": (
                    int(frontier_admission.get("validated_candidate_count", 0))
                    if frontier_admission is not None
                    else 0
                ),
                "selected_candidate": selected_primitive.primitive_id if selected_primitive is not None else None,
                "novelty": novelty,
                "resource_cost": resource_cost,
                "lineage_ok": bool(recursive_reuse_ok),
                "probe_success_rate": statistics.fmean(probe_rates),
                "baseline_probe_success_rate": statistics.fmean(baseline_probe_rates),
                "probe_reuse_rate": statistics.fmean(probe_reuse_rates),
                "semantic_probe_reuse_rate": statistics.fmean(semantic_probe_reuse_rates) if semantic_probe_reuse_rates else 0.0,
                "probe_parent_fidelity": (
                    statistics.fmean(probe_parent_fidelity)
                    if probe_parent_fidelity else 0.0
                ),
                "closure_parent_fidelity": (
                    statistics.fmean(closure_parent_fidelity)
                    if closure_parent_fidelity else 0.0
                ),
                "probe_trap_count": int(probe_trap_count),
                "probe_diagnostics": probe_diagnostics,
                "selection_rows": len(discovery_train),
                "holdout_used_for_selection": False,
                "transfer_used_for_selection": False,
                "ood_used_for_selection": False,
                "search_stats": compact_search_stats(dict(learner.last_search_stats)),
            }
        )
        print(
            json.dumps(
                {
                    "event": "GENERATION_PROGRESS",
                    "seed": seed,
                    "generation": generation,
                    "accepted": bool(accepted),
                    "retained_count": len(retained),
                    "runtime_max_depth": int(learner.meta_policy["max_depth"]),
                    "closure_success_rate": generations_out[-1]["closure_success_rate"],
                    "closure_reuse_rate": generations_out[-1]["closure_reuse_rate"],
                    "probe_success_rate": generations_out[-1]["probe_success_rate"],
                    "probe_reuse_rate": generations_out[-1]["probe_reuse_rate"],
                    "acceptance_reason": generations_out[-1]["acceptance_reason"],
                    "primitive_found": generations_out[-1]["primitive_found"],
                    "primitive_id": generations_out[-1]["primitive_id"],
                    "candidate_count": generations_out[-1]["primitive_candidate_count"],
                    "discovery_perfect_candidate_count": generations_out[-1]["discovery_perfect_candidate_count"],
                    "selection_candidate_count": generations_out[-1]["selection_candidate_count"],
                    "frontier_validated_candidate_count": generations_out[-1]["frontier_validated_candidate_count"],
                    "selected_candidate": generations_out[-1]["selected_candidate"],
                    "transfer_error": generations_out[-1]["transfer_error"],
                    "ood_error": generations_out[-1]["ood_error"],
                    "novelty": generations_out[-1]["novelty"],
                    "resource_cost": generations_out[-1]["resource_cost"],
                    "lineage_ok": generations_out[-1]["lineage_ok"],
                    "target_depth": target_depth,
                    "search_stats": compact_search_stats(dict(learner.last_search_stats)),
                },
                sort_keys=True,
            ),
            flush=True,
        )

        _H7_ACTIVE_GENERATION_CONTEXT.clear()
        if checkpoint_path:
            last_checkpoint_digest = save_checkpoint(
                checkpoint_path,
                seed=seed,
                generation_next=generation + 1,
                initial_depth=initial_depth,
                local_rng=rng,
                learner=learner,
                retained=[asdict(cap) for cap in retained],
                generations_out=generations_out,
                metadata=checkpoint_metadata,
            )
            print(
                json.dumps(
                    {
                        "event": "CHECKPOINT_SAVED",
                        "seed": seed,
                        "generation_completed": generation,
                        "generation_next": generation + 1,
                        "checkpoint_path": checkpoint_path,
                        "checkpoint_digest": last_checkpoint_digest,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

        if stop_after is not None and generation + 1 >= stop_after and generation + 1 < generations:
            print(
                json.dumps(
                    {
                        "event": "SEGMENT_STOP",
                        "seed": seed,
                        "generation_next": generation + 1,
                        "reason": "REQUESTED_CHECKPOINT_BOUNDARY",
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            break

    probe_gain = statistics.fmean(
        row["probe_success_rate"] - row["baseline_probe_success_rate"]
        for row in generations_out
    )
    final = generations_out[-1]
    accepted_after_bootstrap = sum(row["accepted"] for row in generations_out[1:])
    recursive_generations = sum(
        row["recursive_reuse_ok"] for row in generations_out[1:]
    )
    multi_parent_generations = sum(
        row["multi_parent_used"] for row in generations_out[1:]
    )
    last_three = generations_out[-3:]
    final_closure_gain = (
        final["closure_success_rate"] - final["baseline_closure_success_rate"]
    )
    final_closure_reuse_rate = final["closure_reuse_rate"]
    final_probe_reuse_rate = final["probe_reuse_rate"]
    early = generations_out[min(2, len(generations_out) - 1)]
    closure_growth = (
        final["closure_reuse_success_count"] - early["closure_reuse_success_count"]
    )
    closure_capacity_ok = (
        final["closure_pair_count"] > 0
        and final["closure_reuse_rate"] >= 0.75
        and final["closure_reuse_success_count"] > 0
    )
    trap_free_ok = (
        all(row["closure_trap_count"] == 0 for row in generations_out)
        and all(row["probe_trap_count"] == 0 for row in generations_out)
    )

    applicable_generations = generations_out[1:] if len(generations_out) > 1 else []
    every_generation_accepted = bool(generations_out) and all(
        row["accepted"] for row in generations_out
    )
    every_closure_perfect = all(
        row["closure_pair_count"] == 0
        or (
            row["closure_success_rate"] == 1.0
            and row["closure_reuse_rate"] == 1.0
            and row["closure_trap_count"] == 0
        )
        for row in generations_out
    )
    every_probe_perfect = all(
        row["probe_success_rate"] == 1.0
        and row["probe_reuse_rate"] == 1.0
        and row["probe_trap_count"] == 0
        for row in generations_out
    )
    lineage_closed = all(row["parent_used"] for row in applicable_generations)
    strict_growth = all(row["growth_delta"] > 0 for row in applicable_generations)
    depth_growth_contract = (
        final["runtime_max_depth"] >= initial_depth + generations
        and final["runtime_max_depth"] > max(
            row["runtime_max_depth"] for row in generations_out[:-1]
        )
    )

    finite_gate = (
        len(generations_out) == generations
        and every_generation_accepted
        and lineage_closed
        and every_closure_perfect
        and every_probe_perfect
        and all(
            row.get("primary_pair_recency_gate_passed") is True
            for row in generations_out
            if int(row.get("generation", -1)) in (9, 10, 11)
        )
        and strict_growth
        and depth_growth_contract
        and final["retained_count"] >= generations
        and final["target_depth"] > generations_out[0]["target_depth"]
        and final["probe_success_rate"] == 1.0
        and final["probe_reuse_rate"] == 1.0
        and final["closure_pair_count"] >= 6
        and final["closure_success_rate"] == 1.0
        and final["closure_reuse_rate"] == 1.0
        and trap_free_ok
        and final["baseline_accepted"] is False
    )
    return {
        "seed": seed,
        "generations": generations,
        "initial_depth": initial_depth,
        "final_runtime_max_depth": final["runtime_max_depth"],
        "final_target_depth": final["target_depth"],
        "retained_count": final["retained_count"],
        "accepted_after_bootstrap": accepted_after_bootstrap,
        "recursive_generations": recursive_generations,
        "multi_parent_generations": multi_parent_generations,
        "final_closure_success_rate": final["closure_success_rate"],
        "final_baseline_closure_success_rate": final["baseline_closure_success_rate"],
        "final_closure_success_count": final["closure_success_count"],
        "final_baseline_closure_success_count": final["baseline_closure_success_count"],
        "final_closure_gain": final_closure_gain,
        "closure_growth": closure_growth,
        "closure_capacity_ok": closure_capacity_ok,
        "every_generation_accepted": every_generation_accepted,
        "every_closure_perfect": every_closure_perfect,
        "every_probe_perfect": every_probe_perfect,
        "primary_pair_recency_gate_applicable_generations": [
            row for row in generations_out
            if int(row.get("generation", -1)) in (9, 10, 11)
        ],
        "primary_pair_recency_gate_checks": sum(
            1 for row in generations_out
            if int(row.get("generation", -1)) in (9, 10, 11)
        ),
        "primary_pair_recency_gate_failures": sum(
            1 for row in generations_out
            if int(row.get("generation", -1)) in (9, 10, 11)
            and row.get("primary_pair_recency_gate_passed") is not True
        ),
        "lineage_closed": lineage_closed,
        "strict_growth": strict_growth,
        "depth_growth_contract": depth_growth_contract,
        "mean_probe_gain": probe_gain,
        "final_probe_success_rate": final["probe_success_rate"],
        "final_baseline_probe_success_rate": final["baseline_probe_success_rate"],
        "finite_open_ended_growth_gate": finite_gate,
        "external_model": False,
        "target_identity_available_to_runtime": False,
        "task_family_route": False,
        "selection_split_used": True,
        "holdout_used_for_search_selection": False,
        "transfer_used_for_search_selection": False,
        "ood_used_for_search_selection": False,
        "closure_trap_count": int(final["closure_trap_count"]),
        "probe_trap_count": int(final["probe_trap_count"]),
        "final_closure_reuse_rate": final_closure_reuse_rate,
        "final_probe_reuse_rate": final_probe_reuse_rate,
        "final_closure_parent_fidelity": final["closure_parent_fidelity"],
        "final_probe_parent_fidelity": final["probe_parent_fidelity"],
        "reuse_lineage_semantics": "external_executable_macro_reachability_v1",
        "final_semantic_closure_reuse_rate": final["semantic_closure_reuse_rate"],
        "final_semantic_probe_reuse_rate": final["semantic_probe_reuse_rate"],
        "max_generated_expressions": max(
            int(row["search_stats"].get("generated_expressions", 0))
            for row in generations_out
        ),
        "max_unique_search_states": max(
            int(row["search_stats"].get("unique_states", 0))
            for row in generations_out
        ),
        "max_search_states_in_depth": max(
            int(row["search_stats"].get("max_states_in_depth", 0))
            for row in generations_out
        ),
        "generations_detail": generations_out,
        "completed_generations": len(generations_out),
        "resumed_from_checkpoint": resumed,
        "checkpoint_path": checkpoint_path,
        "last_checkpoint_digest": last_checkpoint_digest,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seeds",
        default="2026100301,2026100302,2026100303,2026100304,2026100305",
    )
    parser.add_argument("--generations", type=int, default=12)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    rows = [
        run_seed(int(s), args.generations)
        for s in args.seeds.split(",")
        if s.strip()
    ]
    for row in rows:
        print(json.dumps(row, sort_keys=True))

    gate = (
        len(rows) == 5
        and all(row["finite_open_ended_growth_gate"] for row in rows)
        and all(not row["external_model"] for row in rows)
        and all(not row["target_identity_available_to_runtime"] for row in rows)
        and all(not row["task_family_route"] for row in rows)
    )
    print("OPEN_ENDED_SELF_EXTENDING_GATE=" + ("PASS" if gate else "FAIL"))
    raise SystemExit(0 if (gate or not args.strict) else 2)


if __name__ == "__main__":
    main()

# execution marker: PR-head condition corrected

# execution marker: ubuntu-slim runner route

# execution marker: complete lazy ACSIE stream pinned

# execution marker: fresh exact-SHA PR sync

# execution marker: fixed-baseline scientific run
# execution marker: workflow-resilience rerun

# execution marker: bootstrap-language and primitive-ID fixes

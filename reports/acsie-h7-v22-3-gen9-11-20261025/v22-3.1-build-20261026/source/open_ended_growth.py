from __future__ import annotations

"""Generic self-extending recursive capability search.

This layer does not define named capabilities or map task identities to
procedures. It only lets empirically retained executable artifacts expand the
future search language, with depth/resources adapted from observed transfer
evidence.

Literal unboundedness cannot be proven by a finite run; the runtime therefore
has no fixed depth ceiling and the evaluator measures sustained growth under
finite resource horizons.
"""

import copy
import json
from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

from .behavioral_search import find_exact_expression
from .recursive_cognitive_compiler import (
    ArchiveRecord,
    CognitivePrimitive,
    Evaluation,
    ProcessCandidate,
    RecursiveCognitiveCompiler,
    ast_depth,
    ast_nodes,
    digest,
    eval_expr,
)


def canonical_parent_generation_details(primitives, parent_ids):
    """Return canonical parent IDs/generations from one runtime primitive map.

    Sort and deduplicate IDs before deriving generations so invention events and
    accepted generation rows use the same provenance extraction.
    """
    ids = sorted({str(pid) for pid in (parent_ids or ()) if pid is not None})
    details = []
    for pid in ids:
        primitive = primitives.get(pid) if hasattr(primitives, "get") else None
        try:
            generation = int(getattr(primitive, "generation", -1)) if primitive is not None else -1
        except (TypeError, ValueError):
            generation = -1
        details.append({"parent_id": pid, "generation": generation})
    return {
        "parent_ids": ids,
        "parent_generations": [item["generation"] for item in details],
        "parent_details": details,
    }


def _h7_pair_signature_preserving_specs(
    specs,
    non_pair_cap: int = 8,
    *,
    pair_recency_priority=None,
    max_pair_depth: int = 4,
):
    """Keep shallow pairs and gate-passing deeper pairs before the auxiliary cap.

    The extra depth is eligible only when the caller supplies the frozen
    primary-pair recency predicate and it returns zero. All other alternatives
    retain the established bounded-tail behavior.
    """
    pair_representatives = {}
    other_specs = []
    for index, item in enumerate(specs):
        expression, used = item
        signature = tuple(sorted(set(str(pid) for pid in used)))
        expression_depth = int(ast_depth(expression))
        shallow_pair = expression_depth <= 2 and len(signature) == 2
        recency_pair = (
            expression_depth <= int(max_pair_depth)
            and len(signature) == 2
            and pair_recency_priority is not None
            and pair_recency_priority(expression) == 0
        )
        if shallow_pair or recency_pair:
            key = (
                expression_depth,
                ast_nodes(expression),
                json.dumps(expression, sort_keys=True, separators=(",", ":")),
            )
            old = pair_representatives.get(signature)
            if old is None or key < old[0]:
                pair_representatives[signature] = (key, index, item)
        else:
            other_specs.append((index, item, signature))

    ordered_pairs = [
        value[2] for value in sorted(
            pair_representatives.values(), key=lambda value: value[1]
        )
    ]
    pair_signatures = set(pair_representatives)
    extras = []
    for _, item, signature in other_specs:
        if signature in pair_signatures:
            continue
        # Do not collapse ordinary alternatives by direct vocabulary alone:
        # the legacy frontier intentionally permits same-vocabulary semantic
        # aliases (including the empty-vocabulary bootstrap version space).
        extras.append(item)
        if len(extras) >= max(0, int(non_pair_cap)):
            break
    return ordered_pairs + extras


@dataclass(frozen=True)
class GrowthEvidence:
    accepted: bool
    transfer_error: float
    ood_error: float
    novelty: float
    resource_cost: float
    growth_credit: float
    resulting_max_depth: int
    retained_capability_count: int


class OpenEndedRecursiveCognitiveCompiler(RecursiveCognitiveCompiler):
    """Recursive compiler with self-extending search depth and archive credit.

    The controller is deliberately generic:
    - no task family names are consumed;
    - no target capability labels are consumed;
    - retained executable primitives are the only new search vocabulary;
    - search depth is a mutable resource, not a fixed maximum.
    """

    SCHEMA = "ACSIE.open-ended-recursive-compiler.v1"
    PROCESS_HISTORY_LIMIT = 128

    def __init__(self, max_depth: int = 2, population: int = 24, seed: int = 0):
        super().__init__(max_depth=max_depth, population=population, seed=seed)
        self.growth_credit = 0.0
        self.max_observed_depth = int(max_depth)
        self.growth_history: list[GrowthEvidence] = []
        self.last_search_stats: dict[str, object] = {}
        self.last_primitive_candidate_frontier: tuple[CognitivePrimitive, ...] = ()
        self.last_process_candidate_frontier: tuple[ProcessCandidate, ...] = ()
        self.last_process_validation_summary: dict[str, object] = {}
        self._h7_primary_macro_ids: list[str] = []

    def _h7_macro_coverage_inventory(self) -> frozenset[str]:
        """Return accepted primary inventions plus executable macro ancestors.

        Alternative candidates remain searchable, but they do not each expand
        the active beam. This keeps the per-macro guarantee tied to the actual
        recursive capability chain the learner has retained.
        """
        inventory: set[str] = set()
        pending = list(self._h7_primary_macro_ids)
        while pending:
            pid = str(pending.pop())
            if pid in inventory:
                continue
            primitive = self.primitives.get(pid)
            if primitive is None:
                continue
            inventory.add(pid)
            pending.extend(str(parent) for parent in primitive.parent_ids)
        return frozenset(inventory)

    def propose_search_policies(self):
        p = self.meta_policy
        d = max(1, int(p["max_depth"]))
        n = float(p["novelty_weight"])
        e = float(p["exploration"])
        m = float(p["mutation_rate"])
        return (
            {"max_depth": d, "novelty_weight": n, "exploration": e, "mutation_rate": m},
            {"max_depth": d + 1, "novelty_weight": n, "exploration": min(1.0, e + 0.1), "mutation_rate": m},
            {"max_depth": d + 2, "novelty_weight": min(0.95, n + 0.1), "exploration": e, "mutation_rate": min(0.95, m + 0.1)},
        )

    def _expression_stream(
        self,
        keys: Sequence[str],
        primitive_ids: Sequence[str],
        max_depth: int,
    ):
        raw_atoms = tuple(self._expr_atoms(keys, primitive_ids))
        # Once a capability exists, prioritize expressions that actually reuse
        # retained executable primitives. This is generic archive-driven search
        # ordering, not task-specific routing.
        macro_atoms = tuple(
            atom for atom in raw_atoms if atom.get("op") == "macro"
        )
        other_atoms = tuple(
            atom for atom in raw_atoms if atom.get("op") != "macro"
        )
        atoms = macro_atoms + other_atoms if primitive_ids else raw_atoms
        levels: dict[int, tuple[Mapping[str, object], ...]] = {1: atoms}
        seen: set[str] = set()

        for expression in atoms:
            key = json.dumps(expression, sort_keys=True, separators=(",", ":"))
            if key not in seen:
                seen.add(key)
                yield expression

        for depth in range(2, int(max_depth) + 1):
            current: list[Mapping[str, object]] = []

            for expression in levels.get(depth - 1, ()):
                current.append({"op": "abs", "arg": expression})
                current.append({"op": "neg", "arg": expression})

            pair_specs = [(depth - 1, depth - 1)]
            for other_depth in range(1, depth - 1):
                pair_specs.append((depth - 1, other_depth))
                pair_specs.append((other_depth, depth - 1))

            for left_depth, right_depth in pair_specs:
                for left in levels.get(left_depth, ()):
                    for right in levels.get(right_depth, ()):
                        for op in ("add", "sub", "mul", "max", "min"):
                            current.append(
                                {
                                    "op": op,
                                    "left": left,
                                    "right": right,
                                }
                            )

            unique: list[Mapping[str, object]] = []
            layer_seen: set[str] = set()
            for expression in current:
                if ast_depth(expression) != depth:
                    continue
                key = json.dumps(expression, sort_keys=True, separators=(",", ":"))
                if key in layer_seen:
                    continue
                layer_seen.add(key)
                unique.append(expression)

            levels[depth] = tuple(unique)
            for expression in unique:
                key = json.dumps(expression, sort_keys=True, separators=(",", ":"))
                if key in seen:
                    continue
                seen.add(key)
                yield expression

    def invent_primitive(
        self,
        train: Sequence,
        holdout: Sequence,
        transfer: Sequence,
        semantics: str = "delta",
    ) -> CognitivePrimitive | None:
        if len(train) < 6:
            return None

        discovery_rows = tuple(train)
        max_depth = max(3, int(self.meta_policy["max_depth"]) + 1)
        previous_horizon = getattr(self, "_h7_search_primary_chain_horizon", None)
        self._h7_search_primary_chain_horizon = len(self._h7_primary_macro_ids) + 1
        try:
            result = find_exact_expression(
                self,
                discovery_rows,
                max_depth,
                require_macro=bool(self.generation > 0 and self.primitives),
                # Wider discovery-only alternative pool for the lineage-diverse readout.
                max_alternatives=32,
            )
        finally:
            if previous_horizon is None:
                self.__dict__.pop("_h7_search_primary_chain_horizon", None)
            else:
                self._h7_search_primary_chain_horizon = previous_horizon
        if result is None:
            self.last_primitive_candidate_frontier = ()
            return None

        def error(rows: Sequence, expression: Mapping[str, object]) -> float:
            if not rows:
                return float("inf")
            vals = []
            pmap = self._pmap()
            for trace in rows:
                try:
                    vals.append(abs(eval_expr(expression, trace.inputs, pmap) - trace.target))
                except Exception:
                    return float("inf")
            return sum(vals) / len(vals)

        specs = list(result.alternatives) or [(result.expression, result.used_primitives)]
        exact_discovery_alternative_count = len(specs)
        near_pair_specs = []
        seen_spec_keys = {
            (
                tuple(sorted(set(str(pid) for pid in used))),
                json.dumps(expression, sort_keys=True, separators=(",", ":")),
            )
            for expression, used in specs
        }
        for candidate in result.stats.get("primary_invention_near_target_pair_candidates", ()):
            expression = candidate.get("expression")
            used = tuple(sorted(set(str(pid) for pid in candidate.get("direct_parent_ids", ()))))
            if not isinstance(expression, Mapping) or len(used) != 2:
                continue
            if self._h7_primary_pair_recency_priority(expression) != 0:
                continue
            # Re-evaluate only on permitted discovery rows, using the existing
            # frozen training MAE threshold. Validation partitions are not read.
            if error(discovery_rows, expression) > 1e-9:
                continue
            key = (used, json.dumps(expression, sort_keys=True, separators=(",", ":")))
            if key in seen_spec_keys:
                continue
            seen_spec_keys.add(key)
            near_pair_specs.append((copy.deepcopy(expression), used))
        selected_specs = _h7_pair_signature_preserving_specs(
            specs,
            non_pair_cap=8,
            pair_recency_priority=self._h7_primary_pair_recency_priority,
            max_pair_depth=4,
        )
        selected_spec_keys = {
            (
                tuple(sorted(set(str(pid) for pid in used))),
                json.dumps(expression, sort_keys=True, separators=(",", ":")),
            )
            for expression, used in selected_specs
        }
        for expression, used in near_pair_specs:
            key = (tuple(sorted(set(used))), json.dumps(expression, sort_keys=True, separators=(",", ":")))
            if key not in selected_spec_keys:
                selected_specs.append((expression, used))
                selected_spec_keys.add(key)
        # For the frozen Gen9-11 recency check, order only discovery-fitting
        # alternatives by the recorded primary-chain pair eligibility predicate.
        # No target labels, held-out rows, transfer/OOD results, or post-selection
        # admission outcomes enter this order. Stable index preserves all existing
        # tie-breaks among candidates with the same recency status.
        recency_candidate_rows = []
        candidate_diagnostics = []
        if int(self.generation) in (9, 10, 11):
            selected_specs = [
                item for _, item in sorted(
                    enumerate(selected_specs),
                    key=lambda indexed: (
                        self._h7_primary_pair_recency_priority(indexed[1][0]),
                        indexed[0],
                    ),
                )
            ]
        for expression, used in selected_specs:
            direct_ids = {
                str(node["id"]) for node in self._walk(expression)
                if node.get("op") == "macro" and node.get("id") is not None
            }
            recency_priority = self._h7_primary_pair_recency_priority(expression)
            canonical_parents = canonical_parent_generation_details(
                self.primitives, direct_ids
            )
            direct_parent_generations = canonical_parents["parent_generations"]
            detail = {
                "expression": copy.deepcopy(expression),
                "ast_depth": int(ast_depth(expression)),
                "ast_nodes": int(ast_nodes(expression)),
                "used_primitives": sorted(set(str(pid) for pid in used)),
                "direct_parent_ids": sorted(direct_ids),
                "direct_parent_generations": direct_parent_generations,
                "recency_priority": int(recency_priority),
                "recency_eligible": recency_priority == 0,
            }
            candidate_diagnostics.append(detail)
            if int(self.generation) in (9, 10, 11) and len(direct_ids) >= 2:
                recency_candidate_rows.append(copy.deepcopy(detail))
        frontier: list[CognitivePrimitive] = []
        for expression, used in selected_specs:
            pid = "prim:" + digest((expression, semantics))[:20]
            if pid in self.primitives:
                continue
            primitive = CognitivePrimitive(
                pid,
                copy.deepcopy(expression),
                tuple(sorted(set().union(*(t.inputs.keys() for t in discovery_rows)))),
                semantics,
                self.generation,
                tuple(used),
                tuple(sorted({t.family for t in list(train) + list(transfer)})),
                error(train, expression),
                error(holdout, expression),
                error(transfer, expression),
                ast_nodes(expression),
                {
                    "origin": "open_ended_behavioral_dp_search",
                    "schema_given": False,
                    "external_model": False,
                    "selection_source": "discovery_and_selection_only",
                    "ood_used_for_selection": False,
                    "validation_evaluated_after_selection": True,
                    "validation_role": "admission_only",
                    "candidate_frontier_size": len(selected_specs),
                    "pair_signature_archive_count": sum(
                        1 for expression, used in selected_specs
                        if ast_depth(expression) <= 2 and len(set(used)) == 2
                    ),
                    "direct_parent_ids": list(used),
                    "search_stats": dict(result.stats),
                },
            )
            self.primitives[pid] = primitive
            self.archive[pid] = ArchiveRecord(primitive)
            frontier.append(primitive)

        self.last_search_stats = dict(result.stats)
        self.last_primitive_candidate_frontier = tuple(frontier)
        if int(self.generation) in (9, 10, 11):
            selected = frontier[0] if frontier else None
            selected_ids = list(getattr(selected, "parent_ids", ())) if selected is not None else []
            selected_parent_details = canonical_parent_generation_details(
                self.primitives, selected_ids
            )
            selected_ids = selected_parent_details["parent_ids"]
            selected_generations = selected_parent_details["parent_generations"]
            self._h7_primitive_invention_summary = {
                "generation": int(self.generation),
                "source": "OpenEndedRecursiveCognitiveCompiler.invent_primitive",
                "discovery_fitting_alternative_count": exact_discovery_alternative_count,
                "near_target_recency_pair_candidate_count": len(near_pair_specs),
                "selected_frontier_count_after_signature_preserving": len(selected_specs),
                "recency_eligible_discovery_candidate_count": sum(
                    row["recency_eligible"] for row in recency_candidate_rows
                ),
                "recency_ineligible_discovery_candidate_count": sum(
                    not row["recency_eligible"] for row in recency_candidate_rows
                ),
                # Keep the legacy 32-row sample for compatibility, but also persist
                # the complete discovery-qualified pair list and every returned
                # candidate expression. This is diagnostic-only: it does not alter
                # candidate ordering, admission, or any frozen qualification gate.
                "candidate_pair_samples": recency_candidate_rows[:32],
                "candidate_pair_diagnostics": recency_candidate_rows,
                "candidate_details": candidate_diagnostics,
                "candidate_diagnostics_complete": True,
                "search_diagnostics": {
                    key: result.stats.get(key)
                    for key in (
                        "schema", "status", "rows", "max_depth", "primitive_count",
                        "generated_expressions", "unique_states", "duplicate_states",
                        "inverse_hits", "target_matches", "max_states_in_depth",
                        "max_lineage_coverage", "best_target_depth",
                        "dominance_pruned_states", "dominance_frontier_max",
                        "active_expansion_frontier_max", "active_expansion_pool_states_max",
                        "active_expansion_frontier_input_max", "passive_alias_archive_max",
                        "passive_alias_archive_state_count", "passive_alias_archive_cap",
                        "primary_chain_horizon", "passive_alias_archive_compactions",
                        "passive_alias_primary_subset_overflow_count", "archived_alias_states",
                        "congruence_source_roots", "congruence_child_contexts_seen",
                        "congruence_child_contexts_with_aliases", "congruence_alias_representatives_considered",
                        "congruence_variants_generated", "congruence_variants_registered",
                        "primary_pair_sufficiency_active", "primary_pair_sufficient_candidates",
                        "primary_pair_sufficiency_min_ast_depth", "primary_pair_overparameterized_prunes",
                        "congruence_new_direct_signatures", "congruence_new_lineage_signatures",
                        "exact_expression_duplicates_skipped", "target_directed_candidates",
                        "generic_binary_pairs_evaluated", "binary_combination_attempts",
                        "binary_combination_limit", "binary_combination_budget_exhausted",
                        "active_pool_limit_per_depth", "active_pool_pre_cap_max_per_depth",
                        "active_pool_post_cap_max_per_depth", "active_pool_capped_depth_count",
                        "active_pool_atomic_macro_leaf_count_max", "global_operand_pool_limit",
                        "global_operand_pool_pre_cap_max", "global_operand_pool_post_cap_max",
                        "global_operand_pool_capped_calls", "global_operand_pool_atomic_leaf_count_max",
                        "pair_signature_archive_state_count", "pair_signature_archive_context_count",
                        "pair_signature_archive_max_per_context", "generic_binary_path_skipped_after_target",
                        "target_cutoff_depth", "target_cutoff_reason", "depths_completed",
                        "alternative_candidate_count", "congruence_lifting_enabled",
                        "congruence_signature_prescreen_skips", "congruence_ast_depth_prescreen_skips",
                        "congruence_candidate_validation_failures", "congruence_lifting_skipped_root_coverage",
                        "congruence_lifting_fallback_reason", "congruence_child_representatives_max",
                        "congruence_pair_combinations_evaluated", "congruence_two_level_pair_scan_disabled",
                        "target_matches",
                        "target_pair_signature_archive_count",
                        "target_pair_signature_archive_returned",
                        "target_pair_signature_archive_over_cap",
                        "target_alternatives_cap",
                        "target_alternatives_pre_cap_count",
                        "target_alternatives_post_cap_count",
                        "target_alternatives_pre_cap_signature_count",
                        "target_alternatives_post_cap_signature_count",
                        "target_candidate_lineage_signature_count",
                        "target_matches",
                        "target_directed_candidates",
                        "target_candidate_count",
                        "first_exact_target_depth",
                        "dominance_pruned_states",
                        "within_signature_pruned_states",
                        "subtree_output_degenerate_prunes",
                        "primary_invention_target_vector_match_count_raw",
                        "primary_invention_target_vector_match_outcome_counts",
                        "primary_invention_target_vector_match_states",
                        "primary_invention_near_target_pair_candidates",
                        "primary_invention_near_target_pair_candidate_count",
                        "recent_pair_expression_observations",
                        "recent_pair_expression_observation_count",
                        "recent_primary_subtree_aliases_preserved",
                        "recent_primary_subtree_alias_preserved_count",
                        "recent_primary_subtree_alias_preservation_sample",
                        "recent_primary_alias_selected_by_active_pool_calls",
                        "recent_primary_alias_selected_by_operand_pool_calls",
                        "primary_invention_frontier_diagnostics_complete",
                        "primary_invention_target_frontier_pre_cap",
                        "primary_invention_target_frontier_post_cap",
                        "primary_invention_pair_signature_archive",
                    )
                },
                "selected_primitive_id": getattr(selected, "primitive_id", None),
                "selected_direct_parent_ids": selected_ids,
                "selected_direct_parent_generations": selected_generations,
                "selected_pair_recency_gate_passed": (
                    self._h7_primary_pair_recency_priority(selected.expression) == 0
                    if selected is not None else False
                ),
            }
        return frontier[0] if frontier else None

    def accept_primitive_frontier(
        self,
        *,
        transfer_rows: Sequence,
        ood_rows: Sequence,
        novelty: float,
        resource_cost: float,
    ) -> dict[str, object]:
        frontier = tuple(self.last_primitive_candidate_frontier)
        if not frontier:
            return {"accepted": False, "primary_primitive": None, "candidate_count": 0, "validated_candidate_count": 0}

        def error(rows: Sequence, expression: Mapping[str, object]) -> float:
            if not rows:
                return float("inf")
            vals = []
            pmap = self._pmap()
            for trace in rows:
                try:
                    vals.append(abs(eval_expr(expression, trace.inputs, pmap) - trace.target))
                except Exception:
                    return float("inf")
            return sum(vals) / len(vals)

        passing: list[CognitivePrimitive] = []
        validation: list[dict[str, object]] = []
        for primitive in frontier:
            oo = error(ood_rows, primitive.expression)
            ok = primitive.transfer_error <= 1e-9 and oo <= 1e-9
            validation.append({"primitive_id": primitive.primitive_id, "transfer_error": primitive.transfer_error, "ood_error": oo, "passed": ok})
            if ok:
                passing.append(primitive)
            else:
                self.primitives.pop(primitive.primitive_id, None)
                self.archive.pop(primitive.primitive_id, None)

        self.events.append({
            "event": "PRIMITIVE_POST_SELECTION_VALIDATION",
            "candidate_count": len(frontier),
            "validated_candidate_count": len(passing),
            "selection_source": "discovery_and_selection_only",
            "validation_role": "admission_only",
            "validation": validation,
        })
        if not passing:
            self.last_primitive_candidate_frontier = ()
            return {"accepted": False, "primary_primitive": None, "candidate_count": len(frontier), "validated_candidate_count": 0, "validation": validation}

        primary = passing[0]
        # Maintain only the endogenous selected-primary chain as the active
        # macro coverage inventory. All accepted alternatives remain available
        # to the search, but must not multiply every active expansion group.
        if primary.primitive_id not in self._h7_primary_macro_ids:
            self._h7_primary_macro_ids.append(primary.primitive_id)
        oo = next(x["ood_error"] for x in validation if x["primitive_id"] == primary.primitive_id)
        evaluation = Evaluation(
            float(primary.train_error), float(primary.holdout_error), float(primary.transfer_error), float(oo),
            1.0, max(1.0, float(resource_cost)), max(0.0, float(novelty)), True,
        )
        self.observe_growth_evidence(evaluation, novelty=novelty, resource_cost=resource_cost)
        self.last_primitive_candidate_frontier = tuple(passing)
        return {
            "accepted": True,
            "primary_primitive": primary,
            "candidate_count": len(frontier),
            "validated_candidate_count": len(passing),
            "accepted_candidate_ids": [p.primitive_id for p in passing],
            "validation": validation,
        }

    def _remember_process(self, process: ProcessCandidate) -> None:
        """Keep temporary synthesized-process state bounded without touching the active process.

        Process candidates are evaluated immediately; only retained capabilities need
        long-lived executable state. This bounds stale temporary objects without changing
        candidate generation, selection, evaluator thresholds, or admission semantics.
        """
        self.processes[process.process_id] = process
        if len(self.processes) <= self.PROCESS_HISTORY_LIMIT:
            return
        protected = {self.active, process.process_id}
        for pid in tuple(self.processes):
            if len(self.processes) <= self.PROCESS_HISTORY_LIMIT:
                break
            if pid in protected:
                continue
            self.processes.pop(pid, None)

    def synthesize_process(
        self,
        rows: Sequence,
        transfer: Sequence,
        ood: Sequence | None = None,
    ) -> ProcessCandidate | None:
        if not rows or not transfer:
            self.last_process_candidate_frontier = ()
            return None

        discovery_rows = tuple(rows)
        primitive_ids = tuple(self.primitives)
        frontier: list[ProcessCandidate] = []
        seen: set[str] = set()
        policies = self.propose_search_policies()

        for policy in policies:
            previous_horizon = getattr(self, "_h7_search_primary_chain_horizon", None)
            self._h7_search_primary_chain_horizon = len(self._h7_primary_macro_ids)
            try:
                result = find_exact_expression(
                    self,
                    discovery_rows,
                    max(1, int(policy["max_depth"])),
                    require_macro=bool(self.generation > 0 and primitive_ids),
                    max_alternatives=8,
                )
            finally:
                if previous_horizon is None:
                    self.__dict__.pop("_h7_search_primary_chain_horizon", None)
                else:
                    self._h7_search_primary_chain_horizon = previous_horizon
            if result is None:
                continue
            specs = list(result.alternatives) or [(result.expression, result.used_primitives)]
            selected_specs = _h7_pair_signature_preserving_specs(
                specs,
                non_pair_cap=8,
                pair_recency_priority=self._h7_primary_pair_recency_priority,
                max_pair_depth=min(4, max(1, int(policy["max_depth"]))),
            )
            selected_direct_counts = [len(set(used)) for _, used in selected_specs]
            selected_direct_signatures = [
                "|".join(sorted(set(str(pid) for pid in used)))
                for _, used in selected_specs
            ]
            def _selected_exec_lineage(used):
                lineage = set()
                for primitive_id in used:
                    lineage.update(self.executable_lineage(str(primitive_id)))
                return tuple(sorted(lineage))
            selected_lineage_signatures = [
                _selected_exec_lineage(used) for _, used in selected_specs
            ]
            selected_lineage_coverages = [
                len(signature) for signature in selected_lineage_signatures
            ]
            positive_gen_macro_ids = {
                str(pid) for pid, primitive in self.primitives.items()
                if int(getattr(primitive, "generation", 0)) > 0
            }
            selected_positive_gen_lineage_coverages = [
                len(set(signature) & positive_gen_macro_ids)
                for signature in selected_lineage_signatures
            ]
            search_stats = dict(result.stats)
            _h7_occam_pair_signatures = set(
                str(signature)
                for signature in search_stats.get("primary_pair_occam_minimal_direct_signatures", ())
            )
            search_stats.update({
                "outer_alternative_telemetry_schema": "ACSIE.h7.outer_alternative_slice.v4",
                "outer_alternative_input_count": len(specs),
                "outer_alternative_slice_limit": 8,
                "outer_alternative_slice_count": len(selected_specs),
                "outer_alternative_pair_signature_count": sum(
                    1 for expression, used in selected_specs
                    if ast_depth(expression) <= 2 and len(set(used)) == 2
                ),
                "outer_alternative_non_pair_cap": 8,
                "outer_alternative_max_direct_primitive_count": max(
                    selected_direct_counts, default=0
                ),
                "outer_alternative_direct_primitive_counts": selected_direct_counts,
                "outer_alternative_direct_signatures": selected_direct_signatures,
                "outer_alternative_max_executable_lineage_coverage": max(
                    selected_lineage_coverages, default=0
                ),
                "outer_alternative_executable_lineage_coverages": selected_lineage_coverages,
                "outer_alternative_executable_lineage_signatures": [
                    list(signature) for signature in selected_lineage_signatures
                ],
                "outer_alternative_positive_generation_lineage_coverages": selected_positive_gen_lineage_coverages,
            })
            self.last_search_stats = dict(search_stats)
            for expression, used in selected_specs:
                pid = "proc:" + digest((expression, policy, self.generation))[:20]
                if pid in seen:
                    continue
                seen.add(pid)
                process = ProcessCandidate(
                    pid, copy.deepcopy(expression), tuple(used), self.generation,
                    tuple(used), dict(policy),
                    tuple(sorted({t.family for t in discovery_rows})),
                    ast_nodes(expression),
                    {
                        "origin": "open_ended_behavioral_dp_search",
                        "external_model": False,
                        "retained_macro_count": len(used),
                        "search_depth": int(policy["max_depth"]),
                        "ood_used_for_selection": False,
                        "selection_source": "discovery_and_selection_only",
                        "post_selection_validation_role": "admission_only",
                        "candidate_frontier_size": len(selected_specs),
                        "search_stats": dict(search_stats),
                    },
                )
                process.provenance["primary_pair_occam_minimal"] = (
                    "|".join(sorted(set(str(pid) for pid in used))) in _h7_occam_pair_signatures
                )
                self._remember_process(process)
                frontier.append(process)
            if frontier:
                break

        self.last_process_candidate_frontier = tuple(frontier)
        if not frontier:
            self.process_frontier = []
            return None

        # Keep the historical direct-use count as the first outer objective.
        # For required-macro searches, break direct-count ties using the number
        # of distinct positive-generation IDs in transitive executable lineage
        # before shallow AST complexity and alphabetical JSON order.
        positive_gen_macro_ids = {
            str(pid) for pid, primitive in self.primitives.items()
            if int(getattr(primitive, "generation", 0)) > 0
        }

        if self.generation > 0 and positive_gen_macro_ids:
            active_positive_inventory = (
                set(self._h7_macro_coverage_inventory()) & positive_gen_macro_ids
            )

            def _process_lineage_scores(process: ProcessCandidate) -> tuple[int, int, int]:
                direct = set(str(pid) for pid in process.used_primitives)
                lineage: set[str] = set()
                for primitive_id in process.used_primitives:
                    lineage.update(self.executable_lineage(str(primitive_id)))
                active_coverage = len(lineage & active_positive_inventory)
                off_chain_direct = len(
                    (direct & positive_gen_macro_ids) - active_positive_inventory
                )
                all_positive_lineage = len(lineage & positive_gen_macro_ids)
                return active_coverage, off_chain_direct, all_positive_lineage

            def _process_occam_selection_key(process: ProcessCandidate) -> tuple[Any, ...]:
                if bool(process.provenance.get("primary_pair_occam_minimal")):
                    lineage: set[str] = set()
                    for primitive_id in process.used_primitives:
                        lineage.update(self.executable_lineage(str(primitive_id)))
                    primary_order = tuple(str(pid) for pid in self._h7_primary_macro_ids)
                    primary_index = {pid: index for index, pid in enumerate(primary_order)}
                    direct_indices = sorted(
                        (primary_index[pid] for pid in set(process.used_primitives)
                         if pid in primary_index),
                        reverse=True,
                    )
                    if len(direct_indices) == 2:
                        # Prefer lineage-bearing executable behavior before
                        # direct-ID recency, avoiding shallow recent aliases.
                        return (
                            0,
                            -len(lineage & set(primary_order)),
                            -direct_indices[0],
                            -direct_indices[1],
                            process.complexity,
                            json.dumps(process.expression, sort_keys=True),
                            process.process_id,
                        )
                    return (
                        0,
                        0,
                        0,
                        -len(lineage & set(primary_order)),
                        process.complexity,
                        json.dumps(process.expression, sort_keys=True),
                        process.process_id,
                    )
                return (
                    1,
                    -_process_lineage_scores(process)[0],
                    _process_lineage_scores(process)[1],
                    -len(set(str(pid) for pid in process.used_primitives)),
                    -_process_lineage_scores(process)[2],
                    process.complexity,
                    json.dumps(process.expression, sort_keys=True),
                    process.process_id,
                )

            frontier.sort(key=_process_occam_selection_key)
        else:
            # Unchanged bootstrap order when no learned macro exists.
            frontier.sort(key=lambda p: (
                -len(p.used_primitives),
                p.complexity,
                json.dumps(p.expression, sort_keys=True),
                p.process_id,
            ))
        self.process_frontier = [p.process_id for p in frontier]
        return frontier[0]

    def validate_process_frontier(
        self,
        *,
        train: Sequence,
        holdout: Sequence,
        transfer: Sequence,
        ood: Sequence,
        conflict: Sequence = (),
    ) -> tuple[ProcessCandidate | None, Evaluation | None, dict[str, object]]:
        frontier = tuple(self.last_process_candidate_frontier)
        evaluations: list[dict[str, object]] = []
        passing: list[tuple[ProcessCandidate, Evaluation]] = []
        for proc in frontier:
            ev = self.evaluate(proc, train, holdout, transfer, ood, conflict)
            ok = bool(ev.accepted and ev.ood_error <= 1e-9)
            evaluations.append({"process_id": proc.process_id, "transfer_error": ev.transfer_error, "ood_error": ev.ood_error, "accepted": ok})
            if ok:
                passing.append((proc, ev))
        chosen = passing[0] if passing else (None, None)
        summary = {
            "candidate_count": len(frontier),
            "validated_candidate_count": len(passing),
            "selection_source": "discovery_and_selection_only",
            "validation_role": "admission_only",
            "validation": evaluations,
        }
        self.last_process_validation_summary = dict(summary)
        self.events.append({"event": "PROCESS_POST_SELECTION_VALIDATION", **summary})
        return chosen[0], chosen[1], summary

    def observe_growth_evidence(
        self,
        evaluation: Evaluation,
        *,
        novelty: float,
        resource_cost: float,
    ) -> GrowthEvidence:
        safe_novelty = max(0.0, float(novelty))
        cost = max(1.0, float(resource_cost))
        transfer_gain = max(0.0, 1.0 - float(evaluation.transfer_error))
        ood_gain = max(0.0, 1.0 - float(evaluation.ood_error))
        generic_gain = (transfer_gain + ood_gain + safe_novelty) / cost

        if evaluation.accepted and generic_gain > 0.0:
            self.growth_credit += generic_gain
            # No fixed ceiling: each productive retained capability can buy
            # another unit of future search depth.
            increments = max(1, int(self.growth_credit))
            self.growth_credit -= increments
            self.meta_policy["max_depth"] = int(self.meta_policy["max_depth"]) + increments

        self.max_observed_depth = max(
            self.max_observed_depth,
            int(self.meta_policy["max_depth"]),
        )

        evidence = GrowthEvidence(
            accepted=bool(evaluation.accepted),
            transfer_error=float(evaluation.transfer_error),
            ood_error=float(evaluation.ood_error),
            novelty=safe_novelty,
            resource_cost=cost,
            growth_credit=float(self.growth_credit),
            resulting_max_depth=int(self.meta_policy["max_depth"]),
            retained_capability_count=len(self.primitives),
        )
        self.growth_history.append(evidence)
        self.growth_history = self.growth_history[-512:]
        return evidence

    def accept_primitive(
        self,
        primitive_id: str,
        *,
        transfer_error: float,
        ood_error: float,
        novelty: float,
        resource_cost: float,
    ) -> bool:
        if primitive_id not in self.primitives:
            return False
        accepted = (
            float(transfer_error) <= 1e-9
            and float(ood_error) <= 1e-9
        )
        if not accepted:
            self.primitives.pop(primitive_id, None)
            self.archive.pop(primitive_id, None)
            return False
        evaluation = Evaluation(
            train_error=0.0,
            holdout_error=0.0,
            transfer_error=float(transfer_error),
            ood_error=float(ood_error),
            interference_harm=1.0,
            resource_cost=max(1.0, float(resource_cost)),
            novelty=max(0.0, float(novelty)),
            accepted=True,
        )
        self.observe_growth_evidence(
            evaluation,
            novelty=novelty,
            resource_cost=resource_cost,
        )
        return True

    def retain(
        self,
        proc: ProcessCandidate,
        evaluation: Evaluation,
        *,
        novelty: float = 0.0,
    ) -> bool:
        accepted = super().retain(proc, evaluation)
        if not accepted:
            return False
        self.observe_growth_evidence(
            evaluation,
            novelty=novelty,
            resource_cost=max(1.0, float(proc.complexity)),
        )
        return True

    def growth_state(self) -> dict:
        return {
            "schema": self.SCHEMA,
            "max_depth": int(self.meta_policy["max_depth"]),
            "max_observed_depth": int(self.max_observed_depth),
            "growth_credit": float(self.growth_credit),
            "retained_capability_count": len(self.primitives),
            "active_process": self.active,
            "h7_primary_macro_ids": list(self._h7_primary_macro_ids),
            "h7_macro_coverage_inventory": sorted(self._h7_macro_coverage_inventory()),
            "last_search_stats": dict(self.last_search_stats),
            "history": [asdict(x) for x in self.growth_history[-64:]],
        }


__all__ = [
    "GrowthEvidence",
    "OpenEndedRecursiveCognitiveCompiler",
]

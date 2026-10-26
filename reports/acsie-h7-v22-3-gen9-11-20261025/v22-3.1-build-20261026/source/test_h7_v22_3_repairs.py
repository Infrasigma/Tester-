from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "research/recovered/h7_v22_2_runtime/source"
sys.path.insert(0, str(SOURCE_ROOT))

from cognitive_core.open_ended_growth import OpenEndedRecursiveCognitiveCompiler
from cognitive_core.recursive_cognitive_compiler import (
    ArchiveRecord,
    CognitivePrimitive,
    RecursiveCognitiveCompiler,
    Trace,
    ast_depth,
    eval_expr,
    h7_primary_pair_rank_prefix,
)
import cognitive_core.open_ended_growth as growth_module
import cognitive_core.behavioral_search as behavioral_search
from lab.acsie_open_ended_self_extending_proving import (
    HiddenCapability,
    retained_representation_error,
    select_discovery_ranked_candidate,
    selected_closure_reuse_gate,
    primary_pair_recency_gate,
    _h7_write_incomplete_pair_summary,
)
from lab.h7_exact_audit import memoized_eval_expr


def make_primitive(pid, generation, expression, parents=()):
    return CognitivePrimitive(
        primitive_id=pid,
        expression=expression,
        input_roles=("x",),
        output_semantics="delta",
        generation=generation,
        parent_ids=tuple(parents),
        source_families=("fixture",),
        train_error=0.0,
        holdout_error=0.0,
        transfer_error=0.0,
        complexity=1,
        provenance={"fixture": True},
    )


class H7V223RepairTests(unittest.TestCase):
    def test_memoized_eval_is_bit_identical_and_reuses_shared_nodes(self):
        compiler = RecursiveCognitiveCompiler(seed=31)
        root = make_primitive("prim:root", 0, {"op": "get", "key": "x"})
        shared = {"op": "macro", "id": "prim:root"}
        chain_expr = {"op": "add", "left": shared, "right": shared}
        chain = make_primitive("prim:chain", 1, chain_expr, ("prim:root",))
        compiler.primitives[root.primitive_id] = root
        compiler.primitives[chain.primitive_id] = chain

        hidden_shared = {"op": "macro", "id": "hidden:root"}
        hidden_expr = {"op": "add", "left": hidden_shared, "right": hidden_shared}
        hidden_macros = {"hidden:root": {"op": "get", "key": "x"}}
        cap = HiddenCapability(
            hidden_id="hidden:chain",
            primitive_id="prim:chain",
            expression=hidden_expr,
            depth=2,
            generation=1,
            parent_hidden_id="hidden:root",
            parent_hidden_ids=("hidden:root",),
        )
        rows = tuple(
            Trace(
                inputs={"x": float(x)},
                target=2.0 * float(x),
                family="fixture",
                context={},
                task_id=f"memo-{x}",
            )
            for x in (-3, -1, 0, 2, 4, 7)
        )

        uncached_error = retained_representation_error(
            compiler, cap, rows, hidden_macros
        )
        cache = {}
        stats = {}
        cached_error = retained_representation_error(
            compiler,
            cap,
            rows,
            hidden_macros,
            primitive_macros=compiler._pmap(),
            evaluation_cache=cache,
            evaluation_cache_stats=stats,
        )
        self.assertEqual(cached_error, uncached_error)
        self.assertEqual(cached_error, 0.0)
        # The frozen audit decision is the same exact <= 1e-9 predicate.
        self.assertEqual(cached_error <= 1e-9, uncached_error <= 1e-9)
        self.assertGreater(stats.get("cache_hits", 0), 0)

        # Exact map identity must be part of the key: the same macro AST is not
        # interchangeable across hidden and executable namespaces.
        macro_expr = {"op": "macro", "id": "m"}
        shared_cache = {}
        self.assertEqual(memoized_eval_expr(
            macro_expr, {"x": 1.0}, {"m": {"op": "const", "value": 2}},
            shared_cache,
        ), 2.0)
        self.assertEqual(memoized_eval_expr(
            macro_expr, {"x": 1.0}, {"m": {"op": "const", "value": 9}},
            shared_cache,
        ), 9.0)

    def test_primary_invention_priority_prefers_recent_two_parent_chain(self):
        compiler = RecursiveCognitiveCompiler(seed=53)
        compiler.generation = 11
        compiler._h7_primary_macro_ids = ["prim:old", "prim:mid", "prim:recent", "prim:latest"]
        for pid, gen in (("prim:old", 3), ("prim:mid", 8), ("prim:recent", 10), ("prim:latest", 11)):
            compiler.primitives[pid] = make_primitive(pid, gen, {"op": "get", "key": "x"})
        stale = {"op": "add", "left": {"op": "macro", "id": "prim:mid"}, "right": {"op": "macro", "id": "prim:old"}}
        recent = {"op": "add", "left": {"op": "macro", "id": "prim:recent"}, "right": {"op": "macro", "id": "prim:mid"}}
        self.assertEqual(compiler._h7_primary_pair_recency_priority(stale), 1)
        self.assertEqual(compiler._h7_primary_pair_recency_priority(recent), 0)

    def test_incomplete_pair_audit_is_written_when_denominator_is_short(self):
        rows = [{"pair_index": i, "accepted": False} for i in range(28)]
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"ACSIE_H7_PAIR_AUDIT_DIR": tmp}):
                path, summary = _h7_write_incomplete_pair_summary(
                    2026100303, 8, 36, rows,
                    "frozen_all_pairs_denominator_not_reached",
                    errors=["observed_pair_count=28", "primary_invention_rejection_reason=NO_VALID_PRIMITIVE"],
                    invention_rejection_reason="NO_VALID_PRIMITIVE",
                    invention_candidate_id=None,
                )
            self.assertIsNotNone(path)
            loaded = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema"], "ACSIE.h7.generation_pair_summary.incomplete.v1")
            self.assertEqual(loaded["required_pair_count"], 36)
            self.assertEqual(loaded["observed_pair_count"], 28)
            self.assertEqual(loaded["missing_pair_count"], 8)
            self.assertEqual(loaded["primary_invention_rejection_reason"], "NO_VALID_PRIMITIVE")
            self.assertEqual(loaded["audit_status"], "INCOMPLETE")
            self.assertNotEqual(loaded["schema"], "ACSIE.h7.generation_pair_summary.v1")

    def test_canonical_parent_generation_details_are_ordered_and_deduplicated(self):
        compiler = RecursiveCognitiveCompiler(seed=502)
        compiler.primitives["prim:g8"] = make_primitive("prim:g8", 8, {"op": "get", "key": "x"})
        compiler.primitives["prim:g5"] = make_primitive("prim:g5", 5, {"op": "get", "key": "x"})
        result = growth_module.canonical_parent_generation_details(
            compiler.primitives, ("prim:g8", "prim:g5", "prim:g8")
        )
        self.assertEqual(result["parent_ids"], ["prim:g5", "prim:g8"])
        self.assertEqual(result["parent_generations"], [5, 8])
        self.assertEqual(result["parent_details"], [
            {"parent_id": "prim:g5", "generation": 5},
            {"parent_id": "prim:g8", "generation": 8},
        ])

    def test_scoped_depth4_recency_continuation_preserves_primary_pair_under_cap(self):
        # Gen11 witness: (P9 + P10) * (P9 + P9*P9), with no raw-input
        # leaves and exactly the two direct primary macros {P9, P10}.
        p9 = {"op": "macro", "id": "prim:g9"}
        p10 = {"op": "macro", "id": "prim:g10"}
        s1 = {"op": "add", "left": p9, "right": p10}
        s2 = {"op": "mul", "left": p9, "right": p9}
        s3 = {"op": "add", "left": p9, "right": s2}
        s4 = {"op": "mul", "left": s1, "right": s3}
        self.assertEqual([ast_depth(x) for x in (s1, s2, s3, s4)], [2, 2, 3, 4])

        primary_ids = {"prim:g9", "prim:g10"}
        for subtree in (s1, s2, s3, s4):
            self.assertTrue(behavioral_search._h7_primary_macro_only_tree(subtree, primary_ids))
        self.assertFalse(behavioral_search._h7_primary_macro_only_tree(
            {"op": "add", "left": p9, "right": {"op": "get", "key": "x"}},
            primary_ids,
        ))
        self.assertFalse(behavioral_search._h7_primary_macro_only_tree(
            {"op": "add", "left": p9, "right": {"op": "macro", "id": "prim:aux"}},
            primary_ids,
        ))

        compiler = RecursiveCognitiveCompiler(seed=73)
        compiler.generation = 11
        compiler._h7_primary_macro_ids = ["prim:g9", "prim:g10"]
        compiler.primitives["prim:g9"] = make_primitive(
            "prim:g9", 9, {"op": "get", "key": "x"}
        )
        compiler.primitives["prim:g10"] = make_primitive(
            "prim:g10", 10,
            {"op": "mul", "left": {"op": "const", "value": 2},
             "right": {"op": "mul", "left": {"op": "get", "key": "x"},
                       "right": {"op": "get", "key": "x"}},
             },
        )
        self.assertEqual(compiler._h7_primary_pair_recency_priority(s4), 0)

        # S2/S3 legitimately use only P9 at Gen11; they must survive even
        # though P9 is older than the immediately preceding primary generation.
        generation_by_id = {"prim:g8": 8, "prim:g9": 9, "prim:g10": 10}
        pair_priority = lambda signature: (
            0 if len(set(signature)) == 2 and set(signature) == primary_ids else 1
        )
        for direct_signature in (("prim:g9",), ("prim:g9", "prim:g10")):
            self.assertTrue(behavioral_search._h7_is_primary_recency_building_block(
                direct_signature, primary_ids, generation_by_id, 11, pair_priority
            ))
        self.assertFalse(behavioral_search._h7_is_primary_recency_building_block(
            ("prim:g8",), primary_ids | {"prim:g8"}, generation_by_id, 11, pair_priority
        ))

        # The scoped continuation must include both depths after a depth-2 stale
        # exact match; the prior +1 < depth predicate incorrectly skipped depth 3.
        for continuation_depth in (3, 4):
            self.assertTrue(behavioral_search._h7_extra_recency_depth_at_entry(
                continuation_depth, 2, diagnostics_enabled=True,
                eligible_primary_pair_target_found=False,
            ))
        for continuation_depth in (2, 5):
            self.assertFalse(behavioral_search._h7_extra_recency_depth_at_entry(
                continuation_depth, 2, diagnostics_enabled=True,
                eligible_primary_pair_target_found=False,
            ))
        self.assertFalse(behavioral_search._h7_extra_recency_depth_at_entry(
            3, 2, diagnostics_enabled=True, eligible_primary_pair_target_found=True,
        ))
        # The inner generic continuation must also be primary-scoped at depth 3,
        # not just depth 4; this was the second half of the off-by-one defect.
        for continuation_depth in (3, 4):
            self.assertTrue(behavioral_search._h7_extra_recency_generic_depth(
                continuation_depth, 2, continue_generic_for_recency=True,
            ))
        for continuation_depth in (2, 5):
            self.assertFalse(behavioral_search._h7_extra_recency_generic_depth(
                continuation_depth, 2, continue_generic_for_recency=True,
            ))
        self.assertFalse(behavioral_search._h7_extra_recency_generic_depth(
            3, 2, continue_generic_for_recency=False,
        ))
        generation_by_id = {"prim:g8": 8, "prim:g9": 9, "prim:g10": 10}
        recency_priority = lambda signature: (
            0 if set(signature) == {"prim:g9", "prim:g10"} and len(set(signature)) == 2 else 1
        )
        # The intermediate depth admits P9-only structure, but depth 4 only admits
        # an eligible two-macro pair. This is an operand-language rule, not a target hint.
        self.assertTrue(behavioral_search._h7_extra_recency_union_allowed(
            3, 2, {"prim:g9"}, primary_ids, generation_by_id, 11, recency_priority,
        ))
        self.assertFalse(behavioral_search._h7_extra_recency_union_allowed(
            4, 2, {"prim:g9"}, primary_ids, generation_by_id, 11, recency_priority,
        ))
        self.assertTrue(behavioral_search._h7_extra_recency_union_allowed(
            4, 2, {"prim:g9", "prim:g10"}, primary_ids, generation_by_id, 11, recency_priority,
        ))
        self.assertFalse(behavioral_search._h7_extra_recency_union_allowed(
            3, 2, {"prim:g8"}, primary_ids | {"prim:g8"}, generation_by_id, 11, recency_priority,
        ))

        # Deliberately identical discovery vectors: signature/depth must retain
        # S1, S2, S3, and S4 instead of quotienting S2/S3 into P2/P3 aliases.
        synthetic_states = (
            (s1, (7.0,), ("prim:g9", "prim:g10"), (), 1, 1),
            (s2, (7.0,), ("prim:g9",), (), 2, 2),
            (s3, (7.0,), ("prim:g9",), (), 3, 3),
            (s4, (7.0,), ("prim:g9", "prim:g10"), (), 4, 4),
        )
        self.assertEqual(len({state[1] for state in synthetic_states}), 1)
        witnesses = behavioral_search._h7_primary_signature_depth_witnesses(
            synthetic_states,
            primary_ids,
            max_ast_depth=4,
            pair_recency_priority=lambda signature: (
                0 if len(set(signature)) == 2 and set(signature) == primary_ids else 1
            ),
        )
        witness_exprs = [
            __import__("json").dumps(state[0], sort_keys=True, separators=(",", ":"))
            for state in witnesses
        ]
        self.assertIn(__import__("json").dumps(s1, sort_keys=True, separators=(",", ":")), witness_exprs)
        self.assertIn(__import__("json").dumps(s2, sort_keys=True, separators=(",", ":")), witness_exprs)
        self.assertIn(__import__("json").dumps(s3, sort_keys=True, separators=(",", ":")), witness_exprs)
        self.assertIn(__import__("json").dumps(s4, sort_keys=True, separators=(",", ":")), witness_exprs)
        self.assertEqual(len(witnesses), 4)
        self.assertTrue(primary_pair_recency_gate(
            11, [9, 10], ["prim:g9", "prim:g10"], ["prim:g9", "prim:g10"]
        ))

        # Unequal-depth commutative operands must be reoriented, never skipped.
        self.assertEqual(behavioral_search._h7_commutative_pair_order(100, 1, 3, 2), (False, True))
        self.assertEqual(behavioral_search._h7_commutative_pair_order(1, 100, 3, 2), (False, False))

        # Put many non-pair expressions ahead of the witness. The depth-4
        # recency-eligible direct signature must be reserved before the cap.
        unrelated = [
            ({"op": "add", "left": p9, "right": {"op": "get", "key": f"x{i}"}}, ("prim:g9",))
            for i in range(40)
        ]
        specs = unrelated + [(s4, ("prim:g9", "prim:g10"))]
        preserved = growth_module._h7_pair_signature_preserving_specs(
            specs,
            non_pair_cap=1,
            pair_recency_priority=compiler._h7_primary_pair_recency_priority,
            max_pair_depth=4,
        )
        preserved_json = {
            __import__("json").dumps(expr, sort_keys=True, separators=(",", ":"))
            for expr, _ in preserved
        }
        self.assertIn(
            __import__("json").dumps(s4, sort_keys=True, separators=(",", ":")),
            preserved_json,
        )
        self.assertEqual(len(preserved), 2)  # one reserved pair plus one bounded tail

    def test_primary_pair_recency_gate_rejects_stale_gen11_pair_8_3(self):
        chain = ["prim:a", "prim:b", "prim:c"]
        self.assertEqual(primary_pair_recency_gate(9, [8, 3]), True)
        self.assertEqual(primary_pair_recency_gate(10, [8, 3]), False)
        self.assertEqual(primary_pair_recency_gate(11, [8, 3]), False)
        self.assertEqual(primary_pair_recency_gate(11, [10, 8]), True)
        self.assertEqual(primary_pair_recency_gate(11, [10, 8], ["prim:a", "prim:b"], chain), True)
        self.assertEqual(primary_pair_recency_gate(11, [10, 8], ["prim:a", "prim:alias"], chain), False)
        self.assertEqual(primary_pair_recency_gate(11, [3, 4]), False)  # frozen legacy exclusion
        self.assertIsNone(primary_pair_recency_gate(8, [7, 3]))
        self.assertEqual(primary_pair_recency_gate(11, [10]), False)

    def test_selected_candidate_gate_does_not_promote_other_lineage_candidate(self):
        expected = {"prim:parent-a", "prim:parent-b"}
        selected_trap = SimpleNamespace(process_id="proc:rank-0", used_primitives=("prim:alias",))
        later_valid = SimpleNamespace(process_id="proc:rank-1", used_primitives=("prim:parent-a", "prim:parent-b"))
        frontier = [selected_trap, later_valid]

        selected = select_discovery_ranked_candidate(frontier)
        self.assertIs(selected, selected_trap)
        self.assertIsNot(selected, later_valid)

        # One later lineage candidate among a large frontier does not change the
        # selected candidate's gate. A competent rank-0 non-lineage candidate is
        # an explicit closure trap even if rank-1 would have passed.
        competence, reuse_ok, closure_trap = selected_closure_reuse_gate(
            True, {"prim:alias"}, expected
        )
        self.assertEqual((competence, reuse_ok, closure_trap), (True, False, True))
        self.assertEqual(
            selected_closure_reuse_gate(True, expected, expected),
            (True, True, False),
        )

    def test_retained_representation_error_rejects_primitive_map_in_hidden_macros_slot(self):
        compiler = RecursiveCognitiveCompiler(seed=47)
        primitive = make_primitive("prim:root", 0, {"op": "get", "key": "x"})
        compiler.primitives[primitive.primitive_id] = primitive
        cap = HiddenCapability(
            hidden_id="hidden:root",
            primitive_id="prim:root",
            expression={"op": "macro", "id": "hidden:root"},
            depth=1,
            generation=1,
            parent_hidden_id=None,
            parent_hidden_ids=(),
        )
        hidden_macros = {"hidden:root": {"op": "get", "key": "x"}}
        rows = tuple(
            Trace({"x": float(x)}, float(x), "fixture", {}, f"arg-map-{x}")
            for x in (-2, 0, 3)
        )
        primitive_macros = compiler._pmap()

        correctly_routed = retained_representation_error(
            compiler, cap, rows, hidden_macros,
            primitive_macros=primitive_macros,
        )
        # This reproduces the positional-argument mistake: a primitive map is
        # passed where the hidden-capability map belongs. It must fail closed.
        misrouted = retained_representation_error(
            compiler, cap, rows, primitive_macros,
        )
        self.assertEqual(correctly_routed, 0.0)
        self.assertEqual(correctly_routed <= 1e-9, True)
        self.assertEqual(misrouted, float("inf"))
        self.assertEqual(misrouted <= 1e-9, False)

    def test_closure_telemetry_distinguishes_generated_pair_from_unqualified_pair(self):
        compiler = RecursiveCognitiveCompiler(max_depth=3, population=24, seed=37)
        a = make_primitive("prim:a", 0, {"op": "const", "value": 1.0})
        b = make_primitive("prim:b", 1, {"op": "const", "value": 2.0})
        for primitive in (a, b):
            compiler.primitives[primitive.primitive_id] = primitive
            compiler.archive[primitive.primitive_id] = ArchiveRecord(primitive)
        compiler._h7_primary_macro_ids = ["prim:a", "prim:b"]
        compiler.generation = 9
        rows = tuple(
            Trace(
                inputs={"x": float(x)},
                target=999.0,
                family="fixture",
                context={},
                task_id=f"unqualified-{x}",
            )
            for x in (0, 1, 2, 3, 4, 5)
        )

        frontier = compiler.synthesize_process_frontier(rows, (), (), max_candidates=32)
        summary = compiler.last_process_candidate_selection_summary
        signature = "prim:a|prim:b"
        self.assertEqual(tuple(frontier), ())
        self.assertIn(signature, summary["primary_pair_add_generated_signatures"])
        self.assertNotIn(
            signature,
            summary["primary_pair_add_discovery_qualified_signatures"],
        )
        self.assertIn(
            signature,
            summary["primary_pair_add_not_discovery_qualified_signatures"],
        )

    def test_process_frontier_ranks_minimal_unrolled_pair_before_recent_macro_chain(self):
        compiler = RecursiveCognitiveCompiler(max_depth=3, population=24, seed=2026100301)
        a = make_primitive("prim:a", 0, {"op": "const", "value": 1.0})
        b = make_primitive("prim:b", 1, {"op": "const", "value": 2.0})
        c = make_primitive(
            "prim:c", 2, {"op": "macro", "id": "prim:a"}, ("prim:a",)
        )
        d = make_primitive(
            "prim:d", 3, {"op": "macro", "id": "prim:b"}, ("prim:b",)
        )
        for primitive in (a, b, c, d):
            compiler.primitives[primitive.primitive_id] = primitive
            compiler.archive[primitive.primitive_id] = ArchiveRecord(primitive)
        # Only [a,b] belongs to the accepted primary pair tier. c,d are
        # non-primary alias macros and must not inherit the protected tier just
        # because their expanded expression happens to be exact on these rows.
        compiler._h7_primary_macro_ids = ["prim:a", "prim:b"]
        compiler.generation = 6
        rows = tuple(
            Trace(
                inputs={"x": float(x)},
                target=3.0,
                family="fixture",
                context={},
                task_id=f"minimal-unrolled-{x}",
            )
            for x in range(8)
        )

        frontier = compiler.synthesize_process_frontier(rows, (), (), max_candidates=32)
        self.assertTrue(frontier)
        # [a,b] is an exact discovery-fit direct pair with two expanded leaves;
        # [c,d] has the same surface AST but expands through a four-node chain.
        self.assertEqual(set(frontier[0].used_primitives), {"prim:a", "prim:b"})
        self.assertNotEqual(set(frontier[0].used_primitives), {"prim:c", "prim:d"})
        summary = compiler.last_process_candidate_selection_summary
        self.assertTrue(summary["v22_2_discovery_only_primary_pair_priority"])
        self.assertIn("prim:a|prim:b", summary["v22_2_frontier_direct_signatures"])

    def test_minimal_primary_pair_preserves_lineage_before_unrolled_cost(self):
        # All four primitives are genuine primary-chain members. c and d are
        # executable aliases of a and b respectively; both a+b and c+d fit the
        # discovery rows, but c+d preserves the deeper primary-chain identity.
        compiler = RecursiveCognitiveCompiler(max_depth=3, population=24, seed=2026100305)
        a = make_primitive("prim:a", 0, {"op": "const", "value": 1.0})
        b = make_primitive("prim:b", 1, {"op": "const", "value": 2.0})
        c = make_primitive("prim:c", 2, {"op": "macro", "id": "prim:a"}, ("prim:a",))
        d = make_primitive("prim:d", 3, {"op": "macro", "id": "prim:b"}, ("prim:b",))
        for primitive in (a, b, c, d):
            compiler.primitives[primitive.primitive_id] = primitive
            compiler.archive[primitive.primitive_id] = ArchiveRecord(primitive)
        compiler._h7_primary_macro_ids = ["prim:a", "prim:b", "prim:c", "prim:d"]
        compiler.generation = 4
        rows = tuple(Trace(inputs={"x": float(x)}, target=3.0, family="fixture", context={}, task_id=f"lineage-tier-{x}") for x in range(8))
        frontier = compiler.synthesize_process_frontier(rows, (), (), max_candidates=32)
        self.assertTrue(frontier)
        self.assertEqual(set(frontier[0].used_primitives), {"prim:c", "prim:d"})
        # The child pair is more expensive when unrolled; lineage preservation
        # must therefore precede expanded AST cost within the minimal-pair tier.
        short_alias = h7_primary_pair_rank_prefix(True, 2, 2, 4)
        lineage_preserving = h7_primary_pair_rank_prefix(True, 4, 4, 7)
        non_primary = h7_primary_pair_rank_prefix(False, 999, 1, 1)
        self.assertLess(lineage_preserving, short_alias)
        self.assertLess(lineage_preserving, non_primary)

    def test_checkpoint_closure_trap_boundary_has_competent_lineage_candidate(self):
        # Targeted synthetic replay of the Seed 2026100302 Gen5 failure boundary:
        # a required two-macro addition must be present and lineage-bearing in the
        # returned frontier. This is not claimed as a replay of that seed's checkpoint.
        compiler = RecursiveCognitiveCompiler(max_depth=3, population=24, seed=2026100302)
        a = make_primitive("prim:a", 0, {"op": "const", "value": 1.0})
        b = make_primitive("prim:b", 1, {"op": "const", "value": 2.0})
        for primitive in (a, b):
            compiler.primitives[primitive.primitive_id] = primitive
            compiler.archive[primitive.primitive_id] = ArchiveRecord(primitive)
        compiler._h7_primary_macro_ids = ["prim:a", "prim:b"]
        compiler.generation = 5
        rows = tuple(
            Trace(
                inputs={"x": float(x)},
                target=3.0,
                family="opaque",
                context={},
                task_id=f"closure-seed0302-fixture-{x}",
            )
            for x in range(8)
        )

        frontier = compiler.synthesize_process_frontier(rows, rows, rows, max_candidates=32)
        summary = compiler.last_process_candidate_selection_summary
        signature = "prim:a|prim:b"
        self.assertIn(signature, summary["primary_pair_add_generated_signatures"])
        self.assertIn(signature, summary["primary_pair_add_discovery_qualified_signatures"])

        matching = []
        for proc in frontier:
            direct = set(proc.used_primitives)
            lineage = set()
            for pid in proc.used_primitives:
                lineage.update(compiler.executable_lineage(pid))
            evaluation = compiler.evaluate(proc, rows, rows, rows, rows, ())
            if (
                evaluation.accepted
                and evaluation.ood_error <= 1e-9
                and {"prim:a", "prim:b"}.issubset(lineage)
            ):
                matching.append(proc)
        self.assertTrue(matching, "competent executable lineage-bearing pair candidate missing")
        self.assertTrue(any({"prim:a", "prim:b"}.issubset(set(p.used_primitives)) for p in matching))

    def test_seed0304_gen6_probe_trap_fixture_prefers_executable_lineage(self):
        # Synthetic targeted fixture for the Seed 2026100304 Gen6 probe-trap boundary;
        # this does not claim to reconstruct that seed's unavailable checkpoint state.
        compiler = OpenEndedRecursiveCognitiveCompiler(max_depth=2, population=24, seed=2026100304)
        a = make_primitive("prim:a", 0, {"op": "const", "value": 1.0})
        b = make_primitive(
            "prim:b", 1,
            {"op": "add", "left": {"op": "macro", "id": "prim:a"},
             "right": {"op": "const", "value": 0.0}},
            ("prim:a",),
        )
        c = make_primitive("prim:c", 2, {"op": "const", "value": 2.0})
        d = make_primitive("prim:d", 3, {"op": "const", "value": 3.0})
        for primitive in (a, b, c, d):
            compiler.primitives[primitive.primitive_id] = primitive
            compiler.archive[primitive.primitive_id] = ArchiveRecord(primitive)
        compiler._h7_primary_macro_ids = [
            "prim:a", "prim:b", "prim:c", "prim:d"
        ]
        compiler.generation = 6

        recent_alias = {
            "op": "add",
            "left": {"op": "macro", "id": "prim:c"},
            "right": {"op": "macro", "id": "prim:d"},
        }
        lineage_preserving = {
            "op": "add",
            "left": {"op": "macro", "id": "prim:b"},
            "right": {"op": "macro", "id": "prim:c"},
        }
        alternatives = [
            (recent_alias, ("prim:c", "prim:d")),
            (lineage_preserving, ("prim:b", "prim:c")),
        ]
        stats = {
            "primary_pair_occam_minimal_direct_signatures": [
                "prim:c|prim:d",
                "prim:b|prim:c",
            ]
        }
        result = SimpleNamespace(
            expression=recent_alias,
            used_primitives=("prim:c", "prim:d"),
            alternatives=alternatives,
            stats=stats,
        )
        rows = (
            Trace({"x": 0.0}, 3.0, "fixture", {}, "probe-train-0"),
            Trace({"x": 1.0}, 3.0, "fixture", {}, "probe-train-1"),
            Trace({"x": 2.0}, 3.0, "fixture", {}, "probe-train-2"),
        )
        transfer = (Trace({"x": 4.0}, 3.0, "fixture", {}, "probe-transfer"),)

        with mock.patch.object(growth_module, "find_exact_expression", return_value=result):
            selected = compiler.synthesize_process(rows, transfer, ())

        self.assertIsNotNone(selected)
        self.assertEqual(set(selected.used_primitives), {"prim:b", "prim:c"})
        selected_lineage = set()
        for pid in selected.used_primitives:
            selected_lineage.update(compiler.executable_lineage(pid))
        self.assertTrue({"prim:a", "prim:b", "prim:c"}.issubset(selected_lineage))


    def test_commutative_search_keeps_unique_asymmetric_depth_pair(self):
        # Only the deeper operand is in the current depth frontier; the
        # shallower operand comes from earlier levels. Canonical key order must
        # not make that sole visit disappear.
        self.assertEqual(
            behavioral_search._h7_commutative_pair_order(20, 10, 3, 2),
            (False, True),
        )
        # Equal-depth operands are both visited, so the reverse is a duplicate.
        self.assertEqual(
            behavioral_search._h7_commutative_pair_order(20, 10, 2, 2),
            (True, False),
        )
        self.assertEqual(
            behavioral_search._h7_commutative_pair_order(10, 20, 3, 2),
            (False, False),
        )

    def test_behavioral_search_records_pair_archive_before_and_after_cap(self):
        compiler = OpenEndedRecursiveCognitiveCompiler(max_depth=2, population=24, seed=53)
        primitive_specs = (
            ("prim:g3", 3),
            ("prim:g8", 8),
            ("prim:g9", 9),
            ("prim:g10", 10),
        )
        for pid, generation in primitive_specs:
            primitive = make_primitive(pid, generation, {"op": "const", "value": 1.0})
            compiler.primitives[pid] = primitive
            compiler.archive[pid] = ArchiveRecord(primitive)
        compiler._h7_primary_macro_ids = [pid for pid, _ in primitive_specs]
        compiler.generation = 11
        compiler._h7_search_primary_chain_horizon = 5
        rows = tuple(
            Trace({"x": float(i)}, 2.0, "fixture", {}, f"archive-train-{i}")
            for i in range(6)
        )

        result = growth_module.find_exact_expression(
            compiler, rows, 2, require_macro=True, max_alternatives=2
        )

        self.assertIsNotNone(result)
        stats = result.stats
        self.assertTrue(stats["primary_invention_frontier_diagnostics_complete"])
        self.assertGreater(stats["primary_invention_target_vector_match_count_raw"], 0)
        raw_matches = stats["primary_invention_target_vector_match_states"]
        self.assertEqual(len(raw_matches), stats["primary_invention_target_vector_match_count_raw"])
        self.assertIn(
            ("prim:g10", "prim:g3"),
            {
                tuple(row["direct_signature"])
                for row in raw_matches
                if row["is_two_macro_pair"]
            },
        )
        pre_cap = stats["primary_invention_target_frontier_pre_cap"]
        post_cap = stats["primary_invention_target_frontier_post_cap"]
        pair_archive = stats["primary_invention_pair_signature_archive"]
        self.assertGreaterEqual(len(pair_archive), 6)
        self.assertGreaterEqual(len(pre_cap), len(pair_archive))
        pre_pairs = {
            tuple(row["direct_parent_ids"])
            for row in pre_cap
            if row["ast_depth"] <= 2 and len(row["direct_parent_ids"]) == 2
        }
        post_pairs = {
            tuple(row["direct_parent_ids"])
            for row in post_cap
            if row["ast_depth"] <= 2 and len(row["direct_parent_ids"]) == 2
        }
        expected_recent_pair = ("prim:g10", "prim:g3")
        self.assertIn(expected_recent_pair, pre_pairs)
        self.assertIn(expected_recent_pair, post_pairs)
        self.assertEqual(len(pre_pairs), len(post_pairs))

    def test_primary_recency_diagnostics_persist_every_returned_candidate(self):
        compiler = OpenEndedRecursiveCognitiveCompiler(max_depth=2, population=24, seed=47)
        primitive_specs = (
            ("prim:g3", 3),
            ("prim:g8", 8),
            ("prim:g9", 9),
            ("prim:g10", 10),
        )
        for pid, generation in primitive_specs:
            primitive = make_primitive(pid, generation, {"op": "const", "value": 1.0})
            compiler.primitives[pid] = primitive
            compiler.archive[pid] = ArchiveRecord(primitive)
        compiler._h7_primary_macro_ids = [pid for pid, _ in primitive_specs]
        compiler.generation = 11

        def pair(left, right):
            expression = {
                "op": "add",
                "left": {"op": "macro", "id": left},
                "right": {"op": "macro", "id": right},
            }
            return expression, tuple(sorted((left, right)))

        stale = pair("prim:g8", "prim:g3")
        recent = pair("prim:g10", "prim:g3")
        recent_other = pair("prim:g9", "prim:g10")
        result = SimpleNamespace(
            expression=stale[0],
            used_primitives=stale[1],
            alternatives=[stale, recent, recent_other],
            stats={
                "generated_expressions": 3000,
                "unique_states": 1200,
                "target_matches": 3,
                "target_pair_signature_archive_count": 3,
                "target_pair_signature_archive_returned": 3,
                "target_pair_signature_archive_over_cap": False,
                "target_alternatives_cap": 32,
                "target_alternatives_pre_cap_count": 3,
                "target_alternatives_post_cap_count": 3,
                "target_alternatives_pre_cap_signature_count": 3,
                "target_alternatives_post_cap_signature_count": 3,
                "target_candidate_lineage_signature_count": 3,
            },
        )
        rows = tuple(
            Trace({"x": float(i)}, 2.0, "fixture", {}, f"recency-train-{i}")
            for i in range(6)
        )
        holdout = tuple(
            Trace({"x": float(i)}, 2.0, "fixture", {}, f"recency-holdout-{i}")
            for i in range(2)
        )
        transfer = tuple(
            Trace({"x": float(i)}, 2.0, "fixture", {}, f"recency-transfer-{i}")
            for i in range(4)
        )

        with mock.patch.object(growth_module, "find_exact_expression", return_value=result):
            selected = compiler.invent_primitive(rows, holdout, transfer)

        self.assertIsNotNone(selected)
        self.assertEqual(set(selected.parent_ids), {"prim:g10", "prim:g3"})
        summary = compiler._h7_primitive_invention_summary
        self.assertTrue(summary["candidate_diagnostics_complete"])
        self.assertEqual(len(summary["candidate_details"]), 3)
        self.assertEqual(len(summary["candidate_pair_diagnostics"]), 3)
        self.assertEqual(summary["recency_eligible_discovery_candidate_count"], 2)
        self.assertEqual(summary["recency_ineligible_discovery_candidate_count"], 1)
        self.assertEqual(summary["search_diagnostics"]["target_pair_signature_archive_returned"], 3)
        self.assertTrue(all("expression" in row and "ast_depth" in row for row in summary["candidate_details"]))

    def test_explicit_bootstrap_root_is_protected_outside_primary_chain(self):
        compiler = RecursiveCognitiveCompiler(max_depth=3, population=24, seed=43)
        primary_ids = [f"prim:primary-{i:02d}" for i in range(10)]
        bootstrap_id = "prim:gen0-bootstrap"
        auxiliary_ids = [f"prim:aux-{i:04d}" for i in range(650)]
        compiler._h7_primary_macro_ids = list(primary_ids)
        compiler.bootstrap_primitives = [bootstrap_id]
        compiler._h7_bootstrap_primitives = [
            {"primitive_id": bootstrap_id, "generation": 0}
        ]
        inventory = auxiliary_ids + primary_ids + [bootstrap_id]

        expressions = compiler._exprs(["x"], inventory, 3)
        structures = {
            __import__("json").dumps(expr, sort_keys=True, separators=(",", ":"))
            for expr in expressions
        }
        self.assertEqual(len(expressions), 3000)
        self.assertEqual(
            compiler._expr_enumeration_summary["bootstrap_macro_ids"],
            [bootstrap_id],
        )
        self.assertEqual(compiler._expr_enumeration_summary["protected_macro_count"], 11)
        self.assertFalse(
            compiler._expr_enumeration_summary["primary_pair_prefix_exceeds_limit"]
        )

        protected_pair = {
            "op": "add",
            "left": {"op": "macro", "id": bootstrap_id},
            "right": {"op": "macro", "id": primary_ids[0]},
        }
        self.assertIn(
            __import__("json").dumps(protected_pair, sort_keys=True, separators=(",", ":")),
            structures,
            "explicit bootstrap/primary pair fell behind the 3,000-expression cap",
        )


if __name__ == "__main__":
    unittest.main()

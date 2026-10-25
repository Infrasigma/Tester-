# V22.3 Gen11 recency follow-up — 2026-10-25

## Disposition

**H7 UNRESOLVED · NOT QUALIFIED · DO NOT PROMOTE.** No Kaggle kernel was launched. Frozen seeds, generation count, pair denominators, thresholds, target-access policy, and selection split rules are unchanged.

## Fast primary-invention-only baseline

- Seed: 2026100301
- Restored Gen8 checkpoint SHA-256: 9fa4cdd87ab5039ac6a9bda6e8f65211f1b077622d5a4feb573a30a342c96818
- Checkpoint state digest: 98e11ce0e4940df6dd410dbc6d09f63fc877d0b825e9e9b6c19b02fae5e75b
- Wall time: 15.934715 s; Gen9/10/11 invention times: 0.838830 / 2.873041 / 11.478622 s
- Closure-pair searches: 0; probe searches: 0; probe-parent RNG samples stepped: 12
- target_access_during_discovery=false; selection_uses_holdout_transfer_ood=false

| Generation | Target operator | Target-parent generations | Selected primitive | Selected direct-parent generations | Recency gate |
|---:|---|---|---|---|---|
| 9 | max | [8,7] | prim:1c9f1097608c3f094303 | [7,8] | Pass |
| 10 | max | [8,0] | prim:26db1445ec125612c47d | [9,8] | Pass |
| 11 | mul | [3,4] | prim:c9dafc04ed6c1eaa2115 | [8,3] | FAIL |

The Gen11 target is mul(prim:b9f3c773c769732d845e[Gen3], prim:4a74eb1f189c78ff450e[Gen4]), algebraically:

    ((B0*B1) + B0) * ((B0*B1) + ((B0*B1) + B0))
    B0 = max(abs(z), max(y,z))
    B1 = max(max(abs(z), max(y,z)), z)

This is the target capability's unrolled form, not a selection signal.

## Retained primary-chain inventory at start of Gen11

The restored-and-stepped diagnostic has **11 retained primary-chain capabilities (Gen0–Gen10)**. The actual learner object has **190 primitive records** at that point because search/admission alternatives also exist in learner.primitives; therefore the premise that the entire dictionary contains only 12 primitives is not supported by the state artifact. The table below lists the retained primary chain, using exact direct-macro ASTs and symbolic hidden-capability definitions to avoid exponentially repeating expanded trees.

| Gen | Primitive ID | Direct parent generations | AST depth | Learner expression (direct macro AST) | Hidden capability |
|---:|---|---|---:|---|---|
| 0 | prim:7b9e019ca08c0944c250 | [] | 3 | max(y, abs(z)) | H0 |
| 1 | prim:f7ff4c8074f55158c001 | [0] | 1 | macro(prim:7b9e019ca08c0944c250) | H1 |
| 2 | prim:9c37d71e94d0744e366d | [0,1] | 2 | mul(macro(prim:7b9e019ca08c0944c250), macro(prim:f7ff4c8074f55158c001)) | H2 |
| 3 | prim:b9f3c773c769732d845e | [0,1,2] | 3 | max(macro(prim:f7ff4c8074f55158c001), add(macro(prim:7b9e019ca08c0944c250), macro(prim:9c37d71e94d0744e366d))) | H3 |
| 4 | prim:4a74eb1f189c78ff450e | [0,1,2,3] | 3 | max(add(macro(prim:9c37d71e94d0744e366d), macro(prim:b9f3c773c769732d845e)), max(macro(prim:f7ff4c8074f55158c001), macro(prim:7b9e019ca08c0944c250))) | H4 |
| 5 | prim:22db8a28d488b47c499b | [1,2,4] | 3 | min(macro(prim:4a74eb1f189c78ff450e), max(macro(prim:9c37d71e94d0744e366d), macro(prim:f7ff4c8074f55158c001))) | H5 |
| 6 | prim:9e3491aef701868d2c2a | [4,5] | 2 | max(macro(prim:22db8a28d488b47c499b), macro(prim:4a74eb1f189c78ff450e)) | H6 |
| 7 | prim:13e721bf242502d84dcf | [1,2,4,5,6] | 4 | max(sub(macro(prim:4a74eb1f189c78ff450e), macro(prim:b9f3c773c769732d845e)), max(sub(macro(prim:9e3491aef701868d2c2a), macro(prim:f7ff4c8074f55158c001)), min(macro(prim:22db8a28d488b47c499b), macro(prim:9c37d71e94d0744e366d)))) | H7 |
| 8 | prim:9759420bfb5bc95dcb96 | [1,2,4,5,6,7] | 4 | max(max(max(macro(prim:22db8a28d488b47c499b), macro(prim:4a74eb1f189c78ff450e)), max(macro(prim:13e721bf242502d84dcf), macro(prim:9e3491aef701868d2c2a)), max(macro(prim:9c37d71e94d0744e366d), add(macro(prim:f7ff4c8074f55158c001), macro(prim:13e721bf242502d84dcf)))) | H8 |
| 9 | prim:1c9f1097608c3f094303 | [7,8] | 2 | sub(macro(prim:9759420bfb5bc95dcb96), macro(prim:13e721bf242502d84dcf)) | H9 |
| 10 | prim:26db1445ec125612c47d | [8,9] | 2 | sub(macro(prim:9759420bfb5bc95dcb96), macro(prim:1c9f1097608c3f094303)) | H10 |

Hidden-capability algebra, with B0 = max(abs(z), max(y,z)) and B1 = max(B0,z):

- H0 = B0
- H1 = B1
- H2 = B0 * B1
- H3 = H2 + B0
- H4 = H2 + H3
- H5 = max(B0, H2)
- H6 = max(H2, H4)
- H7 = H6 - H1
- H8 = max(H1, H4)
- H9 = H8 - H7
- H10 = H8 - B0

The Gen11 target is H3 * H4. The counterfactual is not merely a fit to the discovery sample; the hidden-capability definitions give a global algebraic identity. Since B0 = max(abs(z), max(y,z)) is nonnegative and already includes z, B1 = max(B0,z) = B0. Thus H3 = B0²+B0, H4 = 2B0²+B0, H7 = H4-B0 = 2B0², H8 = max(B0,H4) = H4, H9 = H8-H7 = B0, and H10 = H8-B0 = 2B0². Therefore the recency-eligible expression

    (H9+H10) * (H9 + H9*H9)
    = (B0+2B0²) * (B0+B0²)
    = H4 * H3

is globally equivalent to the Gen11 target. The numerical replay's maximum error of 5.68e-14 is floating-point roundoff. This proves a valid recency-eligible depth-4 expression exists, but not that the bounded search enumerated it or retained it.


## Gen11 search evidence

- Raw target-vector-matching states: **532**
- Depth distribution: 56 at AST depth 2, 450 at depth 3, 26 at depth 4
- Raw outcomes: 86 admitted before later pruning; 446 subtree-output-degeneracy pruned
- Two-distinct-macro target matches: 99
- Recency-eligible two-macro matches recorded: **0**
- Pre-cap recency-eligible frontier candidates: **0**
- Recency-eligible raw matches dropped between raw record and post-cap frontier: **0** (because no such raw match was recorded)
- Pair-signature archive depth: 2 only; archived signatures: 56
- Distinct (AST depth, direct signature, parent generations, outcome) tuples: 212

All 99 raw two-macro target matches group as follows; none has Gen9 or Gen10 as a direct parent:

| Parent generations | Admitted before later pruning | Subtree-output-degeneracy pruned | Total |
|---|---:|---:|---:|
| [3,4] | 28 | 0 | 28 |
| [3,8] | 7 | 42 | 49 |
| [3,6] | 21 | 0 | 21 |
| [2,3] | 1 | 0 | 1 |
| **Total** | **57** | **42** | **99** |

A separate post-hoc counterfactual, not used in search or selection, evaluates:

    (prim:1c9f1097608c3f094303 + prim:26db1445ec125612c47d) *
    (prim:1c9f1097608c3f094303 +
      (prim:1c9f1097608c3f094303 * prim:1c9f1097608c3f094303))

It has AST depth 4, direct parent generations [9,10], and maximum absolute error 5.684341886080802e-14 across 20 discovery rows (12 rows are bit-exact; remaining errors are floating-point roundoff). This establishes a discovery-fitting recent-pair expression in the depth-4 syntax space, but does not establish that the bounded search retained or selected it.

### Code-path diagnosis

The search's recency-restricted generic continuation was limited to depth <= first_exact_target_depth + 1. Gen11 finds an older exact target at depth 2; that condition only continues the generic lane through depth 3, while the counterfactual above has depth 4. In addition, the commutative generic loop skipped whenever the left structural key sorted after the right key, even when child AST depths differed and the deeper/shallower pair had only one visit in the depth-frontier loop.

The discovery-only patch changes the continuation predicate to:

    continue_generic_for_recency = bool(
        primary_invention_diagnostics_enabled
        and not eligible_primary_pair_target_found
        and (
            first_exact_target_depth is None
            or depth <= first_exact_target_depth + 2
        )
    )

It also uses this pure ordering rule for commutative pairs:

    if left_key <= right_key:
        return False, False
    if left_ast_depth == right_ast_depth:
        return True, False
    return False, True

The return tuple means (skip_duplicate, swap_operands). Equal-depth operands are visited in both orders by the depth frontier, but for unequal depths the deeper operand is only in the current frontier; canonical ordering must reorient that pair rather than silently skip its sole visit. The frozen recency gate remains max(pair_gens) >= generation - 1, exactly two direct primary-chain IDs, with legacy exclusions {9:{4,7}, 10:{1,4}, 11:{3,4}} unchanged.

**Post-fix replay status: NOT VERIFIED.** Two post-fix primary-only attempts exceeded the lightweight-device budget and were stopped without an output artifact (one at about 98 seconds with memory reaching 23.6%; another at about 61 seconds). A separate synthetic search-path regression fixture also exceeded the local budget and was stopped at about 43 seconds, so it was removed from Phase-0 rather than leaving a slow/hanging test. No post-fix search result is inferred from any interrupted attempt. The final code change has unit/Phase-0 coverage, but must be replay-verified on suitable remote compute before it can be considered a demonstrated fix. No Kaggle kernel was launched.

## Historical Gen11 recency check (post hoc)

The current frozen predicate is defined in source/lab/acsie_open_ended_self_extending_proving.py::primary_pair_recency_gate (lines 371–395) and mirrored by recursive_cognitive_compiler.py::_h7_primary_pair_recency_priority (lines 550–580 and the frontier eligibility helper around 844–868). Historical scripts/logs for kernels #15, #20 and #22 do not contain that gate as an evaluated runtime check, so the following is a post-hoc application of the current predicate:

| Historical kernel | Selected Gen11 primitive | Selected direct-parent generations | Gen11 target-parent generations | Post-hoc frozen gate |
|---|---|---|---|---|
| #15 acsie-h7-v22-2-closure-replay-20261023 | prim:7611e41662bbf9487baf | [4,3] | [3,4] | FAIL (max<10, also legacy exclusion) |
| #20 acsie-h7-arch-v22-five-seed-qualification-20261023 | prim:275bef7b3109c393f144 | [3,8] | [3,4] | FAIL (max<10) |
| #22 acsie-h7-arch-v22-gen9-11-checkpoint-continuation | prim:c9dafc04ed6c1eaa2115 | [8,3] | [4,3] | FAIL (max<10) |
| #19 V19 fast gate | — | — | — | Did not reach Gen11; available output ends at Gen6 |

**None of the available historical runs passes the Gen11 gate under the current frozen predicate.** For Kernel #20, the selected primitive expression is mul(prim:73ce8c6b3c2b7b3de053[Gen3], prim:b9d365400a36bcff9a40[Gen8]); its target parents were prim:73ce8c6b3c2b7b3de053[Gen3] and prim:0fcca8b958c7c756accc[Gen4].

## Build and Phase-0

The V22.3 runner and source manifest were rebuilt after the discovery-only code update. Phase-0 passed **26/26 tests**; compile and runner preflight passed. No research slot was started and no Kaggle dispatch occurred.

- Runner SHA-256: 4f1a48bb7a8f9bdc74205e661db62005da8f9061f72fc2fbfd0a57506bcba1f2
- Embedded source archive SHA-256: fa71f7041ddde3bfc78efa6524d5bf242165b3a67345af01a3e87e2f8ac81efc
- Source-manifest canonical digest (build report): 129610c91b2e0c349284730d796345848c555a9a936c35727660e658b958b3bf
- source-manifest.json file SHA-256: 59c065cdb85f0d7b49cbd1a8c715c067a7757d816fdadfd9448fbe2ae1b35767
- Kernel metadata SHA-256: 49549cd6983ac15897e6152c5f0c29cb3ba6b8c944885c4c71f5d2b40f39f2e9

The compact JSON beside this report contains the full 532-row match metadata (depth, direct signature, parent generations, pruning outcome) without duplicating huge AST expressions. It is the evidence artifact for reviewer inspection.

# V22.3 Kaggle terminal failure diagnosis (local-only; 2026-10-26)

- Created: `2026-10-25T21:59:37Z`
- Canonical slug: `memorican/acsie-h7-v22-3-frozen-qualification`
- Last known remote status: `KernelWorkerStatus.ERROR`
- Qualification: **NOT_QUALIFIED**
- Promotion: **DO NOT PROMOTE**
- No Kaggle status/output call was performed for this diagnosis.

## Bug 1 — rejection identifier omitted from validator

Runtime driver emits `[primary_pair_add_not_discovery_qualified]` when the direct primary-pair add expression was generated but did not qualify on discovery rows. The original `REJECTION_REASONS` set did not include that identifier. The validator therefore raised `ValueError: pair N: rejection_reasons must be a list of allowed reason identifiers` on the affected 2026100304 Gen5–Gen11 summaries, marking seven slots INVALID.

Fix: added the identifier to both `research/h7_generation_pair_summary.py` and the embedded-runtime copy. It is a telemetry classification only; eligibility, acceptance thresholds, pair denominator, primary selection, and scientific gates remain unchanged. A regression test collects the reason identifiers emitted by the runtime driver and exercises the builder/auditor on all five committed failure rows.

## Bug 2 — seed 2026100303 triangle-number shortfall

| Generation | Observed pairs | Required pairs | Interpretation |
|---:|---:|---:|---|
| Gen6 | 21 | 21 | CONSISTENT |
| Gen7 | 28 | 28 | CONSISTENT |
| Gen8 | 28 | 36 | INCOMPLETE |
| Gen9 | 36 | 45 | INCOMPLETE |
| Gen10 | 45 | 55 | INCOMPLETE |
| Gen11 | 55 | 66 | INCOMPLETE |

Gen7 is complete at 28/28, matching `C(8,2)`. Gen8 is the first short slot at 28/36, again matching `C(8,2)` rather than `C(9,2)`. This localizes the missing retained-primary append to the **Gen8 admission/retention boundary**. The compact committed excerpt does not contain seed 2026100303 Gen7/Gen8 `PRIMARY_PRIMITIVE_INVENTION_COMPLETE` or `GENERATION_PROGRESS` lines, so the specific `accepted`/`acceptance_reason` or whether invention vs validation failed cannot be reliably stated. A bounded local replay hit its 18-second timeout at Gen1.

## Bug 3 — earliest closure traps and competence failures

The selected candidate is chosen by `first_discovery_ranked_frontier_candidate_v1` before the closure/reuse gate. This is why a rank-0 candidate can be rejected even though a later candidate in the frontier explicitly contains both expected parent IDs and has `competence_ok=true`, `reuse_ok=true`, and zero transfer/OOD error. The gate intentionally does not switch to that later candidate after validation; no such selection-rule change has been made.

| Seed | Gen | Pair | Gate outcome | Top-ranked candidate | Direct-pair candidate |
|---|---:|---:|---|---|---|
| 2026100301 | Gen6 | 3 | `closure_trap` | rank0 `prim:aa76925e4d86255adac4,prim:f7ff4c8074f55158c001`; competence=True; reuse=False; transfer=0.0; OOD=0.0 | idx3 `prim:0fcca8b958c7c756accc,prim:7b9e019ca08c0944c250`; competence=True; reuse=True; transfer=0.0; OOD=0.0 |
| 2026100302 | Gen7 | 1 | `closure_trap` | rank0 `prim:333e6308aa4aa679610d,prim:58f8a853ef5a383209b9`; competence=True; reuse=False; transfer=0.0; OOD=0.0 | idx4 `prim:4c9bbb56a8227388dc10,prim:c8863ee347902ad8a560`; competence=True; reuse=True; transfer=0.0; OOD=0.0 |
| 2026100303 | Gen6 | 4 | `competence_failure` | rank0 `prim:7a1f0b1112cc01bfd890,prim:82058e1e1f3b884805f0`; competence=False; reuse=False; transfer=0.28494989337274007; OOD=0.0 | idx1 `prim:4a5093a8ae2b4487e3e4,prim:82058e1e1f3b884805f0`; competence=True; reuse=True; transfer=0.0; OOD=0.0 |
| 2026100304 | Gen5 | 3 | `closure_trap` | rank0 `prim:955d3c17dbbca3346a2e,prim:9f30333819569f9b1d9d`; competence=True; reuse=False; transfer=0.0; OOD=0.0 | idx1 `prim:955d3c17dbbca3346a2e,prim:b0c420bf3316e423bc15`; competence=True; reuse=True; transfer=0.0; OOD=0.0 |
| 2026100305 | Gen4 | 0 | `competence_failure` | rank0 `prim:7195554b49c72be55e6d,prim:a00ac8dc7c095a30bc5b`; competence=False; reuse=False; transfer=0.37812640529546765; OOD=0.3698623136982637 | idx5 `prim:69e680889385259c198f,prim:ca1cc7ea4217a64a7f5d`; competence=True; reuse=True; transfer=0.0; OOD=0.0 |

### Compact full diagnostics (JSON excerpts)

The JSON artifact contains expected parent IDs, selected candidate parent generations (clearly distinguished from expected-parent generation mapping), both closure-train and closure-selection fidelity errors, rank-0 candidate metrics, top three candidate metrics, matching direct-pair candidate indices/metrics, raw event line hash and size.

Missing from the committed compact rows: per-candidate `expression` AST, candidate `ast_depth`/`ast_nodes`, `holdout_error`, and per-candidate `accepted` field. Selected AST structure and depth/node counts are computed from the separate top-level `selected_expression`; direct-pair candidate AST/holdout values are `NOT_RECORDED`, not invented.

## Bug 4 — remaining primary recency misses

| Seed | Gen | Selected primitive | Selected parent gens | Required max parent gen | Observed max | Result |
|---|---:|---|---|---:|---:|---|
| 2026100303 | Gen9 | `prim:526084bc4aa4cc1c3e9e` | `[6, 7]` | 8 | 7 | **FAIL** |
| 2026100305 | Gen11 | `prim:315a4b71c4f2ecd61599` | `[5, 4]` | 10 | 5 | **FAIL** |

The frozen rule is `max(selected_pair_gens) >= generation - 1`: seed 2026100303 Gen9 fails because `max(6,7)=7 < 8`; seed 2026100305 Gen11 fails because `max(5,4)=5 < 10`. The committed excerpt does not include target parent IDs/operator or the invention event’s exact `recency_eligible_discovery_candidate_count` for these slots. The false final gate establishes that the selected pair is stale; the available record cannot determine whether a valid depth-4/5 candidate was never generated, failed discovery fit, or was pruned before persistence.

## Kaggle terminal ERROR interpretation

The current source returns process exit code 2 if the frozen run’s scientific status is not `PASSED`. The invalid closure summaries and other scientific failures therefore provide a known path to a non-zero kernel result. Because the harvested final run manifest and kernel/seed logs are absent, it is not possible to prove whether Kaggle’s terminal `ERROR` came specifically from that intended exit-2 path or another process-level exception. No further Kaggle status or output call was made.

## Validation of the local-only repair

```text
Embedded archive SHA-256: 7001f4eda5970f398c49ce8a4d127c9bafa0e398f89078f422f609a9d255f6fd
Runner SHA-256: d620c7ff338974a0da1ec3119ef0a1f6f7392b703ce463d00d43bba13f74c8cd
Source-manifest SHA-256: 7822698d7461ca0f9cbff4f0ceb54924d76bb6ddc73d88db35bef2a6a6ee962f
Source-manifest file SHA-256: 3bcb384fd94419ad3dd71208c63e169650b3986435587c77c2082e5821854a71
Build-report file SHA-256: 6b049c0a9af187d618e6e22e09ffccab2176d481c081d39f6b55d71ca5a094d7
Validator unit tests: 7 passed
Phase-0 tests: 34 ran, OK, 0 skipped
Phase-0 status: PASSED
Qualification slots evaluated locally: 0
Kaggle dispatch performed: false
Promotion: DO NOT PROMOTE
```

## Scientific disposition

**NOT_QUALIFIED — DO NOT PROMOTE.** Schema telemetry was fixed, but this repair has not been dispatched to Kaggle and does not resolve the closure traps, competence failures, Gen8 retained-primary failure, the two recency misses, or missing remote provenance certificates. The frozen thresholds and denominator remain unchanged.

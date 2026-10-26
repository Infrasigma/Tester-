# ACSIE H7 V22.3 Gen9–11 verification receipt

Mirrored from `Infrasigma/ACSIE` PR #115 for cross-repository review. This is evidence-only: qualification is `NOT_QUALIFIED` and promotion remains `DO NOT PROMOTE`.

The combined report reconciles Gen9 45/45, Gen10 55/55, Gen11 66/66 closure reuse and 12/12 probe reuse, all with zero recorded traps. Gen11 closure indices 0–54 have aggregate-only durable progress evidence because the initial bounded workers stopped before serializing individual rows; indices 55–65 have per-pair results. See `verification.md` and its matching JSON for the limitation and provenance hashes. Phase-0 tests passed (27 tests); no frozen Kaggle qualification slots were run by these checks.


## Current Kaggle terminal snapshot (2026-10-25 UTC)

This snapshot supersedes any inference that the remote five-seed qualification may have passed. One bounded status check against `memorican/acsie-h7-v22-3-frozen-qualification` returned `KernelWorkerStatus.ERROR`. The single bounded output harvest produced an incomplete bundle: 49/60 generation pair-summary events and 1392/1430 pair outcomes were present; no `run_manifest.json`, foundry summary, or probe logs were recovered. Seed `2026100303` has incomplete Gen8–Gen11 closure audits; seed `2026100304` has INVALID closure audits for Gen5–Gen11 because rejection-reason schema validation failed. Selected primitives and recency flags were recovered for Gen9–Gen11 only; recency fails at seed `2026100303` Gen9 and seed `2026100305` Gen11. Qualification remains `NOT_QUALIFIED`; promotion remains `DO NOT PROMOTE`.

Current evidence: `V22_3_KAGGLE_TERMINAL_STATUS_20261025.json`, `V22_3_KAGGLE_60_SLOT_AUDIT_20261025.json`, `V22_3_KAGGLE_60_SLOT_AUDIT_20261025.md`, `V22_3_KAGGLE_HARVEST_FILES_MANIFEST_20261025.json`, `V22_3_KAGGLE_FAILURE_EVENT_LINES_20261025.log`, the updated dispatch receipt, and `kernel-metadata-canonical.json`. The raw 41 MB event stream was analyzed and its digest/files manifest recorded, but the bulky temporary download was not added to Git.


## Local V22.3 schema repair and terminal-run diagnosis (2026-10-26)

The terminal-harvest diagnosis is in `V22_3_TERMINAL_FAILURE_DIAGNOSIS_20261026.md` and its JSON companion. It identifies the schema mismatch: the driver emits `primary_pair_add_not_discovery_qualified`, which the allowed rejection-reason set omitted. Both the root and embedded runtime validators now allow that telemetry identifier. Tests assert that all driver-emitted rejection identifiers are covered and exercise the five earliest recorded seed failure reasons through the pair-summary builder/auditor.

The local repair build passed with embedded archive SHA-256 `7001f4eda5970f398c49ce8a4d127c9bafa0e398f89078f422f609a9d255f6fd`. Local validator tests: **7 passed**. Phase-0: **34 tests passed, zero skipped**, preflight/compile passed, `qualification_slots_evaluated=0`. The repaired bundle has **not** been dispatched to Kaggle; no further status/poll/harvest was done. The remote run remains `NOT_QUALIFIED`, and promotion remains `DO NOT PROMOTE`.

Known gaps remain documented: the Gen8 admission/retention failure for seed `2026100303` is localized by pair-count evidence, but its exact `accepted`/`acceptance_reason` event was not recovered; per-candidate AST/holdout metrics and exact target-parent/operator fields for the two recency misses were not retained in the compact event excerpt. Those values are marked `NOT_RECORDED` rather than invented.

# ACSIE H7 V22.3 — Process/Closure Frontier Ranking Fix (2026-10-26)

**Status: local fix verified; frozen qualification remains NOT_QUALIFIED — DO NOT PROMOTE.** No Kaggle dispatch was performed.

ACSIE source correction replaces the process/closure frontier's primary-chain recency and maximal-lineage sort bias with discovery-only minimal unrolled executable AST depth/node cost. The primary-invention recency gate itself remains intact. The closure driver already passes concatenated `ctr + cs` discovery/selection observations; transfer and OOD metrics are post-selection only and do not decide candidate order. The candidate is still selected before validation; the patch does not choose a later candidate based on transfer/OOD or expected-parent labels.

Verification:
- `test_h7_v22_3_repairs.py`: 14 passed.
- `test_h7_generation_pair_summary.py`: 7 passed.
- Rebuilt Phase-0: 35 tests, OK; compile/preflight passed; zero qualification slots evaluated; research did not start.
- Embedded archive SHA-256: `eeef65e6bb74dbf25b6b101874acc283604b0c3bb6bfb655c9538ac837b614d8`
- Runner SHA-256: `82eba365a03c717126a31d2fd0dd2a88a3d9da14107e76bdae101ca43655885e`
- Embedded source-manifest SHA-256: `bc86dda10df0944bfc95dde4dcdfa5d1a1548c8eda8e02decc0cb51f470680ab`

The original remote run is still incomplete: the recovered kernel log reports `scientific_status=INCOMPLETE`, 56/60 slots, with 31 PASSED, 25 FAILED and 4 INCONCLUSIVE. The selective output API did not surface the requested Gen8/Gen9 invention fields or `run_manifest.json`. Thus the complete 60-slot probe reuse/lineage table and exact Gen8 primary admission fields cannot be truthfully produced from the recovered evidence. The two recency misses' underlying search/admission cause also remains unresolved. This test is synthetic and does not establish repaired historical seed outcomes.

Full diagnostic and source-level explanation:
https://github.com/Infrasigma/ACSIE/blob/research/h7-closure-telemetry-audit-20261025/research/recovered/h7_v22_2_runtime/evidence/V22_3_PROCESS_FRONTIER_RANKING_FIX_20261026.md

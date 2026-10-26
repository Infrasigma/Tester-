# Kaggle dispatch and terminal status receipt

- Canonical notebook slug: `memorican/acsie-h7-v22-3-frozen-qualification`
- Legacy metadata ID alias: `memorican/acsie-h7-v22-3`
- Dispatch push: confirmed successful by Kaggle CLI, kernel version 1.
- Single canonical-slug status snapshot at `2026-10-25T21:27:24Z` batch start: exit code 0; status `KernelWorkerStatus.ERROR`.
- One bounded output harvest was attempted. It left an incomplete evidence bundle; no status retry or polling loop was performed.
- Returned runtime audit data: 49/60 generation pair summaries and 1392/1430 pair outcomes, with seven INVALID closure audits and four INCOMPLETE closure audits. No probe logs, run manifest, or foundry summary was recovered.
- Selected recency gate false: seed `2026100303` Gen9 and seed `2026100305` Gen11. Earlier closure failures and missing runtime certificates independently block qualification.
- Qualification: `NOT_QUALIFIED`. Promotion: `DO NOT PROMOTE`.

See `V22_3_KAGGLE_60_SLOT_AUDIT_20261025.md` for the full 60-slot report and `V22_3_KAGGLE_FAILURE_EVENT_LINES_20261025.log` for exact raw event payloads at the earliest failure boundary for each seed.


## Local-only repair status — 2026-10-26

- Schema issue fixed: runtime reason `primary_pair_add_not_discovery_qualified` added to both rejection-reason allowlists.
- Local build archive SHA-256: `7001f4eda5970f398c49ce8a4d127c9bafa0e398f89078f422f609a9d255f6fd`.
- Runner SHA-256: `d620c7ff338974a0da1ec3119ef0a1f6f7392b703ce463d00d43bba13f74c8cd`.
- Local validator unit tests: 7 passed. Phase-0: 34 tests passed, zero skipped; no frozen qualification slots were run locally.
- `kaggle_dispatch_performed=false` for this repaired bundle. The historical dispatched version remains the older archive digest recorded at the top level of the JSON receipt.
- Scientific disposition remains `NOT_QUALIFIED`; promotion remains `DO NOT PROMOTE`.

See `V22_3_TERMINAL_FAILURE_DIAGNOSIS_20261026.md` for the 5 failure pairs, triangle-number shortfall, recency failures, exact limitations and code diff.

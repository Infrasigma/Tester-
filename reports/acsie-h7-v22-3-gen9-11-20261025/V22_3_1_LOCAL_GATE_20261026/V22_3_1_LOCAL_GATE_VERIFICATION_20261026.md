# V22.3.1 Local Gate Verification — 2026-10-26

## Disposition

- `SEED_2026100305_GEN0_4_CLOSURE_GATE=PASSED` — 20/20 required pairs observed across Gen1–4; 20/20 reuse; zero closure traps; zero competence failures. Gen0 is bootstrap with denominator 0.
- `SEED_2026100304_GEN0_4_CLOSURE_GATE=PASSED` — 20/20 required pairs observed across Gen1–4; 20/20 reuse; zero closure traps; zero competence failures. Gen0 is bootstrap with denominator 0.
- `SEED_2026100301_GEN6_PAIR5_SPOTCHECK=PASSED` — current postfix diagnostic observed Pair 5 with `reuse_ok=true`, `closure_trap=false`, `competence_ok=true`; this is a one-pair diagnostic, not a complete Gen6 audit. The earlier pre-postfix diagnostic showed a trap; it is not the current-source result.
- `SEED_2026100303_GEN8_INVENTION_SPOTCHECK=FAILED_TRANSFER` — candidate `prim:1461faa33862371b6527` was discovery-ranked but rejected with `TRANSFER_FAILURE`; Gen8 pair audit is incomplete (0/36 observed). This is diagnostic-only and not a qualification result.
- Phase-0 runner preflight/regressions: `PASSED`; 39 tests, 0 failures; compile passed; `research_started=false`; 0 qualification slots evaluated.
- Full local driver for seed 0305 printed `OPEN_ENDED_SELF_EXTENDING_GATE=FAIL` despite its Gen0–4 pair audit being complete and clean. This broader gate result is retained as a separate failure and is not represented as an overall seed pass.
- Kaggle kernel version 3 was dispatched after both Gen0–4 closure gates passed. The one permitted status check returned `KernelWorkerStatus.RUNNING`; no further status checks were made. The 0303 Gen8 transfer failure remains unresolved diagnostic evidence. Promotion remains `DO NOT PROMOTE`; H7 remains unresolved and AGI/ASI/general capability not demonstrated.

## Pair audit table

| Seed | Gen | Required | Observed | Reuse | Traps | Competence failures | SHA-256 |
|---|---:|---:|---:|---:|---|---|---|
| 0305 | 0 | 0 | 0 | 0/0 | [] | [] | `17fc978832f2e4a1c9d5090d1119c6aa9ba0960ab6efd3ab2c22abd12cb8c359` |
| 0305 | 1 | 1 | 1 | 1/1 | [] | [] | `ce66ae17960c3725379fc1bd5d2aa09cebd1fb9e09192e7de7c8106b41755ae2` |
| 0305 | 2 | 3 | 3 | 3/3 | [] | [] | `3e6ea40b0f0a4720ef2019a16ac7cc2475925e659e7c326b00a1c081d67ae85f` |
| 0305 | 3 | 6 | 6 | 6/6 | [] | [] | `d89c2f7225e732d413c6e950dbb8c0643efe5c9254139b00174e3dbbaf1483ac` |
| 0305 | 4 | 10 | 10 | 10/10 | [] | [] | `f8e37d249f3abbb57dd372ebc34d3de28ea1a8af708a382da1b7746e2442e918` |
| 0304 | 0 | 0 | 0 | 0/0 | [] | [] | `a2a7d1f3a300c06de192bd9c4d31c99125fe5d15fc591d1ece7261444a53c2cb` |
| 0304 | 1 | 1 | 1 | 1/1 | [] | [] | `971376251329852f7062a30422dcc5a55f19305216998303a405503f3e425a08` |
| 0304 | 2 | 3 | 3 | 3/3 | [] | [] | `0b6df76fc24f7f59f6c799077255ad6cbea8c113f555b2a0a8855b909677856a` |
| 0304 | 3 | 6 | 6 | 6/6 | [] | [] | `ed8a1c5780e1a8f879afe62a672c4d9aff538b6b084cb3e8d0c3cdefbd78f3ff` |
| 0304 | 4 | 10 | 10 | 10/10 | [] | [] | `4c85ae80a30594a61b7609962c5b5f5a24f52646740a9a84bb3a93d90e130f0b` |
| 0301 | 6 | 21 | 1 | 1/1 | [] | [] | `1f658c7912234e22e1ce18c9deccd0afc18368f525904c757eb2608c9fa25124` |
| 0303 | 8 | 36 | 0 | 0/0 | [] | [] | `3016a170e20071969fb8091b55da3b297d64606c2ac15be9eb072a275a3ae442` |

## Exact spot-check findings

- Seed 0301 Gen6 Pair 5 direct pair: `prim:7b9e019ca08c0944c250 + prim:aa76925e4d86255adac4`. The current postfix audit selected `proc:9dd23a0cc840fbf974f3`, expression `add(macro(prim:aa76925e4d86255adac4), macro(prim:f7ff4c8074f55158c001))`; executable lineage includes both target pair IDs, and reuse/competence passed. The 1/21 observed count is explicitly incomplete.
- Seed 0303 Gen8: candidate `prim:1461faa33862371b6527`, proposed parents generations `[6,2]`, was rejected with `TRANSFER_FAILURE`. The audit remains 0/36, so it cannot be treated as closure certification.
- The lineage-ranking key is now ordered by minimal direct-primary-pair tier, then expanded depth/nodes, then negative executable primary-lineage size, with primary-chain position only after cost/lineage ties. The test suite specifically checks cost-before-lineage and final chain-position tie-breaking. No expected-pair label or holdout/transfer/OOD value is read during candidate ranking.

## Runner preflight

- Kernel: `memorican/acsie-h7-v22-3-frozen-qualification` (private).
- Frozen plan: 5 seeds × 12 generations = 60 slots; required pair denominator remains `g*(g+1)/2`; internet/GPU disabled; `target_access_during_discovery=false`; no dataset/kernel sources; no gate changes.
- Phase-0 status `PASSED`; 39 tests in 3.610s; compile `PASSED`; promotion `DO NOT PROMOTE`.

## Artifact hashes

- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/pair_audits/seed-2026100305-generation-00.json` — `17fc978832f2e4a1c9d5090d1119c6aa9ba0960ab6efd3ab2c22abd12cb8c359`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/pair_audits/seed-2026100305-generation-01.json` — `ce66ae17960c3725379fc1bd5d2aa09cebd1fb9e09192e7de7c8106b41755ae2`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/pair_audits/seed-2026100305-generation-02.json` — `3e6ea40b0f0a4720ef2019a16ac7cc2475925e659e7c326b00a1c081d67ae85f`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/pair_audits/seed-2026100305-generation-03.json` — `d89c2f7225e732d413c6e950dbb8c0643efe5c9254139b00174e3dbbaf1483ac`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/pair_audits/seed-2026100305-generation-04.json` — `f8e37d249f3abbb57dd372ebc34d3de28ea1a8af708a382da1b7746e2442e918`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/logs/seed-0305-run.log` — `622ea27a243bf8dc09b4f1a9daa5937fba51efef59bb49e6d5ab7886098f91dd`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/logs/seed-0305-events.jsonl` — `72c84c6a1964118e187006c8fc7f5fbfec190bcee9692973680e0479281f9cf6`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/pair_audits/seed-2026100304-generation-00.json` — `a2a7d1f3a300c06de192bd9c4d31c99125fe5d15fc591d1ece7261444a53c2cb`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/pair_audits/seed-2026100304-generation-01.json` — `971376251329852f7062a30422dcc5a55f19305216998303a405503f3e425a08`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/pair_audits/seed-2026100304-generation-02.json` — `0b6df76fc24f7f59f6c799077255ad6cbea8c113f555b2a0a8855b909677856a`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/pair_audits/seed-2026100304-generation-03.json` — `ed8a1c5780e1a8f879afe62a672c4d9aff538b6b084cb3e8d0c3cdefbd78f3ff`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/pair_audits/seed-2026100304-generation-04.json` — `4c85ae80a30594a61b7609962c5b5f5a24f52646740a9a84bb3a93d90e130f0b`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/logs/seed-0304-run.log` — `3340e197b763bb836615ef2f12e825ad5b6081eaa573e5cf287f2865337040a6`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/logs/seed-0304-events.jsonl` — `85c027a191b30374fc7b82ce59be687590fd1f89f045871a3aa2a6d80451b4af`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/pair_audits/seed-2026100301-generation-06.json` — `1f658c7912234e22e1ce18c9deccd0afc18368f525904c757eb2608c9fa25124`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/logs/seed-0301-run.log` — `c6f5b8aaf4ac7c6356b22527572fef1586592abe3daccda5995eb634c5249090`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/logs/seed-0301-events.jsonl` — `1aa37adafe83035e7d4d58eb4f968320d0827cbaab555a5a88b1bc3666d9bd45`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/pair_audits/seed-2026100303-generation-08.json` — `3016a170e20071969fb8091b55da3b297d64606c2ac15be9eb072a275a3ae442`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/logs/seed-0303-run.log` — `122354d1d544edfc3f48ed7d51d78e8d864b0deda379a933952e761b9c0bc422`
- `research/recovered/h7_v22_2_runtime/evidence/V22_3_1_LOCAL_GATE_20261026/logs/seed-0303-events.jsonl` — `8a6543dd6f05f6b16a3343d27060fcdbcd7e2c8578993419531beaa58f2bf6e6`
- `research/recovered/h7_v22_2_runtime/source/cognitive_core/recursive_cognitive_compiler.py` — `ccee6efaabbdd5209eeb64b056d58ba0c8ddc7a1685e6ea0bc00f0702c20afdf`
- `research/recovered/h7_v22_2_runtime/source/lab/acsie_open_ended_self_extending_proving.py` — `b15167254489570e89f0e226d1ad4d64f91061d685a91ae697a98b9016c7681d`
- `research/recovered/h7_v22_2_runtime/v22_3_staging/run_acsie_h7_v22_3.py` — `e480c5c6df3713e816bfdfd21e1f2956427d1be373d008be119ee6ffb1b57e38`
- `research/recovered/h7_v22_2_runtime/v22_3_staging/source-manifest.json` — `8408b720c2ad9dadc2617ea27e15624af9db48c3f4f726c7d68ea84469f22896`

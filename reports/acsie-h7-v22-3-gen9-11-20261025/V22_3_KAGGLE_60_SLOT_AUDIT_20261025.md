# ACSIE H7 V22.3 — Kaggle terminal harvest and 60-slot audit

- Snapshot batch start: `2026-10-25T21:27:24Z`
- Canonical notebook slug: `memorican/acsie-h7-v22-3-frozen-qualification`
- Historical metadata ID alias: `memorican/acsie-h7-v22-3`
- Kaggle status: **`KernelWorkerStatus.ERROR`**
- Audit disposition: **FAILED / INCOMPLETE**
- Scientific disposition: **DO NOT PROMOTE**

## Snapshot CLI output

Command: `timeout 15s kaggle kernels list --mine --search v22-3` (exit 0; stdout/stderr combined):
```text
ref                                                           title                                               author     lastRunTime                 totalVotes
------------------------------------------------------------  --------------------------------------------------  ---------  --------------------------  ----------
memorican/acsie-h7-v22-2-closure-replay-20261023              ACSIE H7 V22 2 CLOSURE REPLAY 20261023              Memorican  2026-10-23 03:34:35.880000           0
memorican/acsie-h7-arch-v22-1-gen9-11-replay-20261023         ACSIE H7 ARCH V22 1 GEN9 11 REPLAY 20261023         Memorican  2026-10-23 03:10:10.907000           0
memorican/acsie-h7-v22-2-lineage-bounds-replay-20261023       ACSIE H7 V22 2 Lineage Bounds Replay 20261023       Memorican  2026-10-23 08:34:51.560000           0
memorican/acsie-h7-arch-v22-five-seed-qualification-20261023  ACSIE H7 ARCH V22 Five Seed Qualification 20261023  Memorican  2026-10-22 19:14:59.067000           0
memorican/acsie-h7-arch-v22-gen9-11-checkpoint-continuation   ACSIE H7 ARCH V22 Gen9-11 Checkpoint Continuation   Memorican  2026-10-22 19:03:51.970000           0
memorican/acsie-h7-v22-3-frozen-qualification                 ACSIE H7 V22.3 Frozen Qualification                 Memorican  2026-10-25 18:16:36.243000           0
```

Command: `timeout 15s kaggle kernels status memorican/acsie-h7-v22-3-frozen-qualification` (exit 0; stdout/stderr combined):
```text
memorican/acsie-h7-v22-3-frozen-qualification has status "KernelWorkerStatus.ERROR"
```

## 5-seed master summary

| Seed | execution_status | generations_completed | runtime_seconds | every_closure_perfect | every_probe_perfect | trap_free_ok | lineage_closed | Gen9_recency_pass | Gen10_recency_pass | Gen11_recency_pass | finite_open_ended_growth_gate | earliest_failing_slot_or_reason |
|---|---|---:|---:|---|---|---|---|---|---|---|---|---|
| 2026100301 | KAGGLE_WORKER_ERROR; per-seed final manifest unavailable | 12/12 | NOT_RECOVERED | false | NOT_VERIFIED | False | NOT_VERIFIED | true | true | true | NOT_VERIFIED | Gen6: audit=CONSISTENT, observed/expected=21/21, accepted=16/21, rejected=5, closure_traps=5, first_failure={'closure_trap': True, 'macro_pair': ['prim:7b9e019ca08c0944c250', 'prim:0fcca8b958c7c756accc'], 'pair_index': 3, 'rejection_reasons': ['closure_trap'], 'source_line': 106} |
| 2026100302 | KAGGLE_WORKER_ERROR; per-seed final manifest unavailable | 12/12 | NOT_RECOVERED | false | NOT_VERIFIED | False | NOT_VERIFIED | true | true | true | NOT_VERIFIED | Gen7: audit=CONSISTENT, observed/expected=28/28, accepted=27/28, rejected=1, closure_traps=1, first_failure={'closure_trap': True, 'macro_pair': ['prim:c8863ee347902ad8a560', 'prim:4c9bbb56a8227388dc10'], 'pair_index': 1, 'rejection_reasons': ['closure_trap'], 'source_line': 541} |
| 2026100303 | KAGGLE_WORKER_ERROR; per-seed final manifest unavailable | 8/12 | NOT_RECOVERED | false | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | false | true | true | NOT_VERIFIED | Gen6: audit=CONSISTENT, observed/expected=21/21, accepted=19/21, rejected=2, closure_traps=0, first_failure={'closure_trap': False, 'macro_pair': ['prim:82058e1e1f3b884805f0', 'prim:4a5093a8ae2b4487e3e4'], 'pair_index': 4, 'rejection_reasons': ['competence_failure'], 'source_line': 919} |
| 2026100304 | KAGGLE_WORKER_ERROR; per-seed final manifest unavailable | 5/12 | NOT_RECOVERED | false | NOT_VERIFIED | False | NOT_VERIFIED | true | true | true | NOT_VERIFIED | Gen5: audit=INVALID, observed/expected=15/15, accepted=10/15, rejected=5, closure_traps=4, first_failure={'closure_trap': True, 'macro_pair': ['prim:955d3c17dbbca3346a2e', 'prim:b0c420bf3316e423bc15'], 'pair_index': 3, 'rejection_reasons': ['closure_trap'], 'source_line': 1257} |
| 2026100305 | KAGGLE_WORKER_ERROR; per-seed final manifest unavailable | 12/12 | NOT_RECOVERED | false | NOT_VERIFIED | False | NOT_VERIFIED | true | true | false | NOT_VERIFIED | Gen4: audit=CONSISTENT, observed/expected=10/10, accepted=9/10, rejected=1, closure_traps=0, first_failure={'closure_trap': False, 'macro_pair': ['prim:69e680889385259c198f', 'prim:ca1cc7ea4217a64a7f5d'], 'pair_index': 0, 'rejection_reasons': ['competence_failure'], 'source_line': 1633} |

Runtime seconds is `NOT_RECOVERED`; per-generation primary-invention elapsed seconds are recorded separately and are not full-run runtimes. `generations_completed` counts slots with expected pair count, a pair summary, and closure audit status `CONSISTENT`; it does not mean the scientific slot passed.

## 60-slot disposition table

`closure_reuse_rate = accepted H7_PAIR_OUTCOME count / expected closure_pair_count`; Gen0 has zero closure pairs and is `N/A`. Probe metrics and full selected-lineage checks are not recovered. Selected primary primitive IDs, selected direct parent IDs/generations, and selected recency flags are present for Gen9–Gen11.

| Seed | Gen | closure_pair_count (observed/expected) | closure_reuse_rate | closure_trap_count | probe_reuse_rate | probe_trap_count | lineage_ok | selected_primitive_id | selected_pair_gens | selected_pair_recency_gate_passed | closure audit | slot disposition |
|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|
| 2026100301 | Gen0 | 0/0 | N/A | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100301 | Gen1 | 1/1 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100301 | Gen2 | 3/3 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100301 | Gen3 | 6/6 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100301 | Gen4 | 10/10 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100301 | Gen5 | 15/15 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100301 | Gen6 | 21/21 | 0.762 | 5 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_FAIL |
| 2026100301 | Gen7 | 28/28 | 0.750 | 7 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_FAIL |
| 2026100301 | Gen8 | 36/36 | 0.722 | 9 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_FAIL |
| 2026100301 | Gen9 | 45/45 | 0.778 | 10 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | prim:065c3aa96a4880082e4f | [8, 7] | true | CONSISTENT | CLOSURE_FAIL |
| 2026100301 | Gen10 | 55/55 | 0.800 | 11 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | prim:57877ee3cfe16d604329 | [9, 8] | true | CONSISTENT | CLOSURE_FAIL |
| 2026100301 | Gen11 | 66/66 | 0.818 | 12 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | prim:e6af0dc33fa83097c61e | [9, 10] | true | CONSISTENT | CLOSURE_FAIL |
| 2026100302 | Gen0 | 0/0 | N/A | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100302 | Gen1 | 1/1 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100302 | Gen2 | 3/3 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100302 | Gen3 | 6/6 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100302 | Gen4 | 10/10 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100302 | Gen5 | 15/15 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100302 | Gen6 | 21/21 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100302 | Gen7 | 28/28 | 0.964 | 1 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_FAIL |
| 2026100302 | Gen8 | 36/36 | 0.972 | 1 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_FAIL |
| 2026100302 | Gen9 | 45/45 | 0.822 | 8 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | prim:035e74418793b7f32417 | [8, 5] | true | CONSISTENT | CLOSURE_FAIL |
| 2026100302 | Gen10 | 55/55 | 0.836 | 9 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | prim:708116f57711e783a5ec | [1, 9] | true | CONSISTENT | CLOSURE_FAIL |
| 2026100302 | Gen11 | 66/66 | 0.848 | 10 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | prim:f0dc5b989a5c6fd5a574 | [3, 10] | true | CONSISTENT | CLOSURE_FAIL |
| 2026100303 | Gen0 | 0/0 | N/A | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100303 | Gen1 | 1/1 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100303 | Gen2 | 3/3 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100303 | Gen3 | 6/6 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100303 | Gen4 | 10/10 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100303 | Gen5 | 15/15 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100303 | Gen6 | 21/21 | 0.905 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_FAIL |
| 2026100303 | Gen7 | 28/28 | 0.857 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_FAIL |
| 2026100303 | Gen8 | 28/36 | 0.667 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | INCOMPLETE | AUDIT_INCOMPLETE |
| 2026100303 | Gen9 | 36/45 | 0.711 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | prim:526084bc4aa4cc1c3e9e | [6, 7] | false | INCOMPLETE | AUDIT_INCOMPLETE |
| 2026100303 | Gen10 | 45/55 | 0.727 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | prim:8edeaaa507dac1552ea3 | [5, 9] | true | INCOMPLETE | AUDIT_INCOMPLETE |
| 2026100303 | Gen11 | 55/66 | 0.788 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | prim:e64e55a4a0313b374b4c | [9, 10] | true | INCOMPLETE | AUDIT_INCOMPLETE |
| 2026100304 | Gen0 | 0/0 | N/A | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100304 | Gen1 | 1/1 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100304 | Gen2 | 3/3 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100304 | Gen3 | 6/6 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100304 | Gen4 | 10/10 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100304 | Gen5 | 15/15 | 0.667 | 4 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | INVALID | AUDIT_INVALID |
| 2026100304 | Gen6 | 21/21 | 0.524 | 6 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | INVALID | AUDIT_INVALID |
| 2026100304 | Gen7 | 28/28 | 0.500 | 8 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | INVALID | AUDIT_INVALID |
| 2026100304 | Gen8 | 36/36 | 0.611 | 7 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | INVALID | AUDIT_INVALID |
| 2026100304 | Gen9 | 45/45 | 0.689 | 9 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | prim:2a84f848c0b8d40a5f93 | [8, 4] | true | INVALID | AUDIT_INVALID |
| 2026100304 | Gen10 | 55/55 | 0.655 | 13 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | prim:896bd5f26d68d2d28fa6 | [9, 7] | true | INVALID | AUDIT_INVALID |
| 2026100304 | Gen11 | 66/66 | 0.667 | 13 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | prim:8830ef6c8972d6874cd2 | [8, 10] | true | INVALID | AUDIT_INVALID |
| 2026100305 | Gen0 | 0/0 | N/A | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100305 | Gen1 | 1/1 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100305 | Gen2 | 3/3 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100305 | Gen3 | 6/6 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100305 | Gen4 | 10/10 | 0.900 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_FAIL |
| 2026100305 | Gen5 | 15/15 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100305 | Gen6 | 21/21 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100305 | Gen7 | 28/28 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100305 | Gen8 | 36/36 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | NOT_RECORDED | NOT_RECORDED | n/a | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100305 | Gen9 | 45/45 | 1.000 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | prim:541d38a62c7933cf8f4e | [6, 8] | true | CONSISTENT | CLOSURE_PASS_ONLY |
| 2026100305 | Gen10 | 55/55 | 0.982 | 0 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | prim:29e6dde886689f2c6ffb | [9, 8] | true | CONSISTENT | CLOSURE_FAIL |
| 2026100305 | Gen11 | 66/66 | 0.924 | 4 | NOT_RECOVERED | NOT_RECOVERED | NOT_VERIFIED | prim:315a4b71c4f2ecd61599 | [5, 4] | false | CONSISTENT | CLOSURE_FAIL |

## Earliest failure boundaries

Exact original event lines are stored in `V22_3_KAGGLE_FAILURE_EVENT_LINES_20261025.log` with source line numbers and raw-line SHA-256 hashes. They include primary-invention, target-parent-audit begin, first rejected pair, generation summary where present, and closure AUDIT_END events.

- **Seed 2026100301** — Gen6: audit=CONSISTENT, observed/expected=21/21, accepted=16/21, rejected=5, closure_traps=5, first_failure={'closure_trap': True, 'macro_pair': ['prim:7b9e019ca08c0944c250', 'prim:0fcca8b958c7c756accc'], 'pair_index': 3, 'rejection_reasons': ['closure_trap'], 'source_line': 106}
- **Seed 2026100302** — Gen7: audit=CONSISTENT, observed/expected=28/28, accepted=27/28, rejected=1, closure_traps=1, first_failure={'closure_trap': True, 'macro_pair': ['prim:c8863ee347902ad8a560', 'prim:4c9bbb56a8227388dc10'], 'pair_index': 1, 'rejection_reasons': ['closure_trap'], 'source_line': 541}
- **Seed 2026100303** — Gen6: audit=CONSISTENT, observed/expected=21/21, accepted=19/21, rejected=2, closure_traps=0, first_failure={'closure_trap': False, 'macro_pair': ['prim:82058e1e1f3b884805f0', 'prim:4a5093a8ae2b4487e3e4'], 'pair_index': 4, 'rejection_reasons': ['competence_failure'], 'source_line': 919}
- **Seed 2026100304** — Gen5: audit=INVALID, observed/expected=15/15, accepted=10/15, rejected=5, closure_traps=4, first_failure={'closure_trap': True, 'macro_pair': ['prim:955d3c17dbbca3346a2e', 'prim:b0c420bf3316e423bc15'], 'pair_index': 3, 'rejection_reasons': ['closure_trap'], 'source_line': 1257}
- **Seed 2026100305** — Gen4: audit=CONSISTENT, observed/expected=10/10, accepted=9/10, rejected=1, closure_traps=0, first_failure={'closure_trap': False, 'macro_pair': ['prim:69e680889385259c198f', 'prim:ca1cc7ea4217a64a7f5d'], 'pair_index': 0, 'rejection_reasons': ['competence_failure'], 'source_line': 1633}

## Runtime provenance and completeness
- Parsed JSONL event lines: `1981`; invalid JSON lines: `0`.
- `H7_GENERATION_PAIR_SUMMARY`: `49/60`; `H7_PAIR_OUTCOME`: `1392/1430` expected.
- Closure evaluation states: `7` INVALID slots and `4` INCOMPLETE slots.
- Selected primitive IDs / parent-generation pairs recovered: `15/60`; selected recency flags recovered: `15/15` Gen9–Gen11 slots.
- `run_manifest.json`: `False`; foundry summary: `False`; probe event count: `0`.
- Runtime events exposing `target_access_during_discovery` / `selection_uses_holdout_transfer_ood`: `0` / `0` occurrences.
 - Runtime verification of target isolation, holdout/transfer/OOD exclusion, full selected-lineage closure and executed archive hash: **NOT VERIFIED** because the final manifest/certificates were not recovered.
- Dispatch-time expected embedded archive SHA-256: `802c102ffcd9187c91aafa9cd7e23ef81ff745ad5f32e6dae7d1a9b04b960e28`.

## Downloaded file inventory

| Relative path from $HOME | Bytes | SHA-256 |
|---|---:|---|
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-audit-events.jsonl` | 41147110 | `f5bf54cf4c4e5b8c5b09751d4239be3fc3381098a8e682043956f340f500b674` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100301-generation-00.json` | 1609 | `eb0b65df698dcb172c45a7bf5ac4c353f2d88e568977b300069c3ec2176a3e13` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100301-generation-01.json` | 8176 | `66a0115c48bbe43405695c392744931856f3923823bbb612e5783a21636a3b53` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100301-generation-02.json` | 31897 | `b48547fb8fbf47cbb2bb0c7c3df8d6c721cdaa833d4ab53a0f73c3c971fd770b` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100301-generation-03.json` | 412187 | `c86f99617f1b304c94835c7b56020a88cf3e8b3fce6058241bbc143596551641` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100301-generation-04.json` | 662612 | `e309b3500199f4642ed5df0439098b06d45893a8c7c62c81f248a1e5ca05e757` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100301-generation-05.json` | 631443 | `7a3381984fda0ec1ed8f17b620b570b355a1319e1186b71f9480467d4ec82ad3` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100301-generation-06.json` | 937354 | `bd91d11a0663d1f9a5e162d08eb63d3c549c7611f117c9b512ca6f09238defa7` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100301-generation-07.json` | 1248698 | `d4a705253264fb702dfa1cb2be0f2ff43b7cf0568058cc920c4a9969df4ff615` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100301-generation-08.json` | 1746671 | `95dc3017788d03c4d70d3623104cf85bd071fb99b1b3f682eb0cbfd4c62712a2` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100301-generation-09.json` | 1997112 | `6cc6164b057263b73c204c7673afd9b212169d15b42d2adc8fa1100ffc5e10dc` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100301-generation-10.json` | 2434523 | `2224f7ea01be5c5ec6ca621a9e053d02848b08f7d18e6cde578e24ed15222858` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100301-generation-11.json` | 2175182 | `a7a186526c6c99274fa55ddb54b551127448b73c5829cc11fd29469549374bdf` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100302-generation-00.json` | 1609 | `0dc5c7f6cfa63f6f9a576bff87148bf469882858a36f7699df6a3c088436bbb2` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100302-generation-01.json` | 7437 | `a6a2a26318aede420824e6434994987a8fa8a994cd280c0aaac8dfc8fc33720c` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100302-generation-02.json` | 28747 | `fd25de09b9aceefd965d014c9921b1bbd65bdecc0cfe73ece69b6f9817d25497` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100302-generation-03.json` | 74081 | `c874cda09d66102c4a2f8c9c0ce6eeaa2e5258521a36c5ba4bc46453dfb625b4` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100302-generation-04.json` | 194554 | `4b66530d0280e508789aa2be150162da418f68b4e5b26dc5d960d3c09fc30756` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100302-generation-05.json` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tmp/v22_3_kaggle_out/acsie-h7-v22-3-pair-audits/seed-2026100302-generation-05.json.kaggle-partial` | 62 | `c0bdd9286f9d8621250854a97535f3036d041b87dbf3348e734cee7e0dae23a3` |

## Final disposition

**NOT QUALIFIED — DO NOT PROMOTE.** Earliest closure defects occur by Gen4–Gen7 across all five seeds. Seed 2026100303 has incomplete closure audits for Gen8–Gen11; seed 2026100304 has invalid audits at Gen5–Gen11 due to rejection-reason schema errors. Gen9 recency gate is false for seed 2026100303; Gen11 recency gate is false for seed 2026100305. Probe results, run manifest, target-isolation runtime verification and executed archive hash were not recovered. No 60-slot qualification pass is certified.

# V22.3 Version 3 Kaggle ERROR audit — 2026-10-26

## Verdict

NOT_QUALIFIED — DO NOT PROMOTE. Exactly one status snapshot was performed and it returned KernelWorkerStatus.ERROR. No polling or rerun was performed. All five per-seed tasks nevertheless report COMPLETED, 12/12 generations, return code 0, and no terminal exception. Scientific slot dispositions are PASSED=29, FAILED=27, INCONCLUSIVE=4; every seed fails its seed-level gate.

## Provenance

- Kernel: memorican/acsie-h7-v22-3-frozen-qualification
- Runner SHA-256: e480c5c6df3713e816bfdfd21e1f2956427d1be373d008be119ee6ffb1b57e38 (matches expected build)
- Executed archive SHA-256: 31c11f123ca60a9e21ae5d5036c1e592eba67858cfd6af87cc491a6c3d5d9b1c (matches expected build)
- target_access_during_discovery: false
- `selection_uses_holdout_transfer_ood == false`: **PASS**, derived from all five per-seed components being false (`holdout_used_for_search_selection=false`, `transfer_used_for_search_selection=false`, `ood_used_for_search_selection=false`); the runner preflight also asserted `holdout_transfer_ood_not_used_for_selection=true`. The JSON manifest does not expose that combined result as a single field.
- Frozen plan: seeds [2026100301, 2026100302, 2026100303, 2026100304, 2026100305], 12 generations per seed, 60 slots; pair denominator g*(g+1)/2; source-manifest SHA-256 b3ff47d93a9499be38b4d556d7bbe88e1318024648195a49132a965522f90cc3; terminal_exception=null; promotion DO NOT PROMOTE.
- The global runner log records infrastructure_status=ORCHESTRATION_COMPLETE and reported_completed_seed_generation_slots=56; all five child jobs report COMPLETED 12/12 with return_code=0. KernelWorkerStatus.ERROR is therefore an orchestration/UI-level status that conflicts with the saved child completion record; the outputs contain no terminal exception or captured Python traceback that identifies a platform-level error cause.
- run_manifest.json: 50746 bytes; SHA-256 ee78f4e0344d75ecfe3f7d7a054acf92c8b0e8d40b2d37c5af6caddb4fac8931
- foundry-summary.json: 83113696 bytes; SHA-256 5e70f434e24df921e579381c64c0cf6ba82df4bb22bee74d38ae1d63d13edad8
- 60 generation pair audit JSON files recovered and parseable; all are copied under pair_audits.

## Five-seed master certification: Version 1 evidence vs Version 3

| Seed | V1 execution | V1 generations evidence | V1 runtime s | V1 closure perfect | V1 probe perfect | V1 trap-free | V1 lineage closed | V1 G9/G10/G11 recency | V1 finite gate | V1 recorded traps* | V3 execution | V3 generations | V3 runtime s | V3 closure perfect | V3 probe perfect | V3 trap-free | V3 lineage closed | V3 G9/G10/G11 recency | V3 finite gate | V3 observed traps** |
|---:|---|---:|---:|---|---|---|---|---|---|---:|---|---:|---:|---|---|---|---|---|---|---:|
| 2026100301 | KAGGLE_WORKER_ERROR; per-seed final manifest unavailable | 12/12 | UNRECOVERED | False | NOT_VERIFIED | False | NOT_VERIFIED | PASS/PASS/PASS | NOT_VERIFIED | 54 | SEED_COMPLETED / WORKER_ERROR | 12/12 | 1627.356 | False | False | False | False | PASS/PASS/PASS | False | 123 |
| 2026100302 | KAGGLE_WORKER_ERROR; per-seed final manifest unavailable | 12/12 | UNRECOVERED | False | NOT_VERIFIED | False | NOT_VERIFIED | PASS/PASS/PASS | NOT_VERIFIED | 29 | SEED_COMPLETED / WORKER_ERROR | 12/12 | 368.916 | False | False | False | False | FAIL/PASS/PASS | False | 46 |
| 2026100303 | KAGGLE_WORKER_ERROR; per-seed final manifest unavailable | 8/12 | UNRECOVERED | False | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | FAIL/PASS/PASS | NOT_VERIFIED | 0 + audit gaps/invalid slots | SEED_COMPLETED / WORKER_ERROR | 12/12 | 453.871 | False | False | False | False | FAIL/PASS/PASS | False | 80 |
| 2026100304 | KAGGLE_WORKER_ERROR; per-seed final manifest unavailable | 5/12 | UNRECOVERED | False | NOT_VERIFIED | False | NOT_VERIFIED | PASS/PASS/PASS | NOT_VERIFIED | 60 + audit gaps/invalid slots | SEED_COMPLETED / WORKER_ERROR | 12/12 | 376.892 | False | False | False | False | PASS/PASS/PASS | False | 133 |
| 2026100305 | KAGGLE_WORKER_ERROR; per-seed final manifest unavailable | 12/12 | UNRECOVERED | False | NOT_VERIFIED | False | NOT_VERIFIED | PASS/PASS/FAIL | NOT_VERIFIED | 4 | SEED_COMPLETED / WORKER_ERROR | 12/12 | 472.401 | False | True | False | False | PASS/PASS/FAIL | False | 36 |

* Version 1 trap numbers are recorded counts from the saved slot rows, not a fully certified total: seed 0303 Gen8-11 has four missing pair-audit files, and seed 0304 Gen5-11 has seven INVALID audit slots. The 60 recorded in those invalid seed-0304 rows remain diagnostics, not a valid seed-level pass. The V1 records sum to 147 closure traps, while the complete-denominator total remains unverified.
** Version 3 totals sum trap-positive closure rows across generations: 418 observed traps. The four incomplete slots in seed 0303 have 38 required pair outcomes absent; total traps over the full denominator could be higher.

## Exact false predicates for OPEN_ENDED_SELF_EXTENDING_GATE

Source gate is a conjunction: 12 generations returned; every generation accepted; lineage closed; every closure perfect; every probe perfect; Gen9/10/11 recency each true; strict growth; depth-growth contract; retained count >= 12; target depth grows from bootstrap; final probe success and reuse each 1.0; final closure pair count >= 6; final closure success and reuse each 1.0; zero closure/probe traps at every generation; final baseline_accepted is false.

- Seed 2026100301: false predicates = lineage_closed, every_closure_perfect, every_probe_perfect, final_closure_reuse_is_1, zero_traps_all_generations.
- Seed 2026100302: false predicates = lineage_closed, every_closure_perfect, every_probe_perfect, Gen9_10_11_recency_all_pass, final_probe_reuse_is_1, final_closure_reuse_is_1, zero_traps_all_generations.
- Seed 2026100303: false predicates = every_generation_accepted, lineage_closed, every_closure_perfect, every_probe_perfect, Gen9_10_11_recency_all_pass, strict_growth, depth_growth_contract, retained_count_at_least_12, final_probe_success_is_1, final_probe_reuse_is_1, final_closure_success_is_1, final_closure_reuse_is_1, zero_traps_all_generations.
- Seed 2026100304: false predicates = lineage_closed, every_closure_perfect, every_probe_perfect, final_probe_success_is_1, final_probe_reuse_is_1, final_closure_reuse_is_1, zero_traps_all_generations.
- Seed 2026100305: false predicates = lineage_closed, every_closure_perfect, Gen9_10_11_recency_all_pass, final_closure_success_is_1, final_closure_reuse_is_1, zero_traps_all_generations.

### Seed 2026100305

It was not a runtime timeout: 12/12 generations completed and the full log ends OPEN_ENDED_SELF_EXTENDING_GATE=FAIL. Gen5 selected prim:6e22731d482440003404 with selected direct-parent generation [0] in the invention event; the generation-summary primary-target pair field is [0,2]. lineage_ok=false, breaking lineage_closed. Gen11 selected prim:315a4b71c4f2ecd61599 with selected direct-parent generations [5,4] in the invention event; the generation-summary primary-target pair field is [0,4]. Recency is false with 66 checks and 56 failures. Final closure reuse is 0.727273 (48/66), with 16 closure traps; every_probe_perfect is true and probe traps are zero. Gen10 proposal and selection were separate: discovery-ranked proposal prim:29e6dde886689f2c6ffb had parent generations [9,8], but post-validation selection accepted prim:b6d64cba2d251406538c with selected direct parents [9,6].

### Seed 2026100303 Gen8

A bounded in-memory stream scan of the remote seed log recovered PRIMARY_PRIMITIVE_INVENTION_COMPLETE for Gen8. The proposed candidate prim:1461faa33862371b6527 was not accepted; acceptance_rejection_reason=TRANSFER_FAILURE, summary stage DISCOVERY_PROPOSAL_PLUS_POST_VALIDATION_SELECTION, and the logged proposed/selected direct parents were prim:7a1f0b1112cc01bfd890 (Gen6) and prim:a0f9e15a97ff7a82441d (Gen2). The candidate summary reports discovery_candidate_count=0 and no alternate invention-candidate list; no alternate generalizable candidate ID is recorded, so one must not be invented. The foundry summary records transfer_error=0.07380682826725142, ood_error=0.4642970733611805, holdout_used_for_selection=false and ood_used_for_selection=false. These are validation diagnostics, not ranking inputs. The generation's closure audit was incomplete at 28/36, with 5 observed traps and observed-only reuse rate 0.714286. Gen9-11 are also incomplete at 36/45, 45/55 and 55/66.

## 60-slot disposition (Version 3)

Rate is reused/observed pairs, shown with observed/required to expose incomplete audits. Trap counts apply to observed pair rows only when the denominator is incomplete. selected_pair_gens is the selected invention event's selected_direct_parent_generations where available; the structured report separately records summary_primary_target_parent_generations. The proposal parent generations may differ from post-validation selected parents: seed 0303 Gen8 proposal/selection parents are [6,2], whereas the summary target pair is [4,5]; seed 0305 Gen10 has proposal parents [9,8] but selected parents [9,6].

| Seed | Gen | Closure pairs observed/required | Closure reuse rate (observed) | Closure traps observed | Probe reuse rate | Probe traps | lineage_ok | selected_primitive_id | selected_pair_gens | recency_gate_passed | Slot disposition |
|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|
| 2026100301 | 0 | 0/0 | N/A | 0 | 1.000 | 0 | True | prim:7b9e019ca08c0944c250 | [] | N/A | PASSED |
| 2026100301 | 1 | 1/1 | 1.000 | 0 | 1.000 | 0 | True | prim:f7ff4c8074f55158c001 | [0] | N/A | PASSED |
| 2026100301 | 2 | 3/3 | 1.000 | 0 | 1.000 | 0 | True | prim:9c37d71e94d0744e366d | [0, 1] | N/A | PASSED |
| 2026100301 | 3 | 6/6 | 1.000 | 0 | 1.000 | 0 | True | prim:73ce8c6b3c2b7b3de053 | [2, 1] | N/A | PASSED |
| 2026100301 | 4 | 10/10 | 1.000 | 0 | 1.000 | 0 | True | prim:0fcca8b958c7c756accc | [3, 2] | N/A | PASSED |
| 2026100301 | 5 | 15/15 | 1.000 | 0 | 1.000 | 0 | True | prim:0bfd752d97fb5edc5e47 | [2, 1] | N/A | PASSED |
| 2026100301 | 6 | 21/21 | 0.762 | 5 | 0.250 | 3 | False | prim:aa76925e4d86255adac4 | [3, 2] | N/A | FAILED |
| 2026100301 | 7 | 28/28 | 0.714 | 8 | 1.000 | 0 | True | prim:80b4d6b5c0f013910807 | [6, 1] | N/A | FAILED |
| 2026100301 | 8 | 36/36 | 0.500 | 17 | 0.750 | 1 | False | prim:7cf9871aa87f7585f1e6 | [7, 1] | N/A | FAILED |
| 2026100301 | 9 | 45/45 | 0.444 | 25 | 1.000 | 0 | True | prim:065c3aa96a4880082e4f | [8, 7] | PASS | FAILED |
| 2026100301 | 10 | 55/55 | 0.382 | 34 | 1.000 | 0 | True | prim:57877ee3cfe16d604329 | [9, 8] | PASS | FAILED |
| 2026100301 | 11 | 66/66 | 0.485 | 34 | 1.000 | 0 | False | prim:e6af0dc33fa83097c61e | [9, 10] | PASS | FAILED |
| 2026100302 | 0 | 0/0 | N/A | 0 | 0.750 | 0 | True | prim:c8863ee347902ad8a560 | [] | N/A | FAILED |
| 2026100302 | 1 | 1/1 | 1.000 | 0 | 1.000 | 0 | True | prim:58f8a853ef5a383209b9 | [0] | N/A | PASSED |
| 2026100302 | 2 | 3/3 | 1.000 | 0 | 1.000 | 0 | True | prim:4c9bbb56a8227388dc10 | [1, 0] | N/A | PASSED |
| 2026100302 | 3 | 6/6 | 1.000 | 0 | 1.000 | 0 | True | prim:11d7afd110a2d44ead43 | [2, 0] | N/A | PASSED |
| 2026100302 | 4 | 10/10 | 1.000 | 0 | 1.000 | 0 | True | prim:c4b6174ba9a4c1e815f8 | [3, 1] | N/A | PASSED |
| 2026100302 | 5 | 15/15 | 1.000 | 0 | 1.000 | 0 | True | prim:d0a2747d8d637dfa42d0 | [3] | N/A | PASSED |
| 2026100302 | 6 | 21/21 | 1.000 | 0 | 1.000 | 0 | True | prim:339fcc177a9cb21bb5f7 | [2, 0] | N/A | PASSED |
| 2026100302 | 7 | 28/28 | 0.964 | 1 | 1.000 | 0 | True | prim:333e6308aa4aa679610d | [1, 0] | N/A | FAILED |
| 2026100302 | 8 | 36/36 | 0.889 | 2 | 1.000 | 0 | True | prim:a7a58ea28ae3d1c92965 | [1, 4] | N/A | FAILED |
| 2026100302 | 9 | 45/45 | 0.756 | 11 | 1.000 | 0 | True | prim:cc9a45b1072662eec6fb | [8, 3] | FAIL | FAILED |
| 2026100302 | 10 | 55/55 | 0.709 | 16 | 0.500 | 2 | True | prim:708116f57711e783a5ec | [1, 9] | PASS | FAILED |
| 2026100302 | 11 | 66/66 | 0.758 | 16 | 0.750 | 1 | False | prim:f0dc5b989a5c6fd5a574 | [3, 10] | PASS | FAILED |
| 2026100303 | 0 | 0/0 | N/A | 0 | 1.000 | 0 | True | prim:82058e1e1f3b884805f0 | [] | N/A | PASSED |
| 2026100303 | 1 | 1/1 | 1.000 | 0 | 1.000 | 0 | True | prim:f68747183b144bb516f2 | [0] | N/A | PASSED |
| 2026100303 | 2 | 3/3 | 1.000 | 0 | 1.000 | 0 | True | prim:a0f9e15a97ff7a82441d | [0, 1] | N/A | PASSED |
| 2026100303 | 3 | 6/6 | 1.000 | 0 | 1.000 | 0 | True | prim:9a83fc72887554d9d99a | [0, 1] | N/A | PASSED |
| 2026100303 | 4 | 10/10 | 1.000 | 0 | 1.000 | 0 | True | prim:aa42494341051e8db19c | [3, 2] | N/A | PASSED |
| 2026100303 | 5 | 15/15 | 1.000 | 0 | 1.000 | 0 | True | prim:4a5093a8ae2b4487e3e | [3] | N/A | PASSED |
| 2026100303 | 6 | 21/21 | 0.857 | 1 | 1.000 | 0 | True | prim:7a1f0b1112cc01bfd890 | [5, 4] | N/A | FAILED |
| 2026100303 | 7 | 28/28 | 0.714 | 6 | 0.750 | 0 | False | prim:8b16be766c884d2478de | [5, 3] | N/A | FAILED |
| 2026100303 | 8 | 28/36 | 0.714 | 5 | 1.000 | 0 | False | prim:1461faa33862371b6527 (rejected) | [6, 2] | N/A | INCONCLUSIVE / AUDIT_INCOMPLETE |
| 2026100303 | 9 | 36/45 | 0.528 | 13 | 1.000 | 0 | True | prim:526084bc4aa4cc1c3e9e | [6, 7] | FAIL | INCONCLUSIVE / AUDIT_INCOMPLETE |
| 2026100303 | 10 | 45/55 | 0.400 | 23 | 1.000 | 0 | True | prim:8edeaaa507dac1552ea3 | [5, 9] | PASS | INCONCLUSIVE / AUDIT_INCOMPLETE |
| 2026100303 | 11 | 55/66 | 0.382 | 32 | 0.500 | 0 | True | prim:e64e55a4a0313b374b4c | [9, 10] | PASS | INCONCLUSIVE / AUDIT_INCOMPLETE |
| 2026100304 | 0 | 0/0 | N/A | 0 | 1.000 | 0 | True | prim:955d3c17dbbca3346a2e | [] | N/A | PASSED |
| 2026100304 | 1 | 1/1 | 1.000 | 0 | 1.000 | 0 | True | prim:3ae721d99fcfec3233e4 | [0] | N/A | PASSED |
| 2026100304 | 2 | 3/3 | 1.000 | 0 | 1.000 | 0 | True | prim:11f231ee482f84f68b7f | [1, 0] | N/A | PASSED |
| 2026100304 | 3 | 6/6 | 1.000 | 0 | 1.000 | 0 | True | prim:886d849d920dc7d92ca2 | [1, 0] | N/A | PASSED |
| 2026100304 | 4 | 10/10 | 0.700 | 3 | 1.000 | 0 | True | prim:b0c420bf3316e423bc15 | [3] | N/A | FAILED |
| 2026100304 | 5 | 15/15 | 0.467 | 8 | 0.500 | 2 | False | prim:9f30333819569f9b1d9d | [3, 0] | N/A | FAILED |
| 2026100304 | 6 | 21/21 | 0.524 | 10 | 0.500 | 2 | True | prim:d394afe207ca666805eb | [2, 3] | N/A | FAILED |
| 2026100304 | 7 | 28/28 | 0.429 | 16 | 1.000 | 0 | True | prim:55bba19d9fd31208aea3 | [0, 4] | N/A | FAILED |
| 2026100304 | 8 | 36/36 | 0.444 | 20 | 0.750 | 1 | False | prim:620296ed662a7160e1a1 | [3, 4] | N/A | FAILED |
| 2026100304 | 9 | 45/45 | 0.489 | 23 | 0.500 | 2 | True | prim:2a84f848c0b8d40a5f93 | [8, 4] | PASS | FAILED |
| 2026100304 | 10 | 55/55 | 0.527 | 26 | 1.000 | 0 | False | prim:896bd5f26d68d2d28fa6 | [9, 7] | PASS | FAILED |
| 2026100304 | 11 | 66/66 | 0.591 | 27 | 0.250 | 2 | True | prim:8830ef6c8972d6874cd2 | [8, 10] | PASS | FAILED |
| 2026100305 | 0 | 0/0 | N/A | 0 | 1.000 | 0 | True | prim:69e680889385259c198f | [] | N/A | PASSED |
| 2026100305 | 1 | 1/1 | 1.000 | 0 | 1.000 | 0 | True | prim:ca1cc7ea4217a64a7f5d | [0] | N/A | PASSED |
| 2026100305 | 2 | 3/3 | 1.000 | 0 | 1.000 | 0 | True | prim:7195554b49c72be55e6d | [1] | N/A | PASSED |
| 2026100305 | 3 | 6/6 | 1.000 | 0 | 1.000 | 0 | True | prim:a00ac8dc7c095a30bc5b | [2] | N/A | PASSED |
| 2026100305 | 4 | 10/10 | 1.000 | 0 | 1.000 | 0 | True | prim:c52acbb01d8ea89043f4 | [2, 3] | N/A | PASSED |
| 2026100305 | 5 | 15/15 | 1.000 | 0 | 1.000 | 0 | False | prim:6e22731d482440003404 | [0] | N/A | FAILED |
| 2026100305 | 6 | 21/21 | 1.000 | 0 | 1.000 | 0 | True | prim:6b62ddff0ed76d37fd6e | [3, 4] | N/A | PASSED |
| 2026100305 | 7 | 28/28 | 1.000 | 0 | 1.000 | 0 | True | prim:ebb0187e024f353a658f | [3] | N/A | PASSED |
| 2026100305 | 8 | 36/36 | 0.972 | 0 | 1.000 | 0 | True | prim:d4d380750bf4764d7013 | [7] | N/A | FAILED |
| 2026100305 | 9 | 45/45 | 0.867 | 5 | 1.000 | 0 | True | prim:541d38a62c7933cf8f4e | [6, 8] | PASS | FAILED |
| 2026100305 | 10 | 55/55 | 0.709 | 15 | 1.000 | 0 | True | prim:b6d64cba2d251406538c | [9, 6] | PASS | FAILED |
| 2026100305 | 11 | 66/66 | 0.727 | 16 | 1.000 | 0 | True | prim:315a4b71c4f2ecd61599 | [5, 4] | FAIL | FAILED |

## Harvest limits

Remote output list contained 95 items. The large acsie-h7-v22-3-audit-events.jsonl was skipped. Per-seed log sizes and full remote SHA-256 digests (streamed for 0301 and 0303 without saving those huge logs locally) are recorded below. Seed 0301 local download hit a timeout at 308281344 / 355689793 bytes; its partial local hash is recorded separately in the structured JSON. Full logs 0302, 0304, and 0305 were downloaded locally. All 60 pair-audit JSONs and both main manifests were preserved.

Per-seed log digests:

- Seed 2026100301: 355689793 bytes; SHA-256 d118af5a8b2682ea353b382efe125d6bca94a7f87deba42566a03bb0963e9e11; local full download=False
- Seed 2026100302: 16744196 bytes; SHA-256 507812efdf4990c49e23fc228b2ecb8d221fec44da557abe1b38dafac68f27f6; local full download=True
- Seed 2026100303: 309027928 bytes; SHA-256 da3654b630139d0fde51209b673eb374e4574684ba27a13554b3ca9313f2e77f; local full download=False
- Seed 2026100304: 29740938 bytes; SHA-256 ec5ec5820fa82855efcf778dd90e27e983f33c77e88bcb9a6aac31f5a7af9da9; local full download=True
- Seed 2026100305: 35762585 bytes; SHA-256 3b4bf0259031fa7056bfe1f4c0451757379efe1222b4da20b39653bab31dd369; local full download=True

- Global runner console log: 8678 bytes, SHA-256 9bfa1b37b29ec1cfc867e8e4e17f5e376c750bff55470c3f7307806472db79f3.
- Seed 0301 partial local file: 308281344 bytes; SHA-256 bd09fc175634e5f9f98fc3acf25dad8cb82ac0896e3523bebe146665a7d4cd71; this is not the full remote log hash.

Final disposition: STATUS_SNAPSHOT=KernelWorkerStatus.ERROR; SCIENCE=NOT_QUALIFIED; PROMOTION=DO NOT PROMOTE.

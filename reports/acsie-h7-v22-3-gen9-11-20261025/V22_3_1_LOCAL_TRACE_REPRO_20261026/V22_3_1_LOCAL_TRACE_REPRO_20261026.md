# V22.3.1 Local Trace Reproduction — 2026-10-26

**Disposition: BLOCKED — no Kaggle dispatch. DO NOT PROMOTE.**

## Build and Phase-0

- ACSIE HEAD: ec141c360624d376ac7581a4bdace995ffb227a5
- Runner SHA-256: 4a23250bb03613c337ec311b04c2a1c5294edb47edbfbdf9b76491c57d7ab67b
- Source-manifest SHA-256: a90ef910dc69cd2f1967bfe327548d2f9c11c0dc97ec2f9d7d5d5941fb5aed07
- Embedded archive SHA-256: 7e55b716e74c6d106e4c85e63e81360a2422ca2ec32c1a3b25aadd90ef8bf31e
- Phase-0: PASSED; 38 tests, 0 failures, 4.459 seconds; no qualification slots evaluated; research not started.
- Frozen 5 seeds x 12 generations, 60 slots, full g*(g+1)/2 pair denominator, target access false, no holdout/transfer/OOD selection, private/no internet/no GPU remain unchanged.

## Local trace results

| Seed | Bound | Exit | Generation audits present | Result |
|---|---:|---:|---|---|
| 2026100305 | 25 s | 124 (timeout) | Gen0, Gen1, Gen2 | Gen0: 0/0 pairs; Gen1: 1/1, reuse 1.0000, 0 traps; Gen2: 3/3, reuse 1.0000, 0 traps, 0 competence failures. Gen3-4 not certified. |
| 2026100304 | 25 s | 124 (timeout) | Gen0, Gen1 | Gen0: 0/0 pairs; Gen1: 1/1, reuse 1.0000, 0 traps. Gen2 was still in closure evaluation at timeout. Gen2-4 not certified. |

The required local gate is NOT passed: both seeds did not complete Gen0-4. The combined 0305 run timed out while later generation work continued; a separate 25-second 0304 run timed out during Gen2 closure evaluation. This is an execution timeout, not a pass or a trap verdict for uncompleted generations.

## Exact reproduction: seed 2026100305 Gen2, pair index 1

Current run outcome: closure_trap=false, reuse_ok=true. The lineage-preserving candidate is rank 0 and the old shallow alias is rank 1.

- Rank 0: proc:d7f1616c498ed19b8e50; expression add(macro(prim:69e680889385259c198f), macro(prim:7195554b49c72be55e6d)); used primitives [prim:69e680889385259c198f, prim:7195554b49c72be55e6d]; executable lineage contains prim:69e680889385259c198f, prim:7195554b49c72be55e6d, prim:ca1cc7ea4217a64a7f5d; reuse true, lineage compatible true, competence true.
- Rank 1: proc:c3b1e338ca60d333dc5e; expression add(macro(prim:69e680889385259c198f), macro(prim:ca1cc7ea4217a64a7f5d)); used primitives [prim:69e680889385259c198f, prim:ca1cc7ea4217a64a7f5d]; executable lineage lacks prim:7195554b49c72be55e6d; reuse false for this pair, lineage incompatible false, competence true.

Historical V22.3 audit for this same seed/generation had a closure trap. The new local result is positive for this pair only; it does not certify seed 0305 Gen3-4 or seed 0304 Gen0-4.

## Relevant repairs already committed

- recursive_cognitive_compiler.py: inside the minimal direct-primary-pair tier, rank by descending executable primary-lineage size before unrolled AST depth/node cost. This protects lineage-preserving macros against shallow ancestor aliases. No expected-pair labels, holdout, transfer, or OOD results are inputs.
- acsie_open_ended_self_extending_proving.py: invention and generation-summary records use canonical parent-generation extraction; incomplete pair audits are atomically written and unhandled generation exceptions are recorded.
- run_acsie_h7_v22_3.py: final manifests are written in finally; missing slots are explicitly INCONCLUSIVE; promotion remains locked.

Representative ranking diff:

    - return (minimal_pair_tier, expanded_depth, expanded_nodes, ...)
    + return (minimal_pair_tier, -primary_lineage_size, expanded_depth, expanded_nodes, ...)

## Final gate decision

LOCAL_GATE=BLOCKED_INCOMPLETE; KAGGLE_DISPATCH_PERFORMED=false; QUALIFICATION_STATUS=NOT_QUALIFIED; PROMOTION=DO NOT PROMOTE.

Do not dispatch until both seeds complete Gen0-4 locally with every required pair present, zero closure traps, and zero competence failures. The frozen 60-slot qualification remains undispatched by this action.

## Preserved local pair-audit artifacts

The five completed generation audit JSON files are stored in the adjacent pair_audits directory. SHA-256 values:

| Artifact | SHA-256 |
|---|---|
| seed-2026100305-generation-00.json | 17fc978832f2e4a1c9d5090d1119c6aa9ba0960ab6efd3ab2c22abd12cb8c359 |
| seed-2026100305-generation-01.json | ce66ae17960c3725379fc1bd5d2aa09cebd1fb9e09192e7de7c8106b41755ae2 |
| seed-2026100305-generation-02.json | 3e6ea40b0f0a4720ef2019a16ac7cc2475925e659e7c326b00a1c081d67ae85f |
| seed-2026100304-generation-00.json | a2a7d1f3a300c06de192bd9c4d31c99125fe5d15fc591d1ece7261444a53c2cb |
| seed-2026100304-generation-01.json | 971376251329852f7062a30422dcc5a55f19305216998303a405503f3e425a08 |

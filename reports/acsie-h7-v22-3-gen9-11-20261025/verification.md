# ACSIE H7 V22.3 — Gen9–11 verification report

Generated: 2026-10-25T23:44:01.697153+05:30

## Qualification disposition

- **Evidence result:** all 166 closure pairs accepted, zero closure traps; all 12 probes reused successfully, zero probe traps.
- **Gen11:** 66/66 closure pairs, 4/4 probes, lineage PASS, recency gate PASS for direct parent generations `[9, 10]`.
- **Qualification remains:** `NOT_QUALIFIED`; `DO NOT PROMOTE`. No frozen qualification slots have been evaluated by Kaggle in this evidence report.
- **Scientific gates:** `target_access_during_discovery=false`; holdout/transfer/OOD are not used for selection; no thresholds or denominators changed.

## Per-generation results

| Generation | Selected primitive | Parent generations | Closure reuse | Closure traps | Probe reuse | Probe traps | Lineage | Recency gate |
|---|---|---|---:|---:|---:|---:|---|---|
| Gen9 | `prim:1c9f1097608c3f094303` | `[7, 8]` | 45/45 | 0 | 4/4 | 0 | PASS | PASS |
| Gen10 | `prim:26db1445ec125612c47d` | `[9, 8]` | 55/55 | 0 | 4/4 | 0 | PASS | PASS |
| Gen11 | `prim:1a7f483ad996e0c26f19` | `[9, 10]` | 66/66 | 0 | 4/4 | 0 | PASS | PASS |

## Gen11 pair-index coverage

| Pair indices | Outcome | Evidence granularity |
|---|---|---|
| `0–42` | 43/43 accepted, zero traps | Earlier progress checkpoints (aggregate status only) |
| `43–54` | 12/12 accepted, zero traps | Timed continuation progress checkpoints (aggregate status only) |
| `55–65` | 11/11 accepted, zero traps | Per-pair results persisted by snapshot continuation |
| **Total `0–65`** | **66/66 accepted, zero traps** | Complete index coverage; indices 0–54 lack per-pair synthesis metadata due interrupted earlier runs |

## Gen11 AST finding

- Selected primitive: `prim:1a7f483ad996e0c26f19`; AST depth 4; 11 AST nodes.
- The selected AST is `mul(add(P9, P10), sub(add(P9, P10), mul(P9, P9)))`.
- The proposed S1–S4 AST using `S3 = add(P9, mul(P9, P9))` is recorded as a post-hoc counterfactual, not the selected expression. It is explicitly marked not used for search/selection. The recency gate still passes on direct parent generations `[9, 10]`.

## Runner and provenance hashes

| Artifact | SHA-256 / digest |
|---|---|
| `behavioral_search.py` | `2902d4ec4010220dd1d1ba81eb2706bd9ca069cfe32eb15bcc1afeed66583b0c` |
| `run_acsie_h7_v22_3.py` | `984f3bdc1967c9edbeb4b367eecd0883ab7d8eb11e9cf82a44b36ac128735022` |
| `source-manifest.json_file` | `f51881fe4f81bc63930ecd34b5982db56e73abcf35bb77babc2570ba57af8bc6` |
| `embedded_archive_sha256` | `802c102ffcd9187c91aafa9cd7e23ef81ff745ad5f32e6dae7d1a9b04b960e28` |
| `embedded_source_manifest_sha256` | `5da98c661e020e3a8e699e3958b2eac34a4fd9539d244b7f696a36f6dcf9551d` |
| `build_report.json` | `aab13830be9838fa2fb47c4755cae0003df56b3b8ce898d9e329d577bcd4986b` |
| `ast_lineage_details.json` | `97261ebc02486495b56582a8df69dfa533c4eaa13c725e3742fc1daf79864d08` |
| `gen11_current_result.json` | `9c5f9957e492c65dce46c6cd5defa6f0ea6bd6985a60c9fac3630e8f1c88f1e9` |
| `gen11_snapshot_sha256` | `760c6a811c162694615351e9b803d271221c32cb7c139da44ed4dc7e33b8545f` |
| `gen11_checkpoint_sha256` | `9fa4cdd87ab5039ac6a9bda6e8f65211f1b077622d5a4feb573a30a342c96818` |

Phase-0 check: `PASSED`; regression suite result from saved log: 27 tests, `OK`. The V22.3 runner is private, with GPU and internet disabled and no dataset/kernel sources.

## Evidence limitation

The original bounded Gen11 closure workers timed out before writing a single final per-pair JSON object for indices 0–54. Their durable progress events confirm the exact attempts/accepted totals and zero traps, and indices 43–54 were covered by a second bounded continuation. Thus all 66 statuses are accounted for, but per-pair synthesis metadata for indices 0–54 is not available in this run. This is stated in the combined JSON rather than inventing per-pair fields.

## Status

`DO NOT PROMOTE` remains locked until all 60 frozen seed-generation slots complete and pass on Kaggle.

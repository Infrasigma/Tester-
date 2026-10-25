# ACSIE H7 V22.3 depth-3 recency continuation — status (2026-10-25)

This is a mirrored research receipt for ACSIE PR #115. Canonical implementation and runner are in private `Infrasigma/ACSIE`; no Kaggle run was launched.

## Verified source and local Phase-0

- ACSIE source commit pushed: `2cb1942` (merge integrating remote depth-three patch plus bounded fix).
- `behavioral_search.py` SHA-256: `2902d4ec4010220dd1d1ba81eb2706bd9ca069cfe32eb15bcc1afeed66583b0c`
- V22.3 runner SHA-256: `984f3bdc1967c9edbeb4b367eecd0883ab7d8eb11e9cf82a44b36ac128735022`
- `source-manifest.json` SHA-256: `f51881fe4f81bc63930ecd34b5982db56e73abcf35bb77babc2570ba57af8bc6`
- Embedded source archive SHA-256: `802c102ffcd9187c91aafa9cd7e23ef81ff745ad5f32e6dae7d1a9b04b960e28`
- Source-manifest canonical digest: `5da98c661e020e3a8e699e3958b2eac34a4fd9539d244b7f696a36f6dcf9551d`
- Phase-0: **PASSED, 27/27 tests**; compilation and preflight passed; `research_started=false`; qualification slots evaluated `0`.

## Checkpoint and bounded replay evidence

- Checkpoint was recovered from the existing Termux cache (the Android environment has no writable `/tmp`); copied temporarily to `$HOME/tmp` and SHA-256 verified as `9fa4cdd87ab5039ac6a9bda6e8f65211f1b077622d5a4feb573a30a342c96818`. Temporary copy was removed after use.
- A primary-invention-only replay log emitted accepted Gen9 and Gen10 selections and a Gen11 selection with direct parent generations `[9,10]` and `selected_pair_recency_gate_passed=true`. Per-generation runtimes in that trace: Gen9 `1.018299s`, Gen10 `3.562761s`, Gen11 `15.495962s`.
- The compact ACSIE evidence explicitly records that selected expressions/AST depths and the exact S1–S4 retained-state trace were **not independently captured**. Do not infer these from the algebraic counterfactual.
- Gen11-only closure/probe verification was launched with a hard `timeout 120s`, limited to Gen11's 66 closure pairs and four probes. Its final JSON/result was not confirmed in this receipt; do not claim 66/66 closure or 4/4 probe success.

## Frozen scientific disposition

**H7 UNRESOLVED / NOT QUALIFIED / DO NOT PROMOTE.** No frozen thresholds, denominators, seed/generation slots, or selection-data boundaries changed. No full 5-seed × 12-generation qualification run was launched.

# ACSIE H7 V22.3 scoped Gen11 recency continuation — status (2026-10-25)

This is a mirrored research receipt for ACSIE PR #115. Canonical implementation and runner are in private `Infrasigma/ACSIE`.

## Algebraic witness (counterfactual, not selected)

Let `B0 = max(abs(z), max(y,z))`. Then `H9 = B0`, `H10 = 2*B0^2`, `H3 = B0^2+B0`, and `H4 = 2*B0^2+B0`. Therefore `(H9+H10)*(H9+H9^2) = H4*H3` globally. The expression has AST depth 4 and direct parent generations `[9,10]`, so it satisfies the Gen11 recency predicate when represented using the retained primary macro IDs. This proves existence, not discovery or selection.

## Rebuild and Phase-0

- ACSIE commit: `ba0acf4` (`h7: scope Gen11 recency continuation and rebuild V22.3`)
- Runner SHA-256: `8b4e0d20dc26e6474bf959c8a5e400d18a6be1629920cf7e660933f312d6a96a`
- Embedded source archive SHA-256: `9e77cbb638251d58d53e455521395834864a42da0b8563a92b2671a5848b3f2d`
- Source-manifest canonical digest: `8a2d6b301fa4c4041c3731803c11454c7b11f1609a264422db52ad93eb47f503`
- Source-manifest file SHA-256: `e537f7059390bd9203bec20746a586e997c41aa5d901687377d0604cb6038017`
- Phase-0: **PASSED, 27/27 tests**, 2.095 seconds; compilation and preflight passed.
- Qualification slots evaluated: `0`; `research_started=false`; no Kaggle kernel was launched.

## Replay limitation and frozen disposition

The available primary-invention-only replay artifact predates this rebuild and recorded 111.749424 seconds, zero recency-eligible Gen11 candidates, and stale selected direct parents `[8,3]`. It is not post-fix verification. No completed post-rebuild Gen9–11 replay, Gen11 acceptance check, 66/66 closure replay, or 4/4 probe replay is claimed.

**H7 UNRESOLVED / NOT QUALIFIED / DO NOT PROMOTE.** No frozen thresholds, denominators, seed/generation slots, or selection-data boundaries changed. The candidate-spec cap path was also corrected to pass the recency-priority callback and depth-4 preservation bound before truncation; the final rebuilt runner then passed Phase-0 again.

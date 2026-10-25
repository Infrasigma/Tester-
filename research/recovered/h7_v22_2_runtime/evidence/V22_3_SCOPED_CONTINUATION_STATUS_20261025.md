# ACSIE H7 V22.3 scoped Gen11 recency continuation — status (2026-10-25)

This is a mirrored research receipt for ACSIE PR #115. Canonical implementation and runner are in private `Infrasigma/ACSIE`.

## Algebraic witness (counterfactual, not selected)

Let `B0 = max(abs(z), max(y,z))`. Then `H9 = B0`, `H10 = 2*B0^2`, `H3 = B0^2+B0`, and `H4 = 2*B0^2+B0`. Therefore `(H9+H10)*(H9+H9^2) = H4*H3` globally. The expression has AST depth 4 and direct parent generations `[9,10]`, so it satisfies the Gen11 recency predicate when represented using the retained primary macro IDs. This proves existence, not discovery or selection.

## Rebuild and Phase-0

- ACSIE commit: `ba0acf4` (`h7: scope Gen11 recency continuation and rebuild V22.3`)
- Runner SHA-256: `bc92065af7dea6d1f29b96e72a13adadd1ea8f4d3bebec39b9ce25b9a683323f`
- Embedded source archive SHA-256: `17fd2e99e1fb0e84fd8c2227f8e6b77b9dbd9ddb31935500d76935c1edd80043`
- Source-manifest canonical digest: `1a35d9cad39dd9fa73bae4277386ab77ef53d6f74bd3392a2f60afffb6844bbe`
- Source-manifest file SHA-256: `d62d862d6ba0e756c860b1dc790eb03d06e6e6338e2db9fc1d34e3393da4bb07`
- Phase-0: **PASSED, 27/27 tests**, 2.095 seconds; compilation and preflight passed.
- Qualification slots evaluated: `0`; `research_started=false`; no Kaggle kernel was launched.

## Replay limitation and frozen disposition

The available primary-invention-only replay artifact predates this rebuild and recorded 111.749424 seconds, zero recency-eligible Gen11 candidates, and stale selected direct parents `[8,3]`. It is not post-fix verification. No completed post-rebuild Gen9–11 replay, Gen11 acceptance check, 66/66 closure replay, or 4/4 probe replay is claimed.

**H7 UNRESOLVED / NOT QUALIFIED / DO NOT PROMOTE.** No frozen thresholds, denominators, seed/generation slots, or selection-data boundaries changed.

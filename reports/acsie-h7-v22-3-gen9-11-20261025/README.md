# ACSIE H7 V22.3 Gen9–11 verification receipt

Mirrored from `Infrasigma/ACSIE` PR #115 for cross-repository review. This is evidence-only: qualification is `NOT_QUALIFIED` and promotion remains `DO NOT PROMOTE`.

The combined report reconciles Gen9 45/45, Gen10 55/55, Gen11 66/66 closure reuse and 12/12 probe reuse, all with zero recorded traps. Gen11 closure indices 0–54 have aggregate-only durable progress evidence because the initial bounded workers stopped before serializing individual rows; indices 55–65 have per-pair results. See `verification.md` and its matching JSON for the limitation and provenance hashes. Phase-0 tests passed (27 tests); no frozen Kaggle qualification slots were run by these checks.

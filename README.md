# Tester-

Public infrastructure and workflow-template repository for Infrasigma research.

## Responsibility split

- **Private `Infrasigma/ACSIE`:** authoritative source and canonical scientific record—hypotheses, experiment definitions, claims, provenance, per-seed/per-generation results, failures, and compact research receipts.
- **Kaggle:** remote research execution plus private, versioned storage for large logs, outputs, and checkpoint bundles when they are too bulky for reviewable ACSIE records.
- **Tester- (this repository):** non-sensitive orchestration code, reusable workflow patterns, and infrastructure diagnostics only.
- **Termux/Android:** control/relay only; not a compute worker, data cache, or artifact staging location.

See the corresponding private ACSIE policy in `research/REMOTE_RESEARCH_STORAGE_POLICY.md`.

## Public-repository safety

This repository is public. Treat **all source, workflow files, logs, job summaries, caches, and uploaded workflow artifacts** as public-facing. Do not put credentials, private ACSIE source/data, raw experiment outputs, hidden evaluation inputs, checkpoints, or private artifact contents here.

Use encrypted, least-privilege secrets only where they are explicitly required. Never print or serialize credential values. A public workflow's default `GITHUB_TOKEN` must not be assumed to authorize checkout of the private ACSIE repository; configure and verify a dedicated, narrowly scoped credential when cross-repository read access is required. Do not expose secrets to untrusted pull-request code.

## Existing workflow caveat

`.github/workflows/gen3-learning-rule-foundry-parallel.yml` is an older research-run workflow, not a private-data storage contract. It uploads seed evidence and an aggregate JSON as artifacts on this public repository, and it uses `${{ github.token }}` for a private ACSIE checkout. Treat it as **not approved for private ACSIE research runs** until private-source authentication is explicitly verified and its evidence/log route is moved to private storage or reduced to deliberately sanitized public metadata. Do not use its green status as scientific qualification.

## Scientific-status discipline

Infrastructure success proves only that infrastructure ran. Preserve `PASSED`, `FAILED`, `BLOCKED`, `CRASHED`, `INVALID`, and `INCONCLUSIVE` distinctions. Never promote research claims based on workflow success, a benchmark-only result, or artifact existence.

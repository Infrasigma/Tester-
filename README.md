# Tester-

Public infrastructure and workflow-template repository for Infrasigma research.

## Responsibility split

- **Private ACSIE:** authoritative scientific source, gate definitions, provenance, per-seed/per-generation outcomes, failures, and compact receipts.
- **Kaggle:** remote research execution and private, versioned kernel output / dataset storage for bulky artifacts.
- **Tester- (this public repository):** non-sensitive orchestration code only. Workflows check out private ACSIE source at dispatch time and submit it to a private Kaggle kernel; private research source and outputs are not committed or uploaded as GitHub Actions artifacts here.
- **Termux/Android:** control and relay only. Do not clone/cache the research tree, download datasets, stage logs, or retain checkpoints on the phone.

## Gen3 Foundry dispatch

The workflow at .github/workflows/gen3-learning-rule-foundry-parallel.yml is manual-only. It requires these Tester- repository secrets:

- ACSIE_READ_TOKEN: fine-grained credential with Contents: read on only Infrasigma/ACSIE.
- KAGGLE_API_TOKEN: a Kaggle API access token used only to submit the private kernel.

A secret stored on ACSIE is not automatically available to workflows running in Tester-. The workflow stages only Python source files into a private Kaggle kernel, keeps kernel internet disabled, and uploads no seed evidence, checkpoints, logs, or aggregate research results as public GitHub artifacts.

Kaggle kernel metadata is committed at kernel-metadata.json; the public payload contains only the runner and metadata. The actual private ACSIE source snapshot is fetched during the manual workflow and sent to memorican/acsie-gen3-foundry.

Scientific gate caveat: the currently pinned research/gen3_learning_rule_foundry_v1.py performs one Foundry run per seed and does not expose an explicit 12-generation checkpoint interface. run_kaggle_foundry.py preserves the five-seed diagnostic outcomes, records the missing generation coverage, and labels the frozen 5-seed x 12-generation qualification INCONCLUSIVE. It must not be treated as a qualification run or promoted.

## Private receipt tooling

The workflow at .github/workflows/validate-acsie-receipt-tooling.yml is manual-only and checks out a selected ACSIE ref using secrets.ACSIE_READ_TOKEN. The exact workflow binding maps ACSIE_READ_TOKEN from the same-named Actions secret for both its preflight and checkout token. The secret must be configured in Tester- Settings > Secrets and variables > Actions, scoped read-only to private ACSIE. The workflow tests synthetic fixtures only.

## Public-repository safety

Treat workflow files, logs, job summaries, caches, and any uploaded artifacts here as public-facing. Never put credentials, private ACSIE source/data, raw experiment outputs, hidden evaluation inputs, checkpoints, or private artifact contents here. Never print or serialize credential values. No secrets are exposed to pull-request code because the research dispatcher is manual-only.

## Scientific-status discipline

Infrastructure success proves only that infrastructure ran. Preserve PASSED, FAILED, BLOCKED, CRASHED, INVALID, and INCONCLUSIVE distinctions. Never promote research claims based on workflow success, benchmark-only results, or artifact existence.

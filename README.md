# Tester-

Public infrastructure and workflow-template repository for Infrasigma research.

## Responsibility split

- **Private ACSIE:** authoritative source, research protocol, provenance, per-seed/per-generation outcomes, failure records, and compact receipts.
- **Kaggle:** isolated research execution and versioned private datasets/kernel output for bulky artifacts.
- **Tester-:** public orchestration code only. Private ACSIE source is checked out during a hosted workflow run; it is sent to a private Kaggle kernel and is not committed to this repository. Raw experiment outputs and checkpoints are not uploaded as GitHub Actions artifacts.
- **Termux/Android:** control and low-volume receipt retry only. Do not clone the research repository, download checkpoint bundles, or retain logs/datasets on the phone.

## Required repository secrets

Add these secrets in **Tester- → Settings → Secrets and variables → Actions**:

- `ACSIE_READ_TOKEN`: fine-grained PAT scoped only to `Infrasigma/ACSIE`, with **Contents: Read and write** for the end-to-end pipeline. Checkout and tests need read access, but receipt publication and the archive retry require write access to the ACSIE working branch. A read-only token will run the synthetic preflight but cannot publish receipts.
- `KAGGLE_API_TOKEN`: the Kaggle token used by the hosted runner. A secret stored in ACSIE is not visible to Tester-. The credential helper accepts a current `KGAT_...` bearer token, a JSON payload with `username` and `key`, or a legacy key paired with the Kaggle owner `memorican`. Do not put the token into a workflow file, command line, issue, log, or phone-side file.

Credentials are consumed on GitHub-hosted runners; the Kaggle CLI and research data are not installed or stored in Termux.

## Branch-only workflow controls

Changes stay on `work/public-infra-contract-20261023` and `work/research-data-routing-20261023`; do not merge to either `main` branch without separate scientific and security review.

The workflows are also reachable before merging by changing the non-secret one-shot config file:

`scripts/acsie-foundry-run-config.json`

For a Foundry run, set `foundry_dispatch.enabled` to `true` and provide the ACSIE ref. For receipt-only recovery, leave that flag false and set `receipt_ingest.enabled` to `true`, with the exact kernel slug, positive kernel version, private dataset slug, and target working branch. **Enable only one flag at a time.** Commit the config change to the working branch. The workflow resets the flag after a push-triggered attempt so a later commit does not accidentally repeat it. A disabled config push runs no Kaggle job.

The Foundry workflow resolves the requested ACSIE revision through the GitHub API, verifies the Git blob hashes while staging only Python source, records the exact source SHA and a unique dispatch nonce inside the private Kaggle payload, and pushes a private kernel with internet disabled. Public job logs show staging status and file counts, not the private ACSIE SHA or source contents. The hosted runner waits for that kernel version, downloads its JSON output, validates a 5-seed × 12-generation manifest, creates/versions a private Kaggle Dataset, downloads its files back for independent SHA-256 rechecks, and only then attempts to write a compact receipt and provenance records to ACSIE. Logs are limited to stage/status and structural counts; heavy artifacts remain on the hosted runner during transfer and in private Kaggle storage after completion.

Default private archive slug: `memorican/acsie-foundry-checkpoints` (matches the current `memorican/acsie-gen3-foundry` kernel owner). If your Kaggle workspace uses a different owner slug, set the Tester- repository variable `ACSIE_FOUNDRY_DATASET_SLUG` or update the non-secret workflow/config values before running. The archive workflow rejects a dataset when its privacy cannot be confirmed as private.

## Termux receipt retry

`scripts/publish_from_termux.sh <run_id> [target_branch]` is a small retry path **after** the hosted publisher has already verified and committed the candidate, manifest, and archive attestation under `research/archive-attestations/<run_id>/` in ACSIE. It downloads only those small JSON files plus the two Python validator files, runs the receipt checks, and publishes via the GitHub CLI session. It does not use Kaggle credentials, clone a repo, fetch checkpoints, or download the private dataset; the script enforces a temporary workspace below 5 MiB. GitHub CLI authentication must have Contents: write for the target ACSIE working branch.

This Termux wrapper cannot create or verify the heavy dataset archive on the phone. If the private Dataset has not yet been created and rechecked by the hosted workflow, rerun the hosted archive workflow instead.

## Mount-free private Kaggle packaging

For direct Termux-to-Kaggle dispatches, run
`scripts/build_embedded_kaggle_kernel.py` after the private ACSIE source blobs
have been verified and the archive's `source-manifest.json` has the current
dispatch nonce. It creates a **transient deployment folder** containing only
`run_kaggle_foundry.py` and `kernel-metadata.json`, so Kaggle does not need
to mount a private source dataset. The generated runner checks the embedded
archive SHA-256 before safe extraction under Kaggle's working directory.

The builder checks the supplied SHA-256 against the exact archive bytes,
verifies the required source files and rejects unsafe archive paths, refuses
metadata that is not private or that enables internet/GPU, sets
`dataset_sources: []`, and requires the title slug to agree with the kernel ID.
Compute the digest only after verifying the source blobs against the private
ACSIE commit; the digest binds the exact packaged bytes but does not replace
those source-blob checks.

Example (run only in a controlled private staging environment after source-blob
verification; `$TEMPLATE_DIR` contains the complete package, source manifest,
runner, and kernel metadata):

```bash
set -euo pipefail
SOURCE_ARCHIVE="$TMPDIR/acsie-gen3-foundry-package.tar.gz"
tar -czf "$SOURCE_ARCHIVE" --exclude=kernel-metadata.json --exclude=__pycache__ --exclude='*.pyc' -C "$TEMPLATE_DIR" .
ARCHIVE_SHA256="$(sha256sum "$SOURCE_ARCHIVE" | awk '{print $1}')"

python3 scripts/build_embedded_kaggle_kernel.py \
  --template-dir "$TEMPLATE_DIR" \
  --source-archive "$SOURCE_ARCHIVE" \
  --output-dir "$TMPDIR/acsie-gen3-embedded-kernel" \
  --expected-sha256 "$ARCHIVE_SHA256" \
  --kernel-id memorican/acsie-gen3-foundry \
  --title "ACSIE Gen3 Foundry" \
  > "$TMPDIR/embedded-kernel-build.json"

python3 - "$TMPDIR/embedded-kernel-build.json" <<'PY'
import json, sys
result = json.load(open(sys.argv[1], encoding="utf-8"))
assert result.get("build_status") == "PASSED"
assert result.get("dataset_sources_count") == 0
assert result.get("expanded_source_files_in_output") == 0
assert result.get("is_private") is True
assert result.get("enable_internet") is False and result.get("enable_gpu") is False
print("KAGGLE_PAYLOAD_STAGED=PRIVATE_EMBEDDED_SOURCE_NO_DATASET_MOUNT")
PY

python3 scripts/poll_kaggle_kernel.py \
  --kernel-slug memorican/acsie-gen3-foundry \
  --path "$TMPDIR/acsie-gen3-embedded-kernel" \
  --dispatch-nonce "$DISPATCH_NONCE" \
  --timeout-minutes 300
```

**Never commit or publish the generated output directory or its runner.** The
generated runner embeds the private ACSIE archive as base64, so that output is
sensitive even though it is a single Python file. Commit only the generic
builder and its synthetic tests to this public repository. Keep the archive,
the embedded runner, real source hashes where restricted, and all experimental
outputs in private storage. The builder does not replace remote Phase 0 tests,
the scientific gate, run-output hashing, or provenance review.

## Scientific status and promotion

The Foundry source now has a deterministic state-carrying `run_generations(seed, generations=12)` driver. Generations execute sequentially as `0 → 1 → … → 11`: each generation evaluates a bounded mutated candidate population on inner forward/reverse streams, selects using those inner metrics only, writes a checkpoint, and passes the selected rule plus learned core state to the next generation. Outer holdout/transfer and legacy retention are measured after the loop, not used for per-generation selection. A broken precondition yields explicit `FAILED`/ `BLOCKED` rows; exceptions are `CRASHED`. The 5 × 12 matrix is structural coverage, not proof of success.

No qualifying Kaggle run has been observed merely because these files exist. Preserve `PASSED`, `FAILED`, `BLOCKED`, `CRASHED`, `INVALID`, and `INCONCLUSIVE`; one non-passing seed/generation blocks the frozen qualification. AGI/ASI/general capability remains **NOT_DEMONSTRATED** and promotion remains **DO NOT PROMOTE** until actual evidence passes the frozen gate.

## Public repository safety

Treat workflow files, logs, job summaries, and caches as public-facing. Never place credentials, private ACSIE source/data, raw experimental output, hidden evaluation inputs, checkpoint contents, or private artifact contents in this repository or its public logs. Do not use workflow-green status, benchmark-only results, or artifact existence to promote scientific claims.

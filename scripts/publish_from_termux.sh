#!/data/data/com.termux/files/usr/bin/bash
# Lightweight retry path for receipt publication after a hosted runner has already
# archived the kernel output into the private Kaggle Dataset and committed the
# verified candidate/manifest/attestation to the ACSIE working branch.
#
# It intentionally does NOT install Kaggle CLI, clone a repository, or download
# checkpoint bundles. Total temporary storage is enforced below 5 MiB.
set -euo pipefail
umask 077

RUN_ID="${1:-}"
TARGET_BRANCH="${2:-work/research-data-routing-20261023}"
REPOSITORY="Infrasigma/ACSIE"

if [[ -z "$RUN_ID" || ! "$RUN_ID" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$ ]]; then
  echo "TERMUX_PUBLISH_FAILED: supply a safe run_id from a completed private archive run." >&2
  exit 2
fi
if [[ "$TARGET_BRANCH" == "main" || ! "$TARGET_BRANCH" =~ ^[A-Za-z0-9._/-]+$ ]]; then
  echo "TERMUX_PUBLISH_FAILED: target must be a non-main ACSIE working branch." >&2
  exit 2
fi
for command in gh python3; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "TERMUX_PUBLISH_FAILED: missing required command $command." >&2
    exit 2
  }
done
gh auth status >/dev/null 2>&1 || {
  echo "TERMUX_PUBLISH_FAILED: GitHub CLI is not authenticated." >&2
  exit 2
}

WORK="$(mktemp -d "${TMPDIR:-/tmp}/acsie-receipt.XXXXXX")"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT INT TERM
mkdir -p "$WORK/research"

fetch_file() {
  local remote_path="$1"
  local output_path="$2"
  local response="$WORK/contents-response.json"
  if ! gh api "repos/$REPOSITORY/contents/$remote_path?ref=$TARGET_BRANCH" > "$response" 2>/dev/null; then
    echo "TERMUX_PUBLISH_FAILED: required archived provenance was not found on the selected ACSIE branch." >&2
    return 2
  fi
  python3 - "$response" "$output_path" <<'PY'
import base64, json, os, sys
response, output = sys.argv[1:]
data = json.loads(open(response, "r", encoding="utf-8").read())
if data.get("encoding") != "base64" or not isinstance(data.get("content"), str):
    raise SystemExit(2)
raw = base64.b64decode(data["content"], validate=False)
if len(raw) > 1024 * 1024:
    raise SystemExit(2)
os.makedirs(os.path.dirname(output), exist_ok=True)
with open(output, "wb") as handle:
    handle.write(raw)
PY
}

fetch_file "research/archive-attestations/$RUN_ID/receipt-candidate.json" "$WORK/receipt-candidate.json"
fetch_file "research/archive-attestations/$RUN_ID/artifact_manifest.json" "$WORK/artifact_manifest.json"
fetch_file "research/archive-attestations/$RUN_ID/archive-attestation.json" "$WORK/archive-attestation.json"
fetch_file "research/emit_validated_receipt.py" "$WORK/research/emit_validated_receipt.py"
fetch_file "research/validate_remote_receipts.py" "$WORK/research/validate_remote_receipts.py"

python3 - "$WORK/receipt-candidate.json" "$WORK/archive-attestation.json" > "$WORK/archive-values.txt" <<'PY'
import json, sys
candidate = json.load(open(sys.argv[1], encoding="utf-8"))
attestation = json.load(open(sys.argv[2], encoding="utf-8"))
execution = candidate.get("execution", {})
values = (
    execution.get("kernel_slug"),
    attestation.get("kernel_version"),
    attestation.get("dataset_slug"),
    attestation.get("dataset_version"),
)
if (not isinstance(values[0], str) or not isinstance(values[1], int)
        or not isinstance(values[2], str) or not isinstance(values[3], int)
        or attestation.get("visibility") != "private"
        or attestation.get("current_version_verified") is not True
        or attestation.get("all_file_sha256_rechecked") is not True):
    raise SystemExit(2)
print(*values)
PY
if [[ $? -ne 0 ]]; then
  echo "TERMUX_PUBLISH_FAILED: archived kernel/dataset attestation is incomplete." >&2
  exit 2
fi
read -r KERNEL_SLUG KERNEL_VERSION DATASET_SLUG DATASET_VERSION < "$WORK/archive-values.txt"

usage_kib="$(du -sk "$WORK" | awk '{print $1}')"
if [[ ! "$usage_kib" =~ ^[0-9]+$ || "$usage_kib" -ge 5120 ]]; then
  echo "TERMUX_PUBLISH_FAILED: temporary metadata workspace exceeded 5 MiB." >&2
  exit 2
fi

# GITHUB_TOKEN is passed only to the child process in memory; it is not echoed or
# written to disk. The authenticated GitHub CLI session must have Contents: write
# access for this ACSIE branch. Heavy dataset files are never downloaded to Termux.
GITHUB_TOKEN="$(gh auth token)" PYTHONPATH="$WORK" python3 "$WORK/research/emit_validated_receipt.py" \
  --input "$WORK/receipt-candidate.json" \
  --artifact-root "$WORK" \
  --manifest "$WORK/artifact_manifest.json" \
  --archive-attestation "$WORK/archive-attestation.json" \
  --dataset-slug "$DATASET_SLUG" \
  --dataset-version "$DATASET_VERSION" \
  --kernel-slug "$KERNEL_SLUG" \
  --kernel-version "$KERNEL_VERSION" \
  --target-branch "$TARGET_BRANCH" \
  --output "$WORK/validated-receipt.json" \
  --publish

receipt_bytes="$(wc -c < "$WORK/validated-receipt.json" | tr -d ' ')"
if [[ ! "$receipt_bytes" =~ ^[0-9]+$ || "$receipt_bytes" -ge 51200 ]]; then
  echo "TERMUX_PUBLISH_FAILED: compact receipt is not under 50 KiB." >&2
  exit 2
fi
echo "TERMUX_PUBLISH_SUCCEEDED: receipt_bytes=$receipt_bytes temp_kib=$usage_kib dataset=private."

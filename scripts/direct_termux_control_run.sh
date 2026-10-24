#!/usr/bin/env bash
# Direct Termux control path: test -> private embedded Kaggle kernel ->
# output validation -> private checkpoint archive -> validated receipt.
# No GitHub Actions or hosted compute is used.
set -Eeuo pipefail
set +x
umask 077
export PATH="$HOME/.local/bin:$PATH"
hash -r

RECOVERY="$HOME/acsie-recovery"
ACSIE="$RECOVERY/ACSIE"
TESTER="$RECOVERY/Tester-"
ACSIE_BRANCH="work/research-data-routing-20261023"
TESTER_BRANCH="work/public-infra-contract-20261023"
V3_KERNEL="memorican/acsie-gen3-foundry-embedded-source"
BASE_KERNEL="memorican/acsie-gen3-foundry-fast"
CHECKPOINT_DATASET="memorican/acsie-foundry-checkpoints"

for cmd in git python3 kaggle gh tar sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "BLOCKED: required command not found: $cmd" >&2
    exit 2
  }
done
[ -d "$ACSIE/.git" ] || { echo "BLOCKED: missing checkout $ACSIE" >&2; exit 2; }
[ -d "$TESTER/.git" ] || { echo "BLOCKED: missing checkout $TESTER" >&2; exit 2; }

check_checkout() {
  local path="$1" expected_branch="$2" current
  current="$(git -C "$path" branch --show-current)"
  [ "$current" = "$expected_branch" ] || {
    echo "BLOCKED: $path is on '$current', expected '$expected_branch'" >&2
    exit 2
  }
  [ -z "$(git -C "$path" status --porcelain)" ] || {
    echo "BLOCKED: uncommitted changes in $path; preserving them" >&2
    git -C "$path" status --short >&2
    exit 2
  }
}
check_checkout "$ACSIE" "$ACSIE_BRANCH"
check_checkout "$TESTER" "$TESTER_BRANCH"

gh auth setup-git
gh auth status
kaggle --version
git -C "$ACSIE" pull --ff-only origin "$ACSIE_BRANCH"
git -C "$TESTER" pull --ff-only origin "$TESTER_BRANCH"

SOURCE_COMMIT="$(git -C "$ACSIE" rev-parse HEAD)"
ORCHESTRATION_COMMIT="$(git -C "$TESTER" rev-parse HEAD)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORKDIR="$(mktemp -d "$RECOVERY/control-stage-$STAMP-XXXXXX")"
chmod 700 "$WORKDIR"
WAKELOCK=0
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock >/dev/null 2>&1 || true
  WAKELOCK=1
fi
cleanup() {
  local rc=$?
  if [ "$WAKELOCK" -eq 1 ] && command -v termux-wake-unlock >/dev/null 2>&1; then
    termux-wake-unlock >/dev/null 2>&1 || true
  fi
  if [ "$rc" -eq 0 ]; then
    rm -rf -- "$WORKDIR"
    echo "TEMP_STAGE_CLEANED=yes"
    df -h "$HOME" 2>/dev/null || true
  else
    echo "TEMP_STAGE_PRESERVED=$WORKDIR" >&2
    echo "Inspect the private staging directory before retrying." >&2
  fi
  return "$rc"
}
trap cleanup EXIT

echo "SOURCE_COMMIT=$SOURCE_COMMIT"
echo "ORCHESTRATION_COMMIT=$ORCHESTRATION_COMMIT"
echo "V3_STATUS_CHECK=one snapshot"
V3_STATUS="$(kaggle kernels status "$V3_KERNEL" 2>&1 || true)"
printf '%s\n' "$V3_STATUS"
if printf '%s' "$V3_STATUS" | grep -qi 'KernelWorkerStatus.COMPLETE'; then
  V3_HARVEST="$WORKDIR/v3-harvest"
  mkdir -p "$V3_HARVEST"
  kaggle kernels output "$V3_KERNEL" \
    --path "$V3_HARVEST" \
    --file-pattern '.*(test_report\.json|receipt-candidate\.json|artifact_manifest\.json|foundry-summary\.json|result-77122[1-5]\.json)$' \
    --force --quiet
  V3_KEEP="$RECOVERY/v3-harvested-$STAMP"
  mkdir -p "$V3_KEEP"
  cp -a "$V3_HARVEST/." "$V3_KEEP/"
  echo "V3_SUMMARY_OUTPUTS_HARVESTED=$V3_KEEP"
  echo "V3_NOTE=preserved for audit; old candidate has known stale execution metadata and will not be auto-published"
elif printf '%s' "$V3_STATUS" | grep -qi 'KernelWorkerStatus.RUNNING'; then
  echo "V3_NOTE=left running and untouched"
else
  echo "V3_NOTE=not confirmed RUNNING/COMPLETE; status text preserved above"
fi

# Prefer the requested slug. If it already exists, create a fresh sibling slug
# so version/status checks cannot accidentally refer to a prior run.
if kaggle kernels status "$BASE_KERNEL" >/dev/null 2>&1; then
  SUFFIX="$(date -u +%Y%m%dt%H%M%S)"
  KERNEL="$BASE_KERNEL-$SUFFIX"
  KERNEL_TITLE="ACSIE Gen3 Foundry Fast $SUFFIX"
else
  KERNEL="$BASE_KERNEL"
  KERNEL_TITLE="ACSIE Gen3 Foundry Fast"
fi
echo "DISPATCH_KERNEL=$KERNEL"
echo "GPU_REQUEST=true; CPU process parallelism is the optimization; GPU math remains unused."

(
  cd "$TESTER"
  python3 -m unittest scripts.tests.test_build_embedded_kaggle_kernel -v
)

TEMPLATE="$WORKDIR/package"
ARCHIVE="$WORKDIR/acsie-gen3-foundry-package.tar.gz"
PAYLOAD="$WORKDIR/kernel-payload"
mkdir -p "$TEMPLATE" "$TEMPLATE/scripts/tests"
git -C "$ACSIE" archive --format=tar "$SOURCE_COMMIT" cognitive_core research |
  tar -xf - -C "$TEMPLATE"
cp "$TESTER/run_kaggle_foundry.py" "$TEMPLATE/run_kaggle_foundry.py"
cp "$TESTER/kernel-metadata.json" "$TEMPLATE/kernel-metadata.json"
cp "$TESTER/scripts/archive_foundry_outputs.py" "$TEMPLATE/scripts/archive_foundry_outputs.py"
cp "$TESTER/scripts/tests/test_archive_foundry_outputs.py" \
  "$TEMPLATE/scripts/tests/test_archive_foundry_outputs.py"

DISPATCH_NONCE="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
python3 - "$TEMPLATE/source-manifest.json" "$SOURCE_COMMIT" \
  "$ORCHESTRATION_COMMIT" "$DISPATCH_NONCE" "$ACSIE_BRANCH" <<'PY'
import json, sys
from pathlib import Path

out, source_commit, orchestration_commit, nonce, requested_ref = sys.argv[1:]
payload = {
    "schema": "ACSIE.gen3-foundry-source-manifest.v1",
    "repository": "Infrasigma/ACSIE",
    "source_commit": source_commit,
    "actual_acsie_commit": source_commit,
    "orchestration_commit": orchestration_commit,
    "requested_ref": requested_ref,
    "dispatch_nonce": nonce,
    "network_during_research": False,
}
Path(out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

echo "========== LOCAL FROZEN PHASE 0 =========="
(
  cd "$TEMPLATE"
  python3 - <<'PY'
import json
import sys
from pathlib import Path
import run_kaggle_foundry as runner

sys.path.insert(0, str(runner.ROOT))
passed = runner.run_phase0_tests()
working = Path("/kaggle/working") if Path("/kaggle/working").is_dir() else runner.ROOT / "kaggle-output"
report_path = working / "test_report.json"
report = json.loads(report_path.read_text(encoding="utf-8"))
print(json.dumps({
    "phase": "local_phase0",
    "status": report.get("status"),
    "tests_run": report.get("tests_run"),
    "tests_passed": report.get("tests_passed"),
    "failure_count": report.get("failure_count"),
    "error_count": report.get("error_count"),
    "loaded_suite_count": report.get("loaded_suite_count"),
}, sort_keys=True))
if (not passed or report.get("status") != "PASSED"
        or report.get("tests_run", 0) != report.get("tests_passed")
        or report.get("failure_count") or report.get("error_count")):
    raise SystemExit(2)
PY
)
cp "$TEMPLATE/kaggle-output/test_report.json" "$WORKDIR/local-test-report.json"

tar -czf "$ARCHIVE" \
  --exclude='kaggle-output' --exclude='*/kaggle-output' \
  --exclude='__pycache__' --exclude='*/__pycache__' --exclude='*.pyc' \
  -C "$TEMPLATE" .
ARCHIVE_SHA256="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
echo "EMBEDDED_SOURCE_ARCHIVE_SHA256=$ARCHIVE_SHA256"

python3 "$TESTER/scripts/build_embedded_kaggle_kernel.py" \
  --template-dir "$TEMPLATE" \
  --source-archive "$ARCHIVE" \
  --output-dir "$PAYLOAD" \
  --expected-sha256 "$ARCHIVE_SHA256" \
  --kernel-id "$KERNEL" \
  --title "$KERNEL_TITLE" \
  --enable-gpu > "$WORKDIR/build-report.json"

python3 - "$PAYLOAD/kernel-metadata.json" "$WORKDIR/build-report.json" \
  "$KERNEL" "$ARCHIVE_SHA256" <<'PY'
import json, sys
from pathlib import Path
meta_path, report_path, kernel_id, archive_sha = sys.argv[1:]
meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
report = json.loads(Path(report_path).read_text(encoding="utf-8"))
checks = {
    "correct_kernel_id": meta.get("id") == kernel_id,
    "private": str(meta.get("is_private", "")).lower() == "true",
    "internet_disabled": str(meta.get("enable_internet", "")).lower() == "false",
    "gpu_requested": str(meta.get("enable_gpu", "")).lower() == "true",
    "no_dataset_mounts": meta.get("dataset_sources") == [],
    "archive_hash_matches": report.get("embedded_archive_sha256") == archive_sha,
    "slug_bound": report.get("deployment_kernel_id_bound") is True,
    "build_passed": report.get("build_status") == "PASSED",
}
print(json.dumps({"payload_validation": checks, "build_report": report}, sort_keys=True))
if not all(checks.values()):
    raise SystemExit(2)
PY

POLL_LOG="$WORKDIR/kernel-poll.log"
set +e
python3 "$TESTER/scripts/poll_kaggle_kernel.py" \
  --kernel-slug "$KERNEL" \
  --path "$PAYLOAD" \
  --dispatch-nonce "$DISPATCH_NONCE" \
  --timeout-minutes 330 2>&1 | tee "$POLL_LOG"
POLL_RC=$?
set -e
KERNEL_VERSION="$(grep '^KAGGLE_KERNEL_VERSION=' "$POLL_LOG" | tail -n 1 | cut -d= -f2 || true)"
if [ "$POLL_RC" -ne 0 ]; then
  if [ -n "$KERNEL_VERSION" ]; then
    mkdir -p "$WORKDIR/phase0-failure"
    kaggle kernels output "$KERNEL/$KERNEL_VERSION" \
      --path "$WORKDIR/phase0-failure" \
      --file-pattern '.*test_report\.json$' --force --quiet || true
    python3 - "$WORKDIR/phase0-failure" <<'PY' || true
import json, sys
from pathlib import Path
files = list(Path(sys.argv[1]).rglob("test_report.json"))
if len(files) == 1:
    report = json.loads(files[0].read_text(encoding="utf-8"))
    print(json.dumps({k: report.get(k) for k in (
        "status","tests_run","tests_passed","failure_count","error_count","loader_errors"
    )}, sort_keys=True))
else:
    print("No unique remote test_report.json was available")
PY
  fi
  echo "BLOCKED: dispatched kernel did not pass completion/sentinel checks" >&2
  exit 2
fi
[[ "$KERNEL_VERSION" =~ ^[1-9][0-9]*$ ]] || {
  echo "BLOCKED: exact Kaggle kernel version was not captured" >&2
  exit 2
}
echo "KAGGLE_KERNEL_VERSION=$KERNEL_VERSION"

PHASE0_DIR="$WORKDIR/remote-phase0"
mkdir -p "$PHASE0_DIR"
kaggle kernels output "$KERNEL/$KERNEL_VERSION" \
  --path "$PHASE0_DIR" \
  --file-pattern '.*test_report\.json$' --force --quiet
python3 - "$PHASE0_DIR" "$WORKDIR/remote-test-report.json" <<'PY'
import json, shutil, sys
from pathlib import Path
root, saved = map(Path, sys.argv[1:])
files = list(root.rglob("test_report.json"))
if len(files) != 1:
    raise SystemExit("BLOCKED: remote test_report.json missing or ambiguous")
report = json.loads(files[0].read_text(encoding="utf-8"))
shutil.copyfile(files[0], saved)
summary = {k: report.get(k) for k in (
    "status","tests_run","tests_passed","failure_count","error_count",
    "loaded_suite_count","required_suite_count","research_started"
)}
print(json.dumps(summary, sort_keys=True))
if (report.get("status") != "PASSED"
        or not isinstance(report.get("tests_run"), int)
        or report.get("tests_run") < 1
        or report.get("tests_passed") != report.get("tests_run")
        or report.get("failure_count") != 0
        or report.get("error_count") != 0
        or report.get("loader_errors")
        or report.get("research_started") is not False):
    raise SystemExit("BLOCKED: remote Phase 0 report did not pass fail-closed validation")
PY

OUTPUT="$WORKDIR/kernel-output"
mkdir -p "$OUTPUT"
kaggle kernels output "$KERNEL/$KERNEL_VERSION" --path "$OUTPUT" --force --quiet
RUN_ID="$(python3 - "$OUTPUT/receipt-candidate.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["run_id"])
PY
)"
echo "RUN_ID=$RUN_ID"

ARCHIVER="$TESTER/scripts/archive_foundry_outputs.py"
DATASET_DIR="$WORKDIR/checkpoint-dataset"
python3 "$ARCHIVER" prepare \
  --output-root "$OUTPUT" \
  --dataset-root "$DATASET_DIR" \
  --dataset-slug "$CHECKPOINT_DATASET" \
  --prepare-record "$WORKDIR/prepare-record.json" \
  --expected-dispatch-nonce "$DISPATCH_NONCE"

DATASET_BEFORE=0
if kaggle datasets status "$CHECKPOINT_DATASET" >/dev/null 2>&1; then
  python3 "$ARCHIVER" verify-private --dataset-slug "$CHECKPOINT_DATASET" \
    > "$WORKDIR/dataset-private-before.json"
  DATASET_BEFORE="$(python3 - "$WORKDIR/dataset-private-before.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["current_version"])
PY
)"
  kaggle datasets version \
    --path "$DATASET_DIR" \
    --message "ACSIE Control $RUN_ID" \
    --keep-tabular --dir-mode skip --quiet
else
  kaggle datasets create \
    --path "$DATASET_DIR" \
    --keep-tabular --dir-mode skip --quiet
fi

DATASET_VERSION=0
for attempt in $(seq 1 90); do
  if python3 "$ARCHIVER" verify-private --dataset-slug "$CHECKPOINT_DATASET" \
      > "$WORKDIR/dataset-private.json" 2>/dev/null; then
    DATASET_VERSION="$(python3 - "$WORKDIR/dataset-private.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["current_version"])
PY
)"
    if [ "$DATASET_VERSION" -gt "$DATASET_BEFORE" ]; then
      break
    fi
  fi
  sleep 10
done
[ "$DATASET_VERSION" -gt "$DATASET_BEFORE" ] || {
  echo "BLOCKED: private dataset version did not advance after upload" >&2
  exit 2
}
echo "KAGGLE_DATASET_VERSION=$DATASET_VERSION"

REMOTE_LISTING="$WORKDIR/remote-dataset-files.csv"
LISTING_READY=0
for attempt in $(seq 1 60); do
  if kaggle datasets files "$CHECKPOINT_DATASET/$DATASET_VERSION" \
      --page-size 200 --csv > "$REMOTE_LISTING" 2>/dev/null; then
    LISTING_READY=1
    break
  fi
  sleep 10
done
[ "$LISTING_READY" -eq 1 ] || {
  echo "BLOCKED: exact checkpoint dataset version file listing unavailable" >&2
  exit 2
}

DOWNLOAD_DIR="$WORKDIR/checkpoint-dataset-recheck"
mkdir -p "$DOWNLOAD_DIR"
kaggle datasets download "$CHECKPOINT_DATASET/$DATASET_VERSION" \
  --path "$DOWNLOAD_DIR" --unzip --force --quiet

python3 "$ARCHIVER" attest \
  --prepare-record "$WORKDIR/prepare-record.json" \
  --output-root "$OUTPUT" \
  --downloaded-root "$DOWNLOAD_DIR" \
  --dataset-slug "$CHECKPOINT_DATASET" \
  --dataset-version "$DATASET_VERSION" \
  --observed-version "$DATASET_VERSION" \
  --kernel-slug "$KERNEL" \
  --kernel-version "$KERNEL_VERSION" \
  --remote-listing "$REMOTE_LISTING" \
  --attestation-output "$WORKDIR/archive-attestation.json"

RECEIPT="$WORKDIR/control-receipt.json"
PUBLISH_LOG="$WORKDIR/receipt-publish.log"
set +e
GITHUB_TOKEN="$(gh auth token)" python3 "$ACSIE/research/emit_validated_receipt.py" \
  --input "$OUTPUT/receipt-candidate.json" \
  --artifact-root "$OUTPUT" \
  --manifest "$OUTPUT/artifact_manifest.json" \
  --archive-attestation "$WORKDIR/archive-attestation.json" \
  --dataset-slug "$CHECKPOINT_DATASET" \
  --dataset-version "$DATASET_VERSION" \
  --kernel-slug "$KERNEL" \
  --kernel-version "$KERNEL_VERSION" \
  --target-branch "$ACSIE_BRANCH" \
  --output "$RECEIPT" --publish 2>&1 | tee "$PUBLISH_LOG"
PUBLISH_RC=$?
set -e
[ "$PUBLISH_RC" -eq 0 ] || {
  echo "BLOCKED: validated receipt was not published" >&2
  exit 2
}
RECEIPT_COMMIT="$(grep 'Published validated receipt' "$PUBLISH_LOG" | sed -n 's/.*commit=//p' | tail -n 1)"
echo "RECEIPT_COMMIT=$RECEIPT_COMMIT"

RUN_ID="$(python3 - "$RECEIPT" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["run_id"])
PY
)"
HANDOFF="$RECOVERY/control-handoffs/$RUN_ID"
mkdir -p "$HANDOFF/seed-results"
chmod 700 "$HANDOFF"
cp "$RECEIPT" "$HANDOFF/receipt.json"
cp "$OUTPUT/receipt-candidate.json" "$HANDOFF/receipt-candidate.json"
cp "$OUTPUT/artifact_manifest.json" "$HANDOFF/artifact_manifest.json"
cp "$WORKDIR/archive-attestation.json" "$HANDOFF/archive-attestation.json"
cp "$WORKDIR/build-report.json" "$HANDOFF/build-report.json"
cp "$WORKDIR/local-test-report.json" "$HANDOFF/local-test-report.json"
cp "$WORKDIR/remote-test-report.json" "$HANDOFF/remote-test-report.json"
cp "$OUTPUT/foundry-summary.json" "$HANDOFF/foundry-summary.json"
for f in "$OUTPUT"/seed-results/result-*.json; do
  [ -f "$f" ] && cp "$f" "$HANDOFF/seed-results/"
done

python3 - "$HANDOFF" "$KERNEL" "$KERNEL_VERSION" "$CHECKPOINT_DATASET" \
  "$DATASET_VERSION" "$SOURCE_COMMIT" "$ORCHESTRATION_COMMIT" "$ARCHIVE_SHA256" \
  "$RECEIPT_COMMIT" <<'PY'
import json, statistics, sys
from pathlib import Path

root = Path(sys.argv[1])
kernel, kernel_version = sys.argv[2], int(sys.argv[3])
dataset, dataset_version = sys.argv[4], int(sys.argv[5])
source_commit, orchestration_commit, archive_sha, receipt_commit = sys.argv[6:]
receipt = json.loads((root / "receipt.json").read_text(encoding="utf-8"))
summary = json.loads((root / "foundry-summary.json").read_text(encoding="utf-8"))
build = json.loads((root / "build-report.json").read_text(encoding="utf-8"))
remote_tests = json.loads((root / "remote-test-report.json").read_text(encoding="utf-8"))
local_tests = json.loads((root / "local-test-report.json").read_text(encoding="utf-8"))

seeds = []
gen0_durations = []
for p in sorted((root / "seed-results").glob("result-*.json")):
    result = json.loads(p.read_text(encoding="utf-8"))
    generations = result.get("generations", [])
    passed = sum(g.get("scientific_status") == "PASSED" for g in generations)
    evaluated = sum(g.get("evaluated") is True for g in generations)
    for g in generations:
        if g.get("generation") == 0 and g.get("evaluated") is True and isinstance(g.get("gen_duration_sec"), (int, float)):
            gen0_durations.append(float(g["gen_duration_sec"]))
    seeds.append({
        "seed": result.get("seed"),
        "scientific_status": result.get("scientific_status"),
        "passed_generations": passed,
        "evaluated_generations": evaluated,
        "failed_or_blocked_generations": len(generations) - passed,
        "final_metrics": result.get("final_metrics", {}),
        "generation_timings_and_gains": [
            {
                "generation": g.get("generation"),
                "status": g.get("scientific_status"),
                "evaluated": g.get("evaluated"),
                "gen_duration_sec": g.get("gen_duration_sec"),
                "replay_exact": g.get("replay_exact"),
                "forward_training_gain": g.get("forward_training_gain"),
                "reverse_training_gain": g.get("reverse_training_gain"),
                "forward_validation_gain": g.get("forward_validation_gain"),
                "reverse_validation_gain": g.get("reverse_validation_gain"),
                "result_sha256": g.get("result_sha256"),
            }
            for g in generations
        ],
    )

scorecard = {
    "run_id": receipt.get("run_id"),
    "scientific_status": receipt.get("scientific_status"),
    "qualification_status": summary.get("qualification_status"),
    "kernel": {"slug": kernel, "version": kernel_version},
    "checkpoint_dataset": {
        "slug": dataset, "version": dataset_version,
        "visibility": "verified private; 67 manifest-declared files SHA-256 rechecked",
    },
    "published_receipt_commit": receipt_commit,
    "hardware": {
        "gpu_requested": summary.get("gpu_requested"),
        "gpu_computation_used": summary.get("gpu_acceleration_enabled"),
        "gpu_device_telemetry": summary.get("gpu_device_telemetry"),
        "cpu_count": summary.get("reported_cpu_count"),
        "parallel_worker_count": summary.get("parallel_worker_count"),
        "platform": summary.get("platform"),
        "machine": summary.get("machine"),
    },
    "runtime": {
        "kernel_wall_clock_sec": summary.get("kernel_wall_clock_sec"),
        "research_wall_clock_sec": summary.get("research_wall_clock_sec"),
        "observed_gen0_sec_per_evaluated_seed": {
            "values": gen0_durations,
            "median": statistics.median(gen0_durations) if gen0_durations else None,
            "note": "observed during the actual 5x12 run; the frozen production driver rejects generations=1, so this is not a separate 1x1 preflight",
        },
    },
    "local_source": {
        "acsie_commit": source_commit,
        "tester_commit": orchestration_commit,
        "embedded_source_archive_sha256": archive_sha,
        "embedded_runner_sha256": build.get("runner_sha256"),
    },
    "phase0": {
        "local": {k: local_tests.get(k) for k in ("status","tests_run","tests_passed","failure_count","error_count")},
        "remote": {k: remote_tests.get(k) for k in ("status","tests_run","tests_passed","failure_count","error_count")},
    },
    "seeds": seeds,
}
(root / "control-scorecard.json").write_text(json.dumps(scorecard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({
    "CONTROL_PIPELINE": "COMPLETE",
    "run_id": scorecard["run_id"],
    "scientific_status": scorecard["scientific_status"],
    "kernel": scorecard["kernel"],
    "checkpoint_dataset": scorecard["checkpoint_dataset"],
    "published_receipt_commit": receipt_commit,
    "hardware": scorecard["hardware"],
    "runtime": scorecard["runtime"],
    "phase0": scorecard["phase0"],
    "seeds": [
        {k: s[k] for k in ("seed","scientific_status","evaluated_generations","passed_generations","failed_or_blocked_generations","final_metrics")}
        for s in seeds
    ],
    "scorecard_path": str(root / "control-scorecard.json"),
}, sort_keys=True))
PY

echo "CONTROL_HANDOFF=$HANDOFF"
echo "CONTROL_RECEIPT_SEALED=yes"
echo "NEXT=H-QD-01 remains a separate scientific treatment change; do not infer it passed or ran from this Control result."

#!/usr/bin/env python3
"""Push the private Kaggle kernel and poll its exact version without verbose logs."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
import re
import subprocess
import sys
import time

try:
    from scripts.build_embedded_kaggle_kernel import BuildError, validate_staged_kernel
except ModuleNotFoundError:
    # The control script may execute this file by path, where scripts/ itself is sys.path[0].
    from build_embedded_kaggle_kernel import BuildError, validate_staged_kernel


VERSION_RE = re.compile(r"(?i)kernel\s+version\s+(\d+)\s+successfully\s+pushed")
KNOWN = ("COMPLETE", "ERROR", "FAILED", "CANCELLED", "RUNNING", "QUEUED", "INITIALIZING")


def run(argv):
    try:
        return subprocess.run(argv, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=False)
    except OSError:
        return None


def candidate_dispatch_error(candidate, expected_nonce: str, expected_slug: str) -> str | None:
    """Require a receipt candidate to bind both the current dispatch and actual kernel slug."""
    if not isinstance(candidate, dict):
        return "candidate_not_object"
    provenance = candidate.get("provenance")
    nonce = provenance.get("dispatch_nonce") if isinstance(provenance, dict) else None
    if nonce is None:
        nonce = candidate.get("dispatch_nonce")
    if nonce != expected_nonce:
        return "dispatch_nonce_mismatch"
    execution = candidate.get("execution")
    if not isinstance(execution, dict):
        return "candidate_execution_missing"
    if execution.get("kernel_slug") != expected_slug:
        return "kernel_slug_mismatch"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel-slug", required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--dispatch-nonce", required=True)
    parser.add_argument("--completion-file", default="receipt-candidate.json")
    parser.add_argument("--timeout-minutes", type=int, default=330)
    args = parser.parse_args()
    if not args.dispatch_nonce or len(args.dispatch_nonce) > 200:
        print("KAGGLE_KERNEL_FAILED: invalid dispatch nonce", file=sys.stderr)
        return 2
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.completion_file):
        print("KAGGLE_KERNEL_FAILED: invalid completion file name", file=sys.stderr)
        return 2

    if not re.fullmatch(r"[a-z0-9._-]+/[a-z0-9._-]+", args.kernel_slug):
        print("KAGGLE_KERNEL_FAILED: invalid slug", file=sys.stderr)
        return 2
    if args.timeout_minutes < 1 or args.timeout_minutes > 345:
        print("KAGGLE_KERNEL_FAILED: invalid timeout", file=sys.stderr)
        return 2
    kernel_dir = Path(args.path)
    if not kernel_dir.is_dir() or not (kernel_dir / "kernel-metadata.json").is_file():
        print("KAGGLE_KERNEL_FAILED: staged kernel payload missing", file=sys.stderr)
        return 2

    try:
        guard = validate_staged_kernel(kernel_dir, args.kernel_slug)
    except (BuildError, OSError, ValueError) as exc:
        print(f"KAGGLE_KERNEL_FAILED: staged payload guard failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"event": "staged_kernel_guard", **guard}, sort_keys=True), flush=True)
    pushed = run(["kaggle", "kernels", "push", "--path", str(kernel_dir)])
    if pushed is None or pushed.returncode != 0:
        print("KAGGLE_KERNEL_FAILED: push stage failed", file=sys.stderr)
        return 2
    match = VERSION_RE.search(pushed.stdout or "")
    if not match:
        print("KAGGLE_KERNEL_FAILED: pushed version was not reported", file=sys.stderr)
        return 2
    version = int(match.group(1))
    started = time.monotonic()
    deadline = started + args.timeout_minutes * 60
    next_progress_log = started + 60
    last_status = "UNKNOWN"

    while time.monotonic() < deadline:
        result = run(["kaggle", "kernels", "status", args.kernel_slug])
        if result is not None and result.returncode == 0:
            output = (result.stdout or "").upper()
            found = next((status for status in KNOWN if status in output), None)
            if found:
                last_status = found
                if found == "COMPLETE":
                    # A terminal status can briefly describe the previous kernel
                    # revision. Do not proceed until this version's small candidate
                    # contains this invocation's nonce.
                    with tempfile.TemporaryDirectory(prefix="acsie-kernel-sentinel-") as temp:
                        sentinel = run([
                            "kaggle", "kernels", "output", f"{args.kernel_slug}/{version}",
                            "--path", temp, "--file-pattern", ".*" + re.escape(args.completion_file) + r"$",
                            "--force", "--quiet",
                        ])
                        matches = list(Path(temp).rglob(args.completion_file))
                        if sentinel is not None and sentinel.returncode == 0 and len(matches) == 1:
                            try:
                                candidate = json.loads(matches[0].read_text(encoding="utf-8"))
                                validation_error = candidate_dispatch_error(
                                    candidate, args.dispatch_nonce, args.kernel_slug
                                )
                            except (OSError, json.JSONDecodeError, AttributeError):
                                validation_error = "candidate_unreadable"
                            if validation_error == "kernel_slug_mismatch":
                                print(
                                    "KAGGLE_KERNEL_FAILED: receipt candidate kernel slug mismatch",
                                    file=sys.stderr,
                                )
                                return 2
                            if validation_error is None:
                                print(f"KAGGLE_KERNEL_VERSION={version}", flush=True)
                                print(f"KAGGLE_KERNEL_SLUG={args.kernel_slug}", flush=True)
                                output_path = os.environ.get("GITHUB_OUTPUT")
                                if output_path:
                                    with open(output_path, "a", encoding="utf-8") as out:
                                        out.write(f"kernel_version={version}\n")
                                        out.write("kernel_status=COMPLETE\n")
                                print("KAGGLE_KERNEL_COMPLETE: requested_version_verified")
                                return 0
                elif found in {"ERROR", "FAILED", "CANCELLED"}:
                    version_match = re.search(r"(?i)version\s*[:#]?\s*(\d+)", result.stdout or "")
                    if version_match and int(version_match.group(1)) != version:
                        # Status still refers to a prior revision; keep waiting.
                        pass
                    else:
                        print(f"KAGGLE_KERNEL_VERSION={version}", file=sys.stderr)
                        print(f"KAGGLE_KERNEL_SLUG={args.kernel_slug}", file=sys.stderr)
                        print(f"KAGGLE_KERNEL_FAILED: version={version} status={found}", file=sys.stderr)
                        return 2
        now = time.monotonic()
        if now >= next_progress_log:
            print(json.dumps({
                "event": "kaggle_kernel_poll",
                "kernel_slug": args.kernel_slug,
                "kernel_version": version,
                "status": last_status,
                "elapsed_sec": round(now - started, 1),
            }, sort_keys=True, separators=(",", ":")), flush=True)
            next_progress_log = now + 60
        time.sleep(15)

    print(f"KAGGLE_KERNEL_VERSION={version}", file=sys.stderr)
    print(f"KAGGLE_KERNEL_SLUG={args.kernel_slug}", file=sys.stderr)
    print(f"KAGGLE_KERNEL_TIMEOUT: version={version} last_status={last_status}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

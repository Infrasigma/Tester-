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


VERSION_RE = re.compile(r"(?i)kernel\s+version\s+(\d+)\s+successfully\s+pushed")
KNOWN = ("COMPLETE", "ERROR", "FAILED", "CANCELLED", "RUNNING", "QUEUED", "INITIALIZING")


def run(argv):
    try:
        return subprocess.run(argv, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=False)
    except OSError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel-slug", required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--dispatch-nonce", required=True)
    parser.add_argument("--timeout-minutes", type=int, default=330)
    args = parser.parse_args()
    if not args.dispatch_nonce or len(args.dispatch_nonce) > 200:
        print("KAGGLE_KERNEL_FAILED: invalid dispatch nonce", file=sys.stderr)
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

    pushed = run(["kaggle", "kernels", "push", "--path", str(kernel_dir)])
    if pushed is None or pushed.returncode != 0:
        print("KAGGLE_KERNEL_FAILED: push stage failed", file=sys.stderr)
        return 2
    match = VERSION_RE.search(pushed.stdout or "")
    if not match:
        print("KAGGLE_KERNEL_FAILED: pushed version was not reported", file=sys.stderr)
        return 2
    version = int(match.group(1))
    deadline = time.monotonic() + args.timeout_minutes * 60
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
                            "--path", temp, "--file-pattern", r".*receipt-candidate\.json$",
                            "--force", "--quiet",
                        ])
                        matches = list(Path(temp).rglob("receipt-candidate.json"))
                        if sentinel is not None and sentinel.returncode == 0 and len(matches) == 1:
                            try:
                                candidate = json.loads(matches[0].read_text(encoding="utf-8"))
                                nonce = candidate.get("provenance", {}).get("dispatch_nonce")
                            except (OSError, json.JSONDecodeError, AttributeError):
                                nonce = None
                            if nonce == args.dispatch_nonce:
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
        time.sleep(15)

    print(f"KAGGLE_KERNEL_VERSION={version}", file=sys.stderr)
    print(f"KAGGLE_KERNEL_SLUG={args.kernel_slug}", file=sys.stderr)
    print(f"KAGGLE_KERNEL_TIMEOUT: version={version} last_status={last_status}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

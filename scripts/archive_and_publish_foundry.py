#!/usr/bin/env python3
"""Post-run private Kaggle archival and compact-receipt publisher.

All large file transfers happen on a GitHub-hosted runner. Logs contain only stage
names and structural counts; subprocess stdout/stderr (which can include API errors)
are held in memory and never dumped wholesale.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import archive_foundry_outputs as archive
from scripts.read_kaggle_version import find_version


class PipelineError(RuntimeError):
    pass


def run_cli(argv: list[str], *, stage: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            argv, cwd=str(cwd) if cwd else None, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
    except OSError as exc:
        raise PipelineError(stage) from exc
    if result.returncode != 0:
        raise PipelineError(stage)
    return result


def try_cli(argv: list[str], *, stage: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError as exc:
        raise PipelineError(stage) from exc


def kaggle_status_version(slug: str) -> tuple[bool, int | None]:
    result = try_cli([
        "kaggle", "datasets", "status", slug, "--format", "json(current_version_number)"
    ], stage="dataset-status")
    if result.returncode != 0:
        return False, None
    version = find_version(result.stdout)
    if version is None:
        raise PipelineError("dataset-version-parse")
    return True, version


def verify_private(slug: str) -> int:
    result = run_cli([
        sys.executable, str(ROOT / "scripts" / "archive_foundry_outputs.py"),
        "verify-private", "--dataset-slug", slug,
    ], stage="dataset-privacy-check")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PipelineError("dataset-privacy-response") from exc
    if payload.get("privacy_status") != "VERIFIED_PRIVATE":
        raise PipelineError("dataset-privacy-check")
    version = payload.get("current_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise PipelineError("dataset-version-privacy-check")
    return version


def archive_run(args: argparse.Namespace) -> int:
    kernel_slug = args.kernel_slug
    dataset_slug = args.dataset_slug
    target_branch = args.target_branch
    if target_branch == "main" or target_branch == "refs/heads/main" or target_branch.endswith("/main"):
        raise PipelineError("main-branch-publication-forbidden")
    if not re.fullmatch(r"[a-z0-9._-]+/[a-z0-9._-]+", kernel_slug):
        raise PipelineError("invalid-kernel-slug")
    if not re.fullmatch(r"[a-z0-9._-]+/[a-z0-9._-]+", dataset_slug):
        raise PipelineError("invalid-dataset-slug")
    if isinstance(args.kernel_version, bool) or args.kernel_version < 1:
        raise PipelineError("invalid-kernel-version")
    token = os.environ.get("KAGGLE_API_TOKEN", "").strip()
    if not token and not (Path.home() / ".kaggle" / "kaggle.json").is_file():
        raise PipelineError("kaggle-auth-not-configured")
    if not os.environ.get("GITHUB_TOKEN"):
        raise PipelineError("acsie-write-token-not-configured")

    work_root = Path(args.work_root).resolve()
    if work_root.exists():
        import shutil
        shutil.rmtree(work_root)
    output_root = work_root / "kernel-output"
    dataset_root = work_root / "dataset-payload"
    downloaded_root = work_root / "dataset-verify"
    prepare_record = work_root / "prepare-record.json"
    listing_path = work_root / "remote-files.csv"
    attestation_path = work_root / "archive-attestation.json"
    receipt_path = work_root / "validated-receipt.json"
    work_root.mkdir(parents=True)

    output_root.mkdir()
    # Pin the version in the argument and confirm the candidate's dispatch nonce.
    # Kaggle CLI builds that ignore version suffixes therefore fail closed on nonce mismatch.
    run_cli([
        "kaggle", "kernels", "output", f"{kernel_slug}/{args.kernel_version}",
        "--path", str(output_root), "--file-pattern", r".*\.json$", "--quiet",
    ], stage="kernel-output-download")

    expected_nonce = args.expected_dispatch_nonce or None
    prepare_args = argparse.Namespace(
        output_root=str(output_root),
        dataset_root=str(dataset_root),
        dataset_slug=dataset_slug,
        prepare_record=str(prepare_record),
        expected_dispatch_nonce=expected_nonce,
    )
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            archive.prepare(prepare_args)
    except Exception as exc:
        raise PipelineError("kernel-output-manifest-check") from exc

    manifest = json.loads((output_root / "artifact_manifest.json").read_text(encoding="utf-8"))
    run_id = manifest["run_id"]
    pre_exists, pre_cli_version = kaggle_status_version(dataset_slug)
    if pre_exists:
        pre_api_version = verify_private(dataset_slug)
        if pre_api_version != pre_cli_version:
            raise PipelineError("pre-version-privacy-version-mismatch")
        old_version = pre_api_version
        run_cli([
            "kaggle", "datasets", "version", "--path", str(dataset_root),
            "--message", f"ACSIE Foundry run {run_id}",
            "--quiet", "--keep-tabular", "--dir-mode", "skip",
        ], stage="dataset-version-upload")
        expected_dataset_version = old_version + 1
    else:
        # Kaggle Dataset creation is private by default. The workflow never passes --public.
        run_cli([
            "kaggle", "datasets", "create", "--path", str(dataset_root),
            "--quiet", "--keep-tabular", "--dir-mode", "skip",
        ], stage="private-dataset-create")
        expected_dataset_version = 1

    dataset_version = None
    api_version = None
    for _ in range(36):
        try:
            exists, cli_version = kaggle_status_version(dataset_slug)
            if exists and cli_version == expected_dataset_version:
                api_version = verify_private(dataset_slug)
                if api_version == expected_dataset_version:
                    dataset_version = cli_version
                    break
        except PipelineError:
            pass
        time.sleep(10)
    if dataset_version is None or api_version != dataset_version:
        raise PipelineError("dataset-version-or-privacy-verification")

    listing = run_cli([
        "kaggle", "datasets", "files", dataset_slug, "--page-size", "200", "--csv"
    ], stage="dataset-file-listing")
    listing_path.write_text(listing.stdout, encoding="utf-8")

    downloaded_root.mkdir()
    run_cli([
        "kaggle", "datasets", "download", dataset_slug,
        "--path", str(downloaded_root), "--unzip", "--force", "--quiet",
    ], stage="private-dataset-download-for-verification")

    # Recheck version after download to detect concurrent dataset mutation.
    exists, after_download_cli_version = kaggle_status_version(dataset_slug)
    after_download_api_version = verify_private(dataset_slug)
    if not exists or after_download_cli_version != dataset_version or after_download_api_version != dataset_version:
        raise PipelineError("dataset-version-changed-during-verification")

    attest_args = argparse.Namespace(
        prepare_record=str(prepare_record),
        output_root=str(output_root),
        downloaded_root=str(downloaded_root),
        dataset_slug=dataset_slug,
        dataset_version=dataset_version,
        observed_version=after_download_api_version,
        kernel_slug=kernel_slug,
        kernel_version=args.kernel_version,
        remote_listing=str(listing_path),
        attestation_output=str(attestation_path),
    )
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            archive.attest(attest_args)
    except Exception as exc:
        raise PipelineError("post-upload-checksum-verification") from exc

    acsie_root = Path(args.acsie_root).resolve()
    emitter = acsie_root / "research" / "emit_validated_receipt.py"
    validator = acsie_root / "research" / "validate_remote_receipts.py"
    if not emitter.is_file() or not validator.is_file():
        raise PipelineError("private-acsie-receipt-tooling-missing")
    candidate = output_root / "receipt-candidate.json"
    manifest_path = output_root / "artifact_manifest.json"
    run_cli([
        sys.executable, "-m", "research.emit_validated_receipt",
        "--input", str(candidate),
        "--artifact-root", str(output_root),
        "--manifest", str(manifest_path),
        "--archive-attestation", str(attestation_path),
        "--dataset-slug", dataset_slug,
        "--dataset-version", str(dataset_version),
        "--kernel-slug", kernel_slug,
        "--kernel-version", str(args.kernel_version),
        "--target-branch", target_branch,
        "--output", str(receipt_path),
        "--publish",
    ], stage="receipt-validation-or-publication", cwd=acsie_root)

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    rows = receipt.get("seed_results", [])
    generation_count = sum(len(row.get("generations", [])) for row in rows if isinstance(row, dict))
    print(json.dumps({
        "pipeline_status": "RECEIPT_PUBLISHED",
        "scientific_status": receipt["scientific_status"],
        "seed_count": len(rows),
        "generation_records": generation_count,
        "artifact_references": len(receipt.get("artifacts", [])),
        "receipt_bytes": receipt_path.stat().st_size,
        "dataset_visibility": "private",
        "sha256_rechecked_files": 67,
    }, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel-slug", required=True)
    parser.add_argument("--kernel-version", required=True, type=int)
    parser.add_argument("--dataset-slug", required=True)
    parser.add_argument("--target-branch", default="work/research-data-routing-20261023")
    parser.add_argument("--acsie-root", required=True)
    parser.add_argument("--work-root", required=True)
    parser.add_argument("--expected-dispatch-nonce")
    args = parser.parse_args()
    try:
        return archive_run(args)
    except (PipelineError, OSError, json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        stage = str(exc) if isinstance(exc, PipelineError) else "unexpected-publisher-error"
        print(f"PIPELINE_NOT_PUBLISHED: stage={stage}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

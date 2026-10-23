#!/usr/bin/env python3
"""Prepare and verify a private Kaggle Dataset snapshot of Foundry kernel outputs.

The kernel itself runs with internet disabled. This helper runs only in the trusted
post-run environment and never prints filenames, tokens, or checkpoint contents.
It deliberately fails closed on missing/duplicate generations or SHA-256 mismatch.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "ACSIE.kaggle-foundry-artifact-manifest.v1"
ATTESTATION_SCHEMA = "ACSIE.kaggle-foundry-dataset-archive-attestation.v1"
SEEDS = (771221, 771222, 771223, 771224, 771225)
STATUS = {"PASSED", "FAILED", "BLOCKED", "CRASHED", "INVALID", "INCONCLUSIVE"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SLUG = re.compile(r"^[a-z0-9._-]+/[a-z0-9._-]+$")


class ArchiveError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchiveError("a required JSON record is missing or unreadable") from exc
    if not isinstance(data, dict):
        raise ArchiveError("a required JSON record is not an object")
    return data


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def relative_file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ArchiveError("manifest contains an unsafe relative path")
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ArchiveError("manifest path escapes the output directory")
    if not resolved.is_file():
        raise ArchiveError("a manifest-declared output file is missing")
    return resolved


def verify_outputs(output_root: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    candidate_path = output_root / "receipt-candidate.json"
    manifest_path = output_root / "artifact_manifest.json"
    candidate = read_json(candidate_path)
    manifest = read_json(manifest_path)
    if candidate.get("candidate_schema") != "ACSIE.kaggle-foundry-candidate.v1":
        raise ArchiveError("unsupported receipt-candidate schema")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ArchiveError("unsupported artifact-manifest schema")
    if candidate.get("run_id") != manifest.get("run_id"):
        raise ArchiveError("candidate/manifest run ID mismatch")
    source = candidate.get("source")
    if not isinstance(source, dict) or source.get("commit_sha") != manifest.get("source_commit"):
        raise ArchiveError("candidate/manifest source commit mismatch")
    expected = candidate.get("expected_seed_ids")
    if expected != list(SEEDS) or manifest.get("expected_seed_ids") != list(SEEDS):
        raise ArchiveError("candidate/manifest seed set mismatch")
    if manifest.get("expected_generations_per_seed") != 12:
        raise ArchiveError("manifest must describe twelve generations per seed")

    rows = manifest.get("files")
    if not isinstance(rows, list) or len(rows) != 66:
        raise ArchiveError("manifest must contain sixty generation bundles, five seed summaries, and one aggregate summary")
    by_path: dict[str, dict[str, Any]] = {}
    generation_rows: dict[tuple[int, int], dict[str, Any]] = {}
    seed_summaries: set[int] = set()
    aggregate_count = 0
    total_size = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ArchiveError("manifest contains a malformed file record")
        relative = row.get("path")
        if relative in by_path:
            raise ArchiveError("manifest contains duplicate artifact paths")
        path = relative_file(output_root, relative)
        digest = row.get("sha256")
        size = row.get("size_bytes")
        if not isinstance(digest, str) or not HEX64.fullmatch(digest):
            raise ArchiveError("manifest contains an invalid SHA-256 digest")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ArchiveError("manifest contains an invalid byte count")
        if path.stat().st_size != size or file_sha(path) != digest:
            raise ArchiveError("manifest-declared SHA-256 or size did not match the downloaded kernel output")
        by_path[relative] = row
        total_size += size
        kind = row.get("kind")
        if kind == "generation_bundle":
            seed, generation = row.get("seed"), row.get("generation")
            if isinstance(seed, bool) or seed not in SEEDS or isinstance(generation, bool) or generation not in range(12):
                raise ArchiveError("manifest contains an unknown seed/generation")
            key = (seed, generation)
            if key in generation_rows:
                raise ArchiveError("manifest contains a duplicate seed/generation")
            bundle = read_json(path)
            record = bundle.get("generation_record")
            if (bundle.get("seed") != seed or bundle.get("generation") != generation
                    or not isinstance(record, dict)
                    or record.get("generation") != generation
                    or record.get("scientific_status") != row.get("scientific_status")
                    or record.get("evaluated") is not row.get("evaluated")
                    or record.get("result_sha256") != row.get("result_sha256")):
                raise ArchiveError("bundle contents disagree with the artifact manifest")
            if row.get("scientific_status") not in STATUS or not isinstance(row.get("evaluated"), bool):
                raise ArchiveError("generation status/evaluated fields are invalid")
            if row["scientific_status"] == "PASSED" and row["evaluated"] is not True:
                raise ArchiveError("PASSED generation did not carry an evaluated=true flag")
            generation_rows[key] = row
        elif kind == "seed_summary":
            seed = row.get("seed")
            if isinstance(seed, bool) or seed not in SEEDS or seed in seed_summaries:
                raise ArchiveError("manifest contains a duplicate or unknown seed summary")
            seed_summaries.add(seed)
        elif kind == "foundry_summary":
            aggregate_count += 1
        else:
            raise ArchiveError("manifest contains an unsupported artifact kind")

    expected_keys = {(seed, generation) for seed in SEEDS for generation in range(12)}
    if set(generation_rows) != expected_keys or len(generation_rows) != 60:
        raise ArchiveError("manifest does not contain the complete 5-by-12 matrix")
    if seed_summaries != set(SEEDS) or aggregate_count != 1:
        raise ArchiveError("manifest must contain one seed summary per seed and one foundry summary")

    candidate_rows = candidate.get("seed_results")
    if not isinstance(candidate_rows, list) or len(candidate_rows) != 5:
        raise ArchiveError("candidate must contain exactly five seed rows")
    candidate_by_seed = {row.get("seed"): row for row in candidate_rows if isinstance(row, dict)}
    if set(candidate_by_seed) != set(SEEDS):
        raise ArchiveError("candidate seeds do not match the fixed seed set")
    for (seed, generation), manifest_row in generation_rows.items():
        seed_row = candidate_by_seed[seed]
        children = seed_row.get("generations")
        child = next((g for g in children if isinstance(g, dict) and g.get("generation") == generation), None) if isinstance(children, list) else None
        if (not isinstance(child, dict)
                or child.get("scientific_status") != manifest_row.get("scientific_status")
                or child.get("evaluated") is not manifest_row.get("evaluated")
                or child.get("result_sha256") != manifest_row.get("result_sha256")):
            raise ArchiveError("candidate generation metadata does not match the hashed checkpoint")

    artifact_refs = candidate.get("artifacts")
    if not isinstance(artifact_refs, list):
        raise ArchiveError("candidate artifact references are missing")
    refs = {row.get("path"): row for row in artifact_refs if isinstance(row, dict)}
    expected_refs = {"artifact_manifest.json"} | {
        row["path"] for row in rows if row.get("kind") == "generation_bundle"
    }
    if set(refs) != expected_refs:
        raise ArchiveError("candidate must reference the manifest and all sixty checkpoint bundles")
    for rel in expected_refs:
        item = refs[rel]
        file_path = manifest_path if rel == "artifact_manifest.json" else relative_file(output_root, rel)
        if (item.get("storage") != "kaggle-kernel-output"
                or item.get("sha256") != file_sha(file_path)
                or item.get("size_bytes") != file_path.stat().st_size):
            raise ArchiveError("candidate artifact reference differs from the downloaded output checksum")

    if manifest.get("file_count") not in (None, len(rows)):
        raise ArchiveError("manifest file_count disagrees with its file list")
    if manifest.get("total_size_bytes") not in (None, total_size):
        raise ArchiveError("manifest total_size_bytes disagrees with its file list")
    return candidate, manifest, rows


def prepare(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root).resolve()
    dataset_root = Path(args.dataset_root).resolve()
    if not SLUG.fullmatch(args.dataset_slug):
        raise ArchiveError("dataset slug must be owner/dataset-slug")
    candidate, manifest, manifest_rows = verify_outputs(output_root)
    if dataset_root.exists():
        shutil.rmtree(dataset_root)
    dataset_root.mkdir(parents=True)
    candidate_path = output_root / "receipt-candidate.json"
    manifest_path = output_root / "artifact_manifest.json"

    logical_files: list[dict[str, Any]] = [{
        "path": "artifact_manifest.json",
        "source": manifest_path,
        "sha256": file_sha(manifest_path),
        "size_bytes": manifest_path.stat().st_size,
        "kind": "artifact_manifest",
    }]
    for item in manifest_rows:
        logical_files.append({
            "path": item["path"],
            "source": relative_file(output_root, item["path"]),
            "sha256": item["sha256"],
            "size_bytes": item["size_bytes"],
            "kind": item["kind"],
            "seed": item.get("seed"),
            "generation": item.get("generation"),
            "scientific_status": item.get("scientific_status"),
            "evaluated": item.get("evaluated"),
            "result_sha256": item.get("result_sha256"),
        })

    index_rows = []
    for number, row in enumerate(sorted(logical_files, key=lambda r: r["path"]), start=1):
        dataset_file = f"artifact-{number:04d}.json"
        destination = dataset_root / dataset_file
        shutil.copyfile(row["source"], destination)
        index_rows.append({
            key: row[key] for key in (
                "path", "sha256", "size_bytes", "kind", "seed", "generation",
                "scientific_status", "evaluated", "result_sha256"
            ) if key in row and row[key] is not None
        } | {"dataset_path": dataset_file})

    index = {
        "schema": "ACSIE.kaggle-foundry-dataset-index.v1",
        "run_id": manifest["run_id"],
        "source_commit": manifest["source_commit"],
        "dataset_slug": args.dataset_slug,
        "logical_files": index_rows,
        "file_count": len(index_rows),
    }
    write_json(dataset_root / "archive-index.json", index)
    metadata = {
        "title": "ACSIE Foundry Checkpoints",
        "id": args.dataset_slug,
        "licenses": [{"name": "other"}],
        "subtitle": "Private, checksummed ACSIE Foundry run outputs",
        "description": (
            "Private versioned archive of a single ACSIE Foundry execution. "
            "Research outputs are not licensed for public redistribution. "
            "SHA-256 manifest and per-file path index are included."
        ),
    }
    write_json(dataset_root / "dataset-metadata.json", metadata)
    candidate_sha = file_sha(candidate_path)
    manifest_sha = file_sha(manifest_path)
    prepare_record = {
        "schema": "ACSIE.kaggle-foundry-dataset-prepare.v1",
        "run_id": manifest["run_id"],
        "source_commit": manifest["source_commit"],
        "dataset_slug": args.dataset_slug,
        "expected_seed_ids": list(SEEDS),
        "receipt_candidate_sha256": candidate_sha,
        "artifact_manifest_sha256": manifest_sha,
        "artifact_manifest_size_bytes": manifest_path.stat().st_size,
        "archive_index_sha256": file_sha(dataset_root / "archive-index.json"),
        "archive_index_size_bytes": (dataset_root / "archive-index.json").stat().st_size,
        "logical_files": index_rows,
        "prepared_dataset_file_count": len(index_rows) + 1,
    }
    write_json(Path(args.prepare_record), prepare_record)
    print(json.dumps({
        "archive_status": "PREPARED",
        "seed_count": 5,
        "generation_bundles": 60,
        "hashed_source_files": len(index_rows),
        "dataset_slug_configured": True,
    }, sort_keys=True))
    return 0


def parse_listing(path: Path) -> set[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ArchiveError("Kaggle private dataset file listing is unavailable") from exc
    try:
        reader = csv.DictReader(raw.splitlines())
        names: set[str] = set()
        for row in reader:
            if not row:
                continue
            value = next((v for k, v in row.items() if k and k.strip().lower() in {"name", "filename", "file_name"}), None)
            if value:
                names.add(Path(value.strip()).name)
        if names:
            return names
    except csv.Error:
        pass
    # Some CLI versions emit a simple table rather than CSV; fail closed if the
    # expected file names cannot be extracted instead of pretending listing verified.
    raise ArchiveError("Kaggle file-listing output was not parseable CSV")


def locate_downloaded(root: Path, name: str) -> Path:
    matches = [p for p in root.rglob(name) if p.is_file()]
    if len(matches) != 1:
        raise ArchiveError("an expected private dataset file was missing or ambiguous after download")
    return matches[0]


def attest(args: argparse.Namespace) -> int:
    prep = read_json(Path(args.prepare_record))
    output_root = Path(args.output_root).resolve()
    downloaded_root = Path(args.downloaded_root).resolve()
    if not SLUG.fullmatch(args.dataset_slug) or prep.get("dataset_slug") != args.dataset_slug:
        raise ArchiveError("dataset slug does not match the prepared archive")
    if args.dataset_version < 1 or args.observed_version != args.dataset_version:
        raise ArchiveError("dataset current-version check did not match the requested version")
    listing = parse_listing(Path(args.remote_listing))
    files = prep.get("logical_files")
    if not isinstance(files, list) or len(files) != 67:
        raise ArchiveError("prepare record has an incomplete list of 67 source files")
    expected_remote = {row["dataset_path"] for row in files} | {"archive-index.json"}
    if not expected_remote.issubset(listing):
        raise ArchiveError("Kaggle's current remote file listing does not include every expected archive file")

    verified_rows = []
    for row in files:
        source_path = output_root / row["path"] if row["path"] != "artifact_manifest.json" else output_root / "artifact_manifest.json"
        downloaded = locate_downloaded(downloaded_root, row["dataset_path"])
        actual_size = downloaded.stat().st_size
        actual_sha = file_sha(downloaded)
        if actual_size != row["size_bytes"] or actual_sha != row["sha256"]:
            raise ArchiveError("post-upload dataset download failed a per-file SHA-256 check")
        if source_path.is_file() and (source_path.stat().st_size != actual_size or file_sha(source_path) != actual_sha):
            raise ArchiveError("post-upload bytes differ from the previously validated kernel output")
        verified_rows.append({
            "path": row["path"],
            "dataset_path": row["dataset_path"],
            "sha256": actual_sha,
            "size_bytes": actual_size,
            "verified": True,
            "verification_method": "downloaded_sha256",
            "archived_version": args.dataset_version,
        })

    downloaded_index = locate_downloaded(downloaded_root, "archive-index.json")
    if file_sha(downloaded_index) != prep.get("archive_index_sha256"):
        raise ArchiveError("archive-index.json failed its post-upload SHA-256 check")
    manifest_path = output_root / "artifact_manifest.json"
    candidate_path = output_root / "receipt-candidate.json"
    attestation = {
        "schema": ATTESTATION_SCHEMA,
        "run_id": prep["run_id"],
        "source_commit": prep["source_commit"],
        "dispatch_nonce": prep.get("dispatch_nonce"),
        "expected_seed_ids": prep["expected_seed_ids"],
        "dataset_slug": args.dataset_slug,
        "dataset_version": args.dataset_version,
        "visibility": "private",
        "current_version_verified": True,
        "remote_file_listing_verified": True,
        "all_file_sha256_rechecked": len(verified_rows) == 67,
        "artifact_manifest_sha256": file_sha(manifest_path),
        "receipt_candidate_sha256": file_sha(candidate_path),
        "archive_index_sha256": prep["archive_index_sha256"],
        "archive_index_size_bytes": prep["archive_index_size_bytes"],
        "verified_files": verified_rows,
        "verification_counts": {
            "seed_summaries": 5,
            "generation_bundles": 60,
            "aggregate_summaries": 1,
            "manifest_files_rechecked": 67,
        },
    }
    if attestation["all_file_sha256_rechecked"] is not True:
        raise ArchiveError("not every source file was independently rehashed after upload")
    write_json(Path(args.attestation_output), attestation)
    print(json.dumps({
        "archive_status": "VERIFIED",
        "dataset_version": args.dataset_version,
        "verified_source_files": len(verified_rows),
        "generation_bundles": 60,
        "private_dataset_configured": True,
        "sha256_rechecks": len(verified_rows),
    }, sort_keys=True))
    return 0


def verify_private_dataset(args: argparse.Namespace) -> int:
    """Query Kaggle's authenticated dataset-view endpoint and fail closed unless private."""
    import base64
    import urllib.error
    import urllib.parse
    import urllib.request

    if not SLUG.fullmatch(args.dataset_slug):
        raise ArchiveError("dataset slug must be owner/dataset-slug")
    owner, slug = args.dataset_slug.split("/", 1)
    auth_header = None
    bearer = os.environ.get("KAGGLE_API_TOKEN", "").strip()
    if bearer.startswith("KGAT_"):
        auth_header = f"Bearer {bearer}"
    else:
        credentials_path = Path.home() / ".kaggle" / "kaggle.json"
        try:
            credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
            username = credentials.get("username")
            key = credentials.get("key")
        except (OSError, json.JSONDecodeError):
            username = key = None
        if not isinstance(username, str) or not isinstance(key, str) or not username or not key:
            raise ArchiveError("Kaggle authentication configuration is not available for privacy verification")
        token = base64.b64encode(f"{username}:{key}".encode("utf-8")).decode("ascii")
        auth_header = f"Basic {token}"

    url = "https://www.kaggle.com/api/v1/datasets/view/" + urllib.parse.quote(owner, safe="") + "/" + urllib.parse.quote(slug, safe="")
    request = urllib.request.Request(
        url,
        headers={"Authorization": auth_header, "Accept": "application/json", "User-Agent": "ACSIE-private-dataset-verifier"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ArchiveError("Kaggle dataset privacy/version metadata could not be verified") from exc
    if not isinstance(payload, dict):
        raise ArchiveError("Kaggle dataset privacy response was malformed")
    private = payload.get("isPrivate", payload.get("is_private"))
    if private is not True:
        raise ArchiveError("refusing to archive checkpoints because Kaggle did not confirm that the dataset is private")
    version = payload.get("currentVersionNumber", payload.get("current_version_number"))
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ArchiveError("Kaggle dataset response did not include a positive current version number")
    print(json.dumps({"privacy_status": "VERIFIED_PRIVATE", "current_version": version}, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--output-root", required=True)
    p.add_argument("--dataset-root", required=True)
    p.add_argument("--dataset-slug", required=True)
    p.add_argument("--prepare-record", required=True)
    p.set_defaults(func=prepare)
    v = commands.add_parser("verify-private")
    v.add_argument("--dataset-slug", required=True)
    v.set_defaults(func=verify_private_dataset)
    a = commands.add_parser("attest")
    a.add_argument("--prepare-record", required=True)
    a.add_argument("--output-root", required=True)
    a.add_argument("--downloaded-root", required=True)
    a.add_argument("--dataset-slug", required=True)
    a.add_argument("--dataset-version", required=True, type=int)
    a.add_argument("--observed-version", required=True, type=int)
    a.add_argument("--remote-listing", required=True)
    a.add_argument("--attestation-output", required=True)
    a.set_defaults(func=attest)
    args = parser.parse_args()
    try:
        return args.func(args)
    except (ArchiveError, OSError, json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
        # Error messages intentionally do not include paths, file contents, or tokens.
        print(f"ARCHIVE_NOT_VERIFIED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

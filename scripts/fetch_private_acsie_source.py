#!/usr/bin/env python3
"""Fetch the exact private ACSIE Python source snapshot without public checkout logs."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request


API = "https://api.github.com"


class SourceFetchError(RuntimeError):
    pass


def get_json(url: str, token: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ACSIE-private-source-stager",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise SourceFetchError("private source API request failed") from exc
    if not isinstance(value, dict):
        raise SourceFetchError("private source API response was malformed")
    return value


def git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def safe_source_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise SourceFetchError("private source tree contains an unsafe path")
    if path.parts[0] not in {"cognitive_core", "research"}:
        raise SourceFetchError("private source tree entry is outside the allowed source roots")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()

    token = os.environ.get("ACSIE_READ_TOKEN", "").strip()
    if not token:
        print("ACSIE_SOURCE_FETCH_FAILED: missing scoped token", file=sys.stderr)
        return 2
    if args.repository != "Infrasigma/ACSIE":
        print("ACSIE_SOURCE_FETCH_FAILED: unexpected source repository", file=sys.stderr)
        return 2
    if args.ref in {"main", "refs/heads/main"}:
        print("ACSIE_SOURCE_FETCH_FAILED: main is not an eligible source ref", file=sys.stderr)
        return 2

    repo = urllib.parse.quote(args.repository, safe="/")
    ref = urllib.parse.quote(args.ref, safe="")
    try:
        commit = get_json(f"{API}/repos/{repo}/commits/{ref}", token)
        commit_sha = commit.get("sha")
        tree_sha = commit.get("commit", {}).get("tree", {}).get("sha")
        if (not isinstance(commit_sha, str) or len(commit_sha) != 40
                or not isinstance(tree_sha, str) or len(tree_sha) != 40):
            raise SourceFetchError("commit provenance was incomplete")
        tree = get_json(f"{API}/repos/{repo}/git/trees/{tree_sha}?recursive=1", token)
        if tree.get("truncated") is True or not isinstance(tree.get("tree"), list):
            raise SourceFetchError("source tree listing is truncated or malformed")

        entries = []
        for row in tree["tree"]:
            if not isinstance(row, dict) or row.get("type") != "blob":
                continue
            path = row.get("path")
            if (isinstance(path, str) and path.endswith(".py")
                    and (path.startswith("cognitive_core/") or path.startswith("research/"))):
                safe_source_path(path)
                if not isinstance(row.get("sha"), str) or len(row["sha"]) != 40:
                    raise SourceFetchError("source tree contains a malformed blob reference")
                entries.append((path, row["sha"], row.get("mode", "100644")))
        if not entries or not any(path == "research/gen3_learning_rule_foundry_v1.py" for path, _, _ in entries):
            raise SourceFetchError("the requested ref does not contain the Gen3 Foundry entrypoint")

        root = Path(args.destination).resolve()
        if root.exists():
            import shutil
            shutil.rmtree(root)
        root.mkdir(parents=True)
        seen = set()
        for path_text, expected_sha, mode in sorted(entries):
            if path_text in seen:
                raise SourceFetchError("source tree contains duplicate file paths")
            seen.add(path_text)
            blob = get_json(f"{API}/repos/{repo}/git/blobs/{expected_sha}", token)
            encoded = blob.get("content")
            if blob.get("encoding") != "base64" or not isinstance(encoded, str):
                raise SourceFetchError("source blob did not use base64 content")
            raw = base64.b64decode(encoded, validate=False)
            if git_blob_sha(raw) != expected_sha:
                raise SourceFetchError("private source blob SHA verification failed")
            target = root / safe_source_path(path_text)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            target.chmod(0o755 if mode == "100755" else 0o644)

        info = {
            "schema": "ACSIE.private-source-snapshot.v1",
            "repository": args.repository,
            "requested_ref": args.ref,
            "commit_sha": commit_sha,
            "tree_sha": tree_sha,
            "python_source_file_count": len(entries),
        }
        (root / "source-info.json").write_text(
            json.dumps(info, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"ACSIE_SOURCE_STAGED files={len(entries)}")
        return 0
    except (SourceFetchError, OSError, ValueError, TypeError, KeyError) as exc:
        # Deliberately omit source SHAs, paths, HTTP bodies, and private metadata.
        print("ACSIE_SOURCE_FETCH_FAILED: source snapshot could not be verified", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

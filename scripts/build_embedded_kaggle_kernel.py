#!/usr/bin/env python3
"""Build a private, mount-free Kaggle kernel from a verified source archive.

The generated runner is a transient deployment artifact. Never commit the
archive-bearing output directory to this public infrastructure repository.
"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import re
import shutil
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any

HEX64 = re.compile(r"^[0-9a-f]{64}$")
KERNEL_ID = re.compile(r"^[a-z0-9._-]+/[a-z0-9._-]+$")
ROOT_ANCHOR = "def _resolve_package_root() -> Path:"
ROOT_END = "\nROOT = _resolve_package_root()"
REQUIRED = (
    "run_kaggle_foundry.py",
    "source-manifest.json",
    "research/gen3_learning_rule_foundry_v1.py",
    "research/tests/test_emit_validated_receipt.py",
    "research/tests/test_gen3_foundry_generations.py",
    "scripts/archive_foundry_outputs.py",
    "scripts/tests/test_archive_foundry_outputs.py",
)


class BuildError(RuntimeError):
    pass


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_title_id(title: str, kernel_id: str) -> None:
    if not KERNEL_ID.fullmatch(kernel_id):
        raise BuildError("kernel ID must be owner/kernel-slug")
    if not isinstance(title, str) or not title.strip():
        raise BuildError("kernel title is required")
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if slug != kernel_id.split("/", 1)[1]:
        raise BuildError("kernel title slug must match the requested kernel ID")


def make_resolver(expected_sha256: str, encoded_archive: str) -> str:
    chunks = [encoded_archive[i:i + 100] for i in range(0, len(encoded_archive), 100)]
    constant = (
        f"EMBEDDED_SOURCE_SHA256 = {expected_sha256!r}\n"
        "EMBEDDED_SOURCE_B64 = (\n"
        + "".join(f"    {chunk!r}\n" for chunk in chunks)
        + ")\n\n"
    )
    resolver = '''def _resolve_package_root() -> Path:
    """Resolve only the embedded source archive; no Kaggle dataset mounts."""
    here = Path(__file__).resolve().parent
    required = (
        "run_kaggle_foundry.py",
        "source-manifest.json",
        "research/gen3_learning_rule_foundry_v1.py",
        "research/tests/test_emit_validated_receipt.py",
        "research/tests/test_gen3_foundry_generations.py",
        "scripts/archive_foundry_outputs.py",
        "scripts/tests/test_archive_foundry_outputs.py",
    )

    def is_package(candidate: Path) -> bool:
        return candidate.is_dir() and all((candidate / item).is_file() for item in required)

    if is_package(here):
        raise RuntimeError("embedded deployment unexpectedly contains expanded source files")

    embedded = base64.b64decode(EMBEDDED_SOURCE_B64, validate=True)
    if hashlib.sha256(embedded).hexdigest() != EMBEDDED_SOURCE_SHA256:
        raise RuntimeError("embedded private source archive SHA-256 mismatch")

    destination = Path("/kaggle/working/_runtime_src")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(embedded), mode="r:gz") as archive:
        members = archive.getmembers()
        seen = set()
        for member in members:
            member_path = PurePosixPath(member.name)
            if (member_path.is_absolute() or ".." in member_path.parts
                    or "\\\\" in member.name or member.issym() or member.islnk()
                    or not (member.isfile() or member.isdir())):
                raise RuntimeError("embedded source archive contains an unsafe path")
            normalized = str(member_path)
            if normalized in seen:
                raise RuntimeError("embedded source archive contains a duplicate path")
            seen.add(normalized)
        archive.extractall(destination, members=members)
    if is_package(destination):
        return destination
    raise RuntimeError("embedded private source package extraction failed")
'''
    return constant + resolver


def build(
    template_dir: Path,
    archive_path: Path,
    output_dir: Path,
    expected_sha256: str,
    kernel_id: str,
    title: str,
    enable_gpu: bool = False,
    profile_only: bool = False,
) -> dict[str, Any]:
    if not HEX64.fullmatch(expected_sha256):
        raise BuildError("expected archive SHA-256 must be 64 lowercase hex characters")
    validate_title_id(title, kernel_id)
    template_dir = template_dir.resolve()
    archive_path = archive_path.resolve()
    output_dir = output_dir.resolve()
    if (output_dir == template_dir or template_dir in output_dir.parents
            or output_dir in template_dir.parents):
        raise BuildError("output directory must not overlap the source template directory")
    if (archive_path == output_dir or output_dir in archive_path.parents
            or archive_path in output_dir.parents):
        raise BuildError("output directory must not overlap the source archive")

    runner_template = template_dir / "run_kaggle_foundry.py"
    metadata_template = template_dir / "kernel-metadata.json"
    if not runner_template.is_file() or not metadata_template.is_file() or not archive_path.is_file():
        raise BuildError("template runner, metadata, or source archive is missing")

    archive_bytes = archive_path.read_bytes()
    if sha256_bytes(archive_bytes) != expected_sha256:
        raise BuildError("source archive SHA-256 does not match the expected digest")
    if len(archive_bytes) > 20 * 1024 * 1024:
        raise BuildError("source archive exceeds the 20 MiB packaging limit")

    try:
        with tarfile.open(fileobj=__import__("io").BytesIO(archive_bytes), mode="r:gz") as archive:
            members = archive.getmembers()
    except (tarfile.TarError, OSError) as exc:
        raise BuildError("source archive is not a valid gzip tar archive") from exc
    names = {str(PurePosixPath(m.name)) for m in members}
    if not set(REQUIRED).issubset(names):
        raise BuildError("source archive omits one or more required runtime files")
    for member in members:
        path = PurePosixPath(member.name)
        if (path.is_absolute() or ".." in path.parts or "\\" in member.name
                or member.issym() or member.islnk()
                or not (member.isfile() or member.isdir())):
            raise BuildError("source archive contains an unsafe member")

    source = runner_template.read_text(encoding="utf-8")
    if ROOT_ANCHOR not in source or ROOT_END not in source:
        raise BuildError("template runner has no recognized package resolver")
    if "EMBEDDED_SOURCE_B64" in source:
        raise BuildError("template runner is already an embedded runner")
    deployment_marker = "DEPLOYMENT_KERNEL_ID = None"
    if source.count(deployment_marker) != 1:
        raise BuildError("template runner must contain exactly one deployment kernel ID marker")
    source = source.replace(deployment_marker, f"DEPLOYMENT_KERNEL_ID = {kernel_id!r}", 1)
    gpu_marker = "DEPLOYMENT_GPU_REQUESTED = False"
    if source.count(gpu_marker) != 1:
        raise BuildError("template runner must contain exactly one GPU request marker")
    source = source.replace(
        gpu_marker, f"DEPLOYMENT_GPU_REQUESTED = {bool(enable_gpu)!r}", 1
    )
    profile_marker = "DEPLOYMENT_PROFILE_ONLY = False"
    if source.count(profile_marker) != 1:
        raise BuildError("template runner must contain exactly one profile-only marker")
    source = source.replace(
        profile_marker, f"DEPLOYMENT_PROFILE_ONLY = {bool(profile_only)!r}", 1
    )
    start = source.index(ROOT_ANCHOR)
    end = source.index(ROOT_END, start)
    old_resolver = source[start:end]
    if "Path('/kaggle/input')" not in old_resolver and 'Path("/kaggle/input")' not in old_resolver:
        raise BuildError("template resolver does not match the expected dataset-mount implementation")

    encoded = base64.b64encode(archive_bytes).decode("ascii")
    new_resolver = make_resolver(expected_sha256, encoded)
    source = source[:start] + new_resolver + source[end:]

    def has_top_level_import(module: str, imported_name: str | None = None) -> bool:
        for node in ast.parse(source).body:
            if isinstance(node, ast.Import):
                if imported_name is None and any(alias.name == module for alias in node.names):
                    return True
            elif isinstance(node, ast.ImportFrom) and node.module == module:
                if imported_name is None or any(alias.name == imported_name for alias in node.names):
                    return True
        return False

    import_specs = (
        ("base64", None, "import base64\n"),
        ("io", None, "import io\n"),
        ("tarfile", None, "import tarfile\n"),
        ("shutil", None, "import shutil\n"),
        ("pathlib", "PurePosixPath", "from pathlib import PurePosixPath\n"),
    )
    marker = "import hashlib\n"
    if marker not in source:
        raise BuildError("template runner lacks the import insertion anchor")
    for module, imported_name, statement in import_specs:
        if not has_top_level_import(module, imported_name):
            source = source.replace(marker, statement + marker, 1)

    # The standalone runner intentionally lacks expanded sources, forcing extraction.
    metadata = json.loads(metadata_template.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise BuildError("kernel metadata must be a JSON object")
    if str(metadata.get("is_private", "")).lower() != "true":
        raise BuildError("kernel metadata must already specify private visibility")
    if str(metadata.get("enable_internet", "")).lower() != "false":
        raise BuildError("kernel metadata must have internet disabled")
    if str(metadata.get("enable_gpu", "")).lower() != "false":
        raise BuildError("template metadata must default to GPU disabled; request GPU with --enable-gpu")
    metadata["id"] = kernel_id
    metadata["title"] = title
    metadata["enable_gpu"] = "true" if enable_gpu else "false"
    metadata["dataset_sources"] = []

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "run_kaggle_foundry.py").write_text(source, encoding="utf-8")
    (output_dir / "kernel-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    compile(source, str(output_dir / "run_kaggle_foundry.py"), "exec")
    tree = ast.parse(source)
    encoded_expr = next(
        node.value for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "EMBEDDED_SOURCE_B64" for target in node.targets)
    )
    roundtrip = base64.b64decode(ast.literal_eval(encoded_expr), validate=True)
    if sha256_bytes(roundtrip) != expected_sha256 or roundtrip != archive_bytes:
        raise BuildError("embedded archive round-trip verification failed")
    loaded_metadata = json.loads((output_dir / "kernel-metadata.json").read_text(encoding="utf-8"))
    if (loaded_metadata.get("dataset_sources") != [] or loaded_metadata.get("id") != kernel_id
            or f"DEPLOYMENT_KERNEL_ID = {kernel_id!r}" not in source
            or f"DEPLOYMENT_GPU_REQUESTED = {bool(enable_gpu)!r}" not in source
            or f"DEPLOYMENT_PROFILE_ONLY = {bool(profile_only)!r}" not in source
            or str(loaded_metadata.get("enable_gpu", "")).lower() != str(bool(enable_gpu)).lower()):
        raise BuildError("generated kernel metadata or bound slug failed post-write verification")
    if any((output_dir / p).exists() for p in ("cognitive_core", "research", "source-manifest.json")):
        raise BuildError("expanded source was copied to the output; only the self-extractor may be deployed")

    return {
        "build_status": "PASSED",
        "kernel_id": kernel_id,
        "deployment_kernel_id_bound": True,
        "profile_only": bool(profile_only),
        "is_private": True,
        "enable_internet": False,
        "enable_gpu": bool(enable_gpu),
        "dataset_sources_count": 0,
        "runner_bytes": (output_dir / "run_kaggle_foundry.py").stat().st_size,
        "runner_sha256": sha256_bytes((output_dir / "run_kaggle_foundry.py").read_bytes()),
        "embedded_archive_bytes": len(archive_bytes),
        "embedded_archive_sha256": expected_sha256,
        "embedded_roundtrip": "PASSED",
        "expanded_source_files_in_output": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-dir", required=True, type=Path)
    parser.add_argument("--source-archive", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--kernel-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument(
        "--enable-gpu",
        action="store_true",
        help="request Kaggle GPU hardware; this does not itself GPU-accelerate the CPU-based research code",
    )
    parser.add_argument(
        "--profile-only",
        action="store_true",
        help="run the diagnostic one-generation profile and exit without the frozen 5x12 run",
    )
    args = parser.parse_args()
    try:
        result = build(
            args.template_dir, args.source_archive, args.output_dir,
            args.expected_sha256, args.kernel_id, args.title,
            enable_gpu=args.enable_gpu,
            profile_only=args.profile_only,
        )
    except (BuildError, OSError, ValueError, KeyError, json.JSONDecodeError, StopIteration) as exc:
        print(f"EMBEDDED_KERNEL_BUILD_FAILED: {exc}", file=__import__("sys").stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

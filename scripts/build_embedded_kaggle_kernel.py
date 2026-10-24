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


def validate_kernel_slug_binding(source: str) -> int:
    """Reject receipt code that hard-codes a kernel slug instead of binding the deployment ID."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise BuildError("runner source is not valid Python") from exc

    fields = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if not (isinstance(key, ast.Constant) and key.value == "kernel_slug"):
                continue
            fields += 1
            if not (isinstance(value, ast.Name) and value.id == "DEPLOYMENT_KERNEL_ID"):
                raise BuildError(
                    "receipt kernel_slug must be dynamically bound to DEPLOYMENT_KERNEL_ID"
                )
    if fields == 0:
        raise BuildError("runner has no kernel_slug field to bind in its receipt")
    return fields


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _top_level_assignment(tree: ast.Module, name: str) -> Any:
    matches = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            matches.append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            matches.append(node.value)
    if len(matches) != 1:
        raise BuildError(f"staged runner must define exactly one {name} constant")
    try:
        return ast.literal_eval(matches[0])
    except (ValueError, TypeError) as exc:
        raise BuildError(f"staged runner {name} must be a literal constant") from exc


def validate_staged_kernel(kernel_dir: Path, expected_kernel_id: str) -> dict[str, Any]:
    """Fail closed before dispatch unless the staged runner embeds the complete verified Phase-0 archive."""
    if not KERNEL_ID.fullmatch(expected_kernel_id):
        raise BuildError("expected kernel ID must be owner/kernel-slug")
    kernel_dir = Path(kernel_dir).resolve()
    runner_path = kernel_dir / "run_kaggle_foundry.py"
    metadata_path = kernel_dir / "kernel-metadata.json"
    if not runner_path.is_file() or not metadata_path.is_file():
        raise BuildError("staged kernel is missing runner or metadata")
    try:
        source = runner_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError, json.JSONDecodeError) as exc:
        raise BuildError("staged runner or metadata cannot be parsed") from exc
    if not isinstance(metadata, dict) or metadata.get("id") != expected_kernel_id:
        raise BuildError("staged metadata kernel ID does not match dispatch target")
    if str(metadata.get("is_private", "")).lower() != "true":
        raise BuildError("staged kernel must be private")
    if str(metadata.get("enable_internet", "")).lower() != "false":
        raise BuildError("staged kernel must have internet disabled")
    if metadata.get("dataset_sources") != []:
        raise BuildError("staged embedded kernel must not use dataset mounts")
    deployment_id = _top_level_assignment(tree, "DEPLOYMENT_KERNEL_ID")
    if deployment_id != expected_kernel_id:
        raise BuildError("staged runner deployment ID does not match dispatch target")
    validate_kernel_slug_binding(source)
    declared_sha = _top_level_assignment(tree, "EMBEDDED_SOURCE_SHA256")
    encoded = _top_level_assignment(tree, "EMBEDDED_SOURCE_B64")
    if not isinstance(declared_sha, str) or not HEX64.fullmatch(declared_sha):
        raise BuildError("staged runner has no valid embedded archive SHA-256 constant")
    if not isinstance(encoded, str) or not encoded:
        raise BuildError("staged runner has no embedded source archive constant")
    try:
        archive_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise BuildError("staged embedded source archive is not valid base64") from exc
    observed_sha = sha256_bytes(archive_bytes)
    if observed_sha != declared_sha:
        raise BuildError("staged embedded archive SHA-256 does not match its declared digest")
    try:
        with tarfile.open(fileobj=__import__("io").BytesIO(archive_bytes), mode="r:gz") as archive:
            members = archive.getmembers()
            names: set[str] = set()
            normalized_names: set[str] = set()
            for member in members:
                path = PurePosixPath(member.name)
                normalized = str(path)
                if (path.is_absolute() or ".." in path.parts or "\\" in member.name
                        or member.issym() or member.islnk()
                        or not (member.isfile() or member.isdir())):
                    raise BuildError("staged embedded archive contains an unsafe member")
                if normalized in normalized_names:
                    raise BuildError("staged embedded archive contains a duplicate path")
                normalized_names.add(normalized)
                if member.isfile():
                    names.add(normalized)
            missing = sorted(set(REQUIRED) - names)
            if missing:
                raise BuildError("staged embedded archive omits required Phase-0/runtime files: " + ", ".join(missing))
            # Read required members through the in-memory tar stream to ensure each
            # path refers to an extractable regular file, not just a name in metadata.
            by_name = {str(PurePosixPath(m.name)): m for m in members if m.isfile()}
            for required in REQUIRED:
                content = archive.extractfile(by_name[required])
                if content is None:
                    raise BuildError("required embedded source member is not extractable: " + required)
                content.read(1)
    except BuildError:
        raise
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise BuildError("staged embedded source is not a valid gzip tar archive") from exc

    # The builder emits a self-extracting runner plus metadata only. Reject accidental
    # expanded-source staging so the uploaded bytes are exactly the validated payload.
    if any((kernel_dir / item).exists() for item in ("research", "cognitive_core", "source-manifest.json")):
        raise BuildError("staged output contains expanded/unverified source files")
    unexpected = {p.name for p in kernel_dir.iterdir()} - {"run_kaggle_foundry.py", "kernel-metadata.json"}
    if unexpected:
        raise BuildError("staged output contains unexpected files: " + ", ".join(sorted(unexpected)))
    return {
        "guard_status": "PASSED",
        "kernel_id": expected_kernel_id,
        "runner_sha256": sha256_bytes(runner_path.read_bytes()),
        "runner_bytes": runner_path.stat().st_size,
        "embedded_archive_sha256": observed_sha,
        "embedded_archive_bytes": len(archive_bytes),
        "required_files_verified": len(REQUIRED),
        "dataset_sources": [],
        "private": True,
        "internet_enabled": False,
        "receipt_slug_bound": True,
    }


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
    validate_kernel_slug_binding(source)
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

    # Validate the exact bytes written to the staging directory before build() may
    # report success. poll_kaggle_kernel repeats this check immediately before push.
    staged_guard = validate_staged_kernel(output_dir, kernel_id)

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
        "staged_payload_guard": staged_guard["guard_status"],
        "staged_guard_required_files_verified": staged_guard["required_files_verified"],
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

from __future__ import annotations

import ast
import hashlib
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts import build_embedded_kaggle_kernel as builder


TEMPLATE = '''#!/usr/bin/env python3
import hashlib
from pathlib import Path

DEPLOYMENT_KERNEL_ID = None


def _resolve_package_root() -> Path:
    here = Path(__file__).resolve().parent
    required = ("run_kaggle_foundry.py", "source-manifest.json")
    def is_package(candidate: Path) -> bool:
        return candidate.is_dir() and all((candidate / item).is_file() for item in required)
    if is_package(here):
        return here
    destination = Path("/kaggle/working/_runtime_src")
    if destination.exists():
        import shutil
        shutil.rmtree(destination)
    input_root = Path("/kaggle/input")
    return here

ROOT = _resolve_package_root()
'''


class BuildEmbeddedKernelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.template_dir = self.root / "template"
        self.template_dir.mkdir()
        (self.template_dir / "run_kaggle_foundry.py").write_text(TEMPLATE, encoding="utf-8")
        (self.template_dir / "kernel-metadata.json").write_text(json.dumps({
            "id": "memorican/test-kernel",
            "title": "Test Kernel",
            "code_file": "run_kaggle_foundry.py",
            "is_private": True,
            "enable_internet": False,
            "enable_gpu": False,
            "dataset_sources": ["memorican/private-source"],
        }), encoding="utf-8")
        self.archive_path = self.root / "source.tar.gz"
        self._make_archive()
        self.archive_sha = hashlib.sha256(self.archive_path.read_bytes()).hexdigest()
        self.output_dir = self.root / "generated-kernel"

    def tearDown(self):
        self.temp.cleanup()

    def _make_archive(self, add_unsafe=False):
        files = {}
        for name in builder.REQUIRED:
            files[name] = f"# fixture: {name}\n".encode("utf-8")
        if add_unsafe:
            files["../escape.txt"] = b"unsafe\n"
        source_root = self.root / "archive-files"
        source_root.mkdir(exist_ok=True)
        for name, body in files.items():
            target = source_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        with tarfile.open(self.archive_path, "w:gz") as archive:
            for name in files:
                archive.add(source_root / name, arcname=name)

    def _build(self, expected_sha=None, title="Test Kernel Embedded Source",
               kernel_id="memorican/test-kernel-embedded-source"):
        return builder.build(
            self.template_dir,
            self.archive_path,
            self.output_dir,
            expected_sha or self.archive_sha,
            kernel_id,
            title,
        )

    def test_builds_mount_free_private_runner_with_verified_archive(self):
        result = self._build()
        self.assertEqual(result["build_status"], "PASSED")
        self.assertEqual(result["dataset_sources_count"], 0)
        self.assertEqual(result["expanded_source_files_in_output"], 0)
        self.assertTrue((self.output_dir / "run_kaggle_foundry.py").is_file())
        self.assertTrue((self.output_dir / "kernel-metadata.json").is_file())
        self.assertEqual(sorted(p.name for p in self.output_dir.iterdir()),
                         ["kernel-metadata.json", "run_kaggle_foundry.py"])
        generated = (self.output_dir / "run_kaggle_foundry.py").read_text(encoding="utf-8")
        self.assertIn("EMBEDDED_SOURCE_SHA256", generated)
        self.assertIn("DEPLOYMENT_KERNEL_ID = 'memorican/test-kernel-embedded-source'", generated)
        self.assertNotIn("DEPLOYMENT_KERNEL_ID = None", generated)
        self.assertNotIn("/kaggle/input", generated)
        tree = ast.parse(generated)
        self.assertTrue(any(
            isinstance(node, ast.Import) and any(alias.name == "shutil" for alias in node.names)
            for node in tree.body
        ), "a nested-only template import must not be mistaken for a top-level import")
        expr = next(
            node.value for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "EMBEDDED_SOURCE_B64"
                    for target in node.targets)
        )
        import base64
        decoded = base64.b64decode(ast.literal_eval(expr), validate=True)
        self.assertEqual(hashlib.sha256(decoded).hexdigest(), self.archive_sha)
        metadata = json.loads((self.output_dir / "kernel-metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["dataset_sources"], [])
        self.assertTrue(metadata["is_private"])
        self.assertFalse(metadata["enable_internet"])
        self.assertFalse(metadata["enable_gpu"])

        # Execute the generated resolver with a temporary extraction path so the
        # self-extraction branch is exercised without creating /kaggle directories.
        runtime_root = self.root / "simulated-kaggle-working" / "_runtime_src"
        runtime_root.parent.mkdir(parents=True)
        simulated = generated.replace(
            'Path("/kaggle/working/_runtime_src")',
            f'Path({str(runtime_root)!r})',
        )
        namespace = {"__file__": str(self.output_dir / "run_kaggle_foundry.py"),
                     "__name__": "_generated_runner_test"}
        exec(compile(simulated, namespace["__file__"], "exec"), namespace)
        self.assertEqual(Path(namespace["ROOT"]), runtime_root)
        research_entry = runtime_root / "research/gen3_learning_rule_foundry_v1.py"
        self.assertTrue(research_entry.is_file())
        sentinel = runtime_root / "stale-sentinel.txt"
        sentinel.write_text("must be removed before re-extraction", encoding="utf-8")
        exec(compile(simulated, namespace["__file__"], "exec"), namespace)
        self.assertFalse(sentinel.exists(), "existing extraction should be replaced from the verified archive")

    def test_rejects_sha256_mismatch_before_output(self):
        with self.assertRaisesRegex(builder.BuildError, "SHA-256"):
            self._build(expected_sha="0" * 64)
        self.assertFalse(self.output_dir.exists())

    def test_rejects_title_that_would_create_different_kernel_slug(self):
        with self.assertRaisesRegex(builder.BuildError, "title slug"):
            self._build(title="Wrong Slug")

    def test_rejects_public_or_network_enabled_metadata(self):
        metadata_path = self.template_dir / "kernel-metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["is_private"] = False
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        with self.assertRaisesRegex(builder.BuildError, "private visibility"):
            self._build()

    def test_rejects_unsafe_archive_members(self):
        self._make_archive(add_unsafe=True)
        digest = hashlib.sha256(self.archive_path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(builder.BuildError, "unsafe member"):
            self._build(expected_sha=digest)


if __name__ == "__main__":
    unittest.main()

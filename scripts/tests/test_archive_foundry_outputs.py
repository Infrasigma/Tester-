import hashlib
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from scripts import archive_foundry_outputs as archive


SEEDS = (771221, 771222, 771223, 771224, 771225)
RESULT_HASH = "d" * 64


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_output(root: Path):
    (root / "checkpoints").mkdir(parents=True)
    (root / "seed-results").mkdir()
    files = []
    artifact_refs = []
    seed_rows = []
    total_size = 0

    for seed in SEEDS:
        generations = []
        for generation in range(12):
            record = {
                "generation": generation,
                "scientific_status": "INCONCLUSIVE",
                "evaluated": False,
                "reason": "test fixture not a scientific pass",
                "result_sha256": RESULT_HASH,
            }
            relative = f"checkpoints/seed-{seed}/generation-{generation:02d}.json"
            bundle_path = root / relative
            write_json(bundle_path, {
                "schema": "ACSIE.gen3-foundry-generation-checkpoint.v1",
                "seed": seed,
                "generation": generation,
                "generation_record": record,
                "native_state": {"fixture": True},
            })
            size = bundle_path.stat().st_size
            digest = sha(bundle_path)
            files.append({
                "path": relative,
                "sha256": digest,
                "size_bytes": size,
                "kind": "generation_bundle",
                "seed": seed,
                "generation": generation,
                "scientific_status": "INCONCLUSIVE",
                "evaluated": False,
                "result_sha256": RESULT_HASH,
            })
            artifact_refs.append({
                "storage": "kaggle-kernel-output",
                "path": relative,
                "sha256": digest,
                "size_bytes": size,
            })
            generations.append({
                "generation": generation,
                "scientific_status": "INCONCLUSIVE",
                "evaluated": False,
                "result_sha256": RESULT_HASH,
            })
            total_size += size

        summary = root / f"seed-results/result-{seed}.json"
        write_json(summary, {"seed": seed, "scientific_status": "INCONCLUSIVE", "generations": generations})
        files.append({
            "path": summary.relative_to(root).as_posix(),
            "sha256": sha(summary),
            "size_bytes": summary.stat().st_size,
            "kind": "seed_summary",
            "seed": seed,
        })
        total_size += summary.stat().st_size
        seed_rows.append({
            "seed": seed,
            "scientific_status": "INCONCLUSIVE",
            "generations": generations,
        })

    summary = root / "foundry-summary.json"
    write_json(summary, {"seed_count": 5, "scientific_status": "FAILED"})
    files.append({
        "path": "foundry-summary.json",
        "sha256": sha(summary),
        "size_bytes": summary.stat().st_size,
        "kind": "foundry_summary",
    })
    total_size += summary.stat().st_size

    manifest = {
        "schema": "ACSIE.kaggle-foundry-artifact-manifest.v1",
        "run_id": "unit-test-run-001",
        "source_commit": "a" * 40,
        "dispatch_nonce": "test-run-001",
        "expected_seed_ids": list(SEEDS),
        "expected_generations_per_seed": 12,
        "files": files,
        "file_count": len(files),
        "total_size_bytes": total_size,
    }
    manifest_path = root / "artifact_manifest.json"
    write_json(manifest_path, manifest)
    artifact_refs.insert(0, {
        "storage": "kaggle-kernel-output",
        "path": "artifact_manifest.json",
        "sha256": sha(manifest_path),
        "size_bytes": manifest_path.stat().st_size,
    })
    candidate = {
        "candidate_schema": "ACSIE.kaggle-foundry-candidate.v1",
        "run_id": "unit-test-run-001",
        "source": {"repository": "Infrasigma/ACSIE", "commit_sha": "a" * 40},
        "provenance": {"dispatch_nonce": "test-run-001"},
        "expected_seed_ids": list(SEEDS),
        "seed_results": seed_rows,
        "artifacts": artifact_refs,
    }
    write_json(root / "receipt-candidate.json", candidate)


class ArchiveFoundryOutputsTests(unittest.TestCase):
    def test_prepare_creates_flat_archive_with_manifest_and_67_verifiable_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_root = root / "kernel"
            output_root.mkdir()
            build_output(output_root)
            dataset_root = root / "dataset"
            prepare_record = root / "prepare.json"
            result = archive.prepare(Namespace(
                output_root=str(output_root),
                dataset_root=str(dataset_root),
                dataset_slug="memorican/acsie-foundry-checkpoints",
                prepare_record=str(prepare_record),
                expected_dispatch_nonce="test-run-001",
            ))
            self.assertEqual(result, 0)
            index = json.loads((dataset_root / "archive-index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["file_count"], 67)
            self.assertEqual(len(list(dataset_root.glob("artifact-*.json"))), 67)
            metadata = json.loads((dataset_root / "dataset-metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["id"], "memorican/acsie-foundry-checkpoints")
            self.assertFalse(any(path.is_dir() for path in dataset_root.iterdir()))
            record = json.loads(prepare_record.read_text(encoding="utf-8"))
            self.assertEqual(record["prepared_dataset_file_count"], 68)

    def test_prepare_rejects_manifest_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_root = root / "kernel"
            output_root.mkdir()
            build_output(output_root)
            tamper = output_root / "checkpoints/seed-771221/generation-00.json"
            tamper.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(archive.ArchiveError, "SHA-256"):
                archive.verify_outputs(output_root)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.poll_kaggle_kernel import BuildError, candidate_dispatch_error, main


class PollKernelReceiptBindingTests(unittest.TestCase):
    def test_accepts_candidate_for_exact_nonce_and_kernel_slug(self):
        candidate = {
            "provenance": {"dispatch_nonce": "nonce-001"},
            "execution": {"kernel_slug": "memorican/test-kernel"},
        }
        self.assertIsNone(
            candidate_dispatch_error(candidate, "nonce-001", "memorican/test-kernel")
        )

    def test_rejects_same_nonce_with_stale_kernel_slug(self):
        candidate = {
            "provenance": {"dispatch_nonce": "nonce-001"},
            "execution": {"kernel_slug": "memorican/acsie-gen3-foundry"},
        }
        self.assertEqual(
            candidate_dispatch_error(candidate, "nonce-001", "memorican/acsie-gen3-foundry-embedded-source"),
            "kernel_slug_mismatch",
        )

    def test_rejects_candidate_from_another_dispatch(self):
        candidate = {
            "provenance": {"dispatch_nonce": "old-nonce"},
            "execution": {"kernel_slug": "memorican/test-kernel"},
        }
        self.assertEqual(
            candidate_dispatch_error(candidate, "current-nonce", "memorican/test-kernel"),
            "dispatch_nonce_mismatch",
        )

    def test_rejects_candidate_without_execution_identity(self):
        candidate = {"provenance": {"dispatch_nonce": "nonce-001"}}
        self.assertEqual(
            candidate_dispatch_error(candidate, "nonce-001", "memorican/test-kernel"),
            "candidate_execution_missing",
        )

    def test_failed_staged_guard_blocks_push_before_any_kaggle_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            (stage / "kernel-metadata.json").write_text(json.dumps({"id": "memorican/test-kernel"}), encoding="utf-8")
            (stage / "run_kaggle_foundry.py").write_text("# deliberately rejected by the guard\n", encoding="utf-8")
            argv = ["poll_kaggle_kernel.py", "--kernel-slug", "memorican/test-kernel",
                    "--path", str(stage), "--dispatch-nonce", "nonce-guard"]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch("scripts.poll_kaggle_kernel.validate_staged_kernel", side_effect=BuildError("bad embedded bundle")) as guard, \
                 mock.patch("scripts.poll_kaggle_kernel.run") as run_command:
                self.assertEqual(main(), 2)
                guard.assert_called_once_with(stage, "memorican/test-kernel")
                run_command.assert_not_called()


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from scripts.poll_kaggle_kernel import candidate_dispatch_error


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


if __name__ == "__main__":
    unittest.main()

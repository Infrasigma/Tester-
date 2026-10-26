import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("run_kaggle_foundry_tested", ROOT / "run_kaggle_foundry.py")
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


def gates(ok=True):
    return [{"name": "sample_gate", "value": 0.2, "operator": ">=", "threshold": 0.1, "passed": ok}]


def generation(number=0, status="PASSED", evaluated=True, gate_predicates=None, failed_gates=None):
    gate_predicates = gates() if gate_predicates is None else gate_predicates
    failed_gates = [] if failed_gates is None else failed_gates
    return {"generation": number, "scientific_status": status, "evaluated": evaluated,
            "result_sha256": "a" * 64, "gate_evaluation_status": "COMPLETE",
            "gate_predicates": gate_predicates, "failed_gates": failed_gates}


class FoundryGateTelemetryMatrixTests(unittest.TestCase):
    def test_passed_generation_preserves_compact_gate_pointer(self):
        row = runner.matrix_row({"seed": 771221, "scientific_status": "PASSED",
                                 "generations": [generation(i) for i in range(12)]}, 771221)
        item = row["generations"][0]
        self.assertEqual(item["gate_predicate_count"], 1)
        self.assertEqual(item["gate_predicates_sha256"], runner.canonical_sha256(gates()))
        self.assertEqual(item["failed_gates"], [])
        self.assertEqual(item["gate_evaluation_status"], "COMPLETE")

    def test_failed_generation_without_named_gate_is_rejected(self):
        rows = [generation(i) for i in range(12)]
        rows[3] = generation(3, status="FAILED", gate_predicates=gates(False), failed_gates=[])
        with self.assertRaisesRegex(ValueError, "FAILED without named failed_gates"):
            runner.matrix_row({"seed": 771221, "scientific_status": "FAILED", "generations": rows}, 771221)

    def test_failed_gate_names_must_match_failed_measured_predicates(self):
        rows = [generation(i) for i in range(12)]
        rows[3] = generation(3, status="FAILED", gate_predicates=gates(False), failed_gates=["different_gate"])
        with self.assertRaisesRegex(ValueError, "failed_gates disagree"):
            runner.matrix_row({"seed": 771221, "scientific_status": "FAILED", "generations": rows}, 771221)

    def test_non_evaluated_crash_can_report_not_evaluated_gate_telemetry(self):
        rows = [generation(i) for i in range(12)]
        rows[0] = {"generation": 0, "scientific_status": "CRASHED", "evaluated": False,
                   "result_sha256": "a" * 64, "gate_evaluation_status": "NOT_EVALUATED",
                   "gate_predicates": [], "failed_gates": []}
        row = runner.matrix_row({"seed": 771221, "scientific_status": "CRASHED", "generations": rows}, 771221)
        self.assertEqual(row["generations"][0]["gate_predicate_count"], 0)
        self.assertIsNone(row["generations"][0]["gate_predicates_sha256"])
        self.assertEqual(row["generations"][0]["gate_evaluation_status"], "NOT_EVALUATED")


if __name__ == "__main__":
    unittest.main()

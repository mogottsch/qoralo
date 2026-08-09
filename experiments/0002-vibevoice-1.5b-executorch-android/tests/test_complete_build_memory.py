import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "export" / "complete_build_memory.py"
SPEC = importlib.util.spec_from_file_location("complete_build_memory", MODULE_PATH)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def fixture(deployed, rss, pss, hwm, seconds=10.0, wav="same"):
    runs = []
    for label in ("cold", "warm"):
        runs.append({"protocol_run": label, "memory_kib": {"rss": rss, "pss": pss, "vmhwm": hwm},
                     "generation_seconds": seconds, "ttfa_seconds": seconds / 2,
                     "stop_reason": "CAPACITY"})
    return {"runs": runs, "size": {"module_bytes": 100, "deployed_module_bytes": deployed,
            "deployed_excess_bytes": deployed - 100, "exact_duplicate_bytes": 0},
            "summary": {"wav_sha256": wav, "cross_process_deterministic": True,
                        "median_generation_seconds": seconds},
            "failure": {"reason": "static capacity"}, "protocol": {"repetitions": 2}}


class CompleteBuildMemoryTest(unittest.TestCase):
    def test_direct_deltas_and_correctness(self):
        got = M.compare(fixture(180, 500, 450, 1600), fixture(100, 400, 350, 1600, 10.5), "abc")
        self.assertEqual(got["status"], "passed")
        self.assertEqual(got["package_bytes"]["deployed_module_bytes"]["reduction"], 80)
        self.assertEqual(got["memory_and_latency"][0]["rss_kib"]["reduction"], 100)
        self.assertEqual(got["memory_and_latency"][0]["vmhwm_kib"]["reduction"], 0)
        self.assertTrue(got["correctness"]["same_wav_sha256"])
        self.assertTrue(got["latency_regression_check"]["within_guardrail"])

    def test_changed_output_fails_even_if_memory_improves(self):
        got = M.compare(fixture(180, 500, 450, 1600), fixture(100, 400, 350, 1500, wav="changed"), "abc")
        self.assertEqual(got["status"], "failed")
        self.assertTrue(got["correctness"]["quality_regression"])

    def test_run_label_mismatch_rejected(self):
        optimized = fixture(100, 400, 350, 1500)
        optimized["runs"][0]["protocol_run"] = "other"
        with self.assertRaises(ValueError):
            M.compare(fixture(180, 500, 450, 1600), optimized, "abc")


if __name__ == "__main__":
    unittest.main()

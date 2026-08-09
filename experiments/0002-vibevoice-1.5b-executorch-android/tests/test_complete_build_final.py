import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "export" / "complete_build_final.py"
SPEC = importlib.util.spec_from_file_location("complete_build_final", MODULE_PATH)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def measurement(seconds, wav="wav"):
    run = {
        "component_seconds": {name: seconds for name in M.STAGES},
        "ttfa_seconds": seconds * 3,
        "generation_seconds": seconds * 10,
        "protocol_wall_seconds": seconds * 12,
        "rtf": seconds * 20,
        "memory_kib": {"rss": 10, "pss": 9, "vmhwm": 20},
        "stop_reason": "CAPACITY",
        "audio_duration_seconds": 6400 / 24000,
    }
    return {
        "runs": [run, dict(run)], "summary": {"cross_process_deterministic": True, "wav_sha256": wav},
        "size": {"module_bytes": 1, "apk_plus_modules_bytes": 2}, "failure": {"requested_duration_seconds": 13.066667},
        "device": {}, "runtime": {}, "thermal": {},
    }


class CompleteBuildFinalTest(unittest.TestCase):
    def test_metrics_and_reductions_are_reproducible(self):
        before = measurement(2.0)
        after = measurement(1.0)
        audio = {
            "status": "rejected", "duration": {"reference_seconds": 13, "android_seconds": .25, "coverage_ratio": .02},
            "waveform": {"android": {"rms_dbfs": -118}},
            "quality_rubric": {name: {"status": value} for name, value in
                (("omissions", "fail"), ("repetitions", "fail"), ("corruption", "fail"), ("speaker_consistency", "not_assessable"))},
        }
        got = M.build({"optimized_measurement": before}, after, audio, "abc")
        self.assertEqual(got["status"], "rejected_not_feasible")
        self.assertEqual(got["reduction"]["generation_wall_percent"], 50.0)
        self.assertTrue(got["correctness_and_determinism"]["same_wav_as_memory_baseline"])
        self.assertEqual(got["audio_comparison"]["omissions"], "fail")

    def test_variability_records_range_and_population_cv(self):
        got = M.variability([1.0, 3.0])
        self.assertEqual(got["range"], 2.0)
        self.assertEqual(got["population_cv"], 0.5)


if __name__ == "__main__":
    unittest.main()

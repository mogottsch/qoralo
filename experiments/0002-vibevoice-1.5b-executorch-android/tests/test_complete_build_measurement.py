import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "export" / "complete_build_measurement.py"
SPEC = importlib.util.spec_from_file_location("complete_build_measurement", MODULE_PATH)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class CompleteBuildCalculationsTest(unittest.TestCase):
    def test_package_size_counts_only_exact_duplicate_files(self):
        files = [
            {"bytes": 10, "sha256": "a"},
            {"bytes": 10, "sha256": "a"},
            {"bytes": 7, "sha256": "b"},
        ]
        got = M.package_size(files)
        self.assertEqual(got["module_bytes"], 27)
        self.assertEqual(got["exact_duplicate_groups"], 1)
        self.assertEqual(got["exact_duplicate_bytes"], 10)

    def test_run_calculations_report_capacity_prefix_without_overclaiming(self):
        chunk = {"diffusion_seconds": 2.0, "decoder_seconds": 3.0, "semantic_seconds": 4.0,
                 "connector_seconds": 0.25, "qwen_decode_seconds": 1.0}
        run = {"stop_reason": "CAPACITY", "pcm_samples": 6400, "elapsed_seconds": 20.0,
               "prefill": {"seconds": 5.0}, "chunks": [chunk, chunk], "rss_kib": 1,
               "pss_kib": 2, "vmhwm_kib": 3, "wav_sha256": "w", "pcm_sha256": "p",
               "tokens": [1, 2]}
        got = M.summarize_run("cold", {"status": "passed", "runs": [run, dict(run)]}, 22.0)
        self.assertAlmostEqual(got["audio_duration_seconds"], 6400 / 24000)
        self.assertAlmostEqual(got["rtf"], 75.0)
        self.assertAlmostEqual(got["ttfa_seconds"], 10.0)
        self.assertEqual(got["component_seconds"]["semantic_encoder"], 8.0)
        self.assertEqual(got["status"], "capacity_terminated")
        self.assertIsNone(got["module_load_seconds"])
        self.assertTrue(got["within_process_deterministic"])

    def test_build_result_is_precise_failure_for_short_runs(self):
        chunk = {"diffusion_seconds": 1, "decoder_seconds": 1, "semantic_seconds": 1,
                 "connector_seconds": 1, "qwen_decode_seconds": 1}
        run = {"stop_reason": "CAPACITY", "pcm_samples": 6400, "elapsed_seconds": 10,
               "prefill": {"seconds": 1}, "chunks": [chunk], "rss_kib": 1, "pss_kib": 1,
               "vmhwm_kib": 1, "wav_sha256": "same", "pcm_sha256": "same", "tokens": [3]}
        device = {"status": "passed", "runs": [run, dict(run)]}
        raw = {"runs": [{"label": "cold", "wall_seconds": 11, "device_result": device},
                        {"label": "warm", "wall_seconds": 11, "device_result": device}],
               "device": {}, "thermal": {}, "commands": []}
        preflight = {"status": "passed", "runtime": {}, "reference_wav": {"duration_seconds": 13.0,
                     "frames": 312000, "sha256": "ref"}, "packages": {"aggregate_sha256": "agg", "files": []}}
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / "app.apk"; apk.write_bytes(b"apk")
            got = M.build_result(raw, preflight, apk, "abc")
        self.assertEqual(got["status"], "precise_failure")
        self.assertFalse(got["failure"]["complete_locked_run"])
        self.assertTrue(got["summary"]["cross_process_deterministic"])
        self.assertEqual(got["size"]["apk_plus_modules_bytes"], 3)


if __name__ == "__main__":
    unittest.main()

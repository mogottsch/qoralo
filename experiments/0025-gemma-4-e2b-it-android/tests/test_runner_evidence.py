#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "finalize_runner_evidence", ROOT / "tools" / "finalize_runner_evidence.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PersistenceFirstRegressionTest(unittest.TestCase):
    def test_canonical_gpu_campaign_is_complete_provider_bound_and_hash_bound(self) -> None:
        result_dir = ROOT / "results/android-gpu-campaign"
        result = json.loads((result_dir / "result.json").read_text())
        runs = result["runs"]
        self.assertEqual("canonical_campaign_complete", result["status"])
        self.assertEqual(16, len(runs))
        self.assertEqual(1, sum(run["phase"] == "first" for run in runs))
        self.assertEqual(
            {"short": 5, "medium": 5, "long": 5},
            result["validation"]["loaded_route_counts"],
        )
        binding = result["gpu_provider_binding"]
        self.assertTrue(binding["binding_proven"])
        self.assertEqual(
            "kGpu only (no CPU fallback bit)",
            binding["litert_hardware_accelerators"],
        )
        self.assertTrue(binding["fully_delegated_to_single_delegate_hint"])
        self.assertIn("/dev/kgsl-3d0", binding["gpu_device_fds"])
        self.assertTrue(
            any("libLiteRtGpuAccelerator.so" in line for line in binding["mapped_provider_and_driver_libraries"])
        )
        self.assertTrue(
            any("libOpenCL.so" in line for line in binding["mapped_provider_and_driver_libraries"])
        )
        for index, run in enumerate(runs):
            self.assertTrue(run["runtime_input_token_count_matches"])
            self.assertIsNone(run["runtime_error"])
            self.assertFalse(run["session_recreation_in_total_request"])
            if index:
                self.assertEqual("fresh_session_per_logical_request", run["request_isolation_strategy"])
            output = result_dir / run["output"]["path"]
            self.assertEqual(run["output"]["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertEqual({"looks_sensible": True, "issue_notes": None}, run["output_sanity"])
        self.assertEqual("removed_and_verified_absent", result["remote_stage_cleanup"]["status"])

    def test_gpu_smoke_is_only_a_viability_milestone(self) -> None:
        result = json.loads((ROOT / "results/android-gpu-smoke/result.json").read_text())
        self.assertEqual("viability_passed_not_experiment_complete", result["status"])
        self.assertEqual(1, len(result["runs"]))
        self.assertTrue(result["gpu_provider_binding"]["binding_proven"])

    def test_approved_gpu_preflight_blocker_did_not_touch_phone(self) -> None:
        result = json.loads(
            (ROOT / "results/android-gpu-generic-preflight-blocker/result.json").read_text()
        )
        self.assertEqual("blocked_before_identity_capture", result["status"])
        self.assertFalse(result["stage_created"])
        self.assertFalse(result["process_launched"])
        self.assertFalse(result["remote_mutation"])
        self.assertFalse(result["gpu_provider_binding_tested"])
        self.assertTrue(result["phone_lock_released"])

    def test_gpu_blocker_never_claims_fallback_or_performance(self) -> None:
        result = json.loads(
            (ROOT / "results/android-gpu-blocker/result.json").read_text()
        )
        self.assertEqual("blocked_before_inference", result["status"])
        self.assertEqual(0, result["attempt"]["logical_requests_started"])
        self.assertFalse(result["blocker"]["cpu_fallback_used"])
        self.assertFalse(result["blocker"]["provider_binding_proven"])
        self.assertIn("GPU_ARTISAN", result["blocker"]["exact_error"])
        self.assertEqual(
            "removed_and_verified_absent", result["cleanup"]["status"]
        )

    def test_canonical_cpu_campaign_is_complete_and_hash_bound(self) -> None:
        result_dir = ROOT / "results/android-cpu-campaign"
        result = json.loads((result_dir / "result.json").read_text())
        runs = result["runs"]
        self.assertEqual(16, len(runs))
        self.assertEqual(1, sum(run["phase"] == "first" for run in runs))
        self.assertEqual(
            {"short": 5, "medium": 5, "long": 5},
            {
                tier: sum(
                    run["phase"] == "loaded_route" and run["tier"] == tier
                    for run in runs
                )
                for tier in ("short", "medium", "long")
            },
        )
        for index, run in enumerate(runs):
            self.assertTrue(run["runtime_input_token_count_matches"])
            self.assertIsNone(run["runtime_error"])
            self.assertFalse(run["session_recreation_in_total_request"])
            if index:
                self.assertEqual(
                    "fresh_session_per_logical_request",
                    run["request_isolation_strategy"],
                )
                self.assertGreater(run["session_recreation_seconds"], 0)
            output = result_dir / run["output"]["path"]
            self.assertEqual(
                run["output"]["sha256"],
                hashlib.sha256(output.read_bytes()).hexdigest(),
            )
            self.assertEqual(
                {"looks_sensible": True, "issue_notes": None},
                run["output_sanity"],
            )
        self.assertEqual("removed_and_verified_absent", result["remote_stage_cleanup"]["status"])
        self.assertEqual(0, result["validation"]["runner_exit_code"])

    def test_successful_output_survives_empty_optional_benchmark_turns(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            destination = base / "result"
            (source / "outputs").mkdir(parents=True)
            (source / "outputs" / "short.txt").write_text("A sensible response.\n")
            for tier in ("short", "medium", "long"):
                (source / f"rendered-{tier}.txt").write_text(f"rendered {tier}\n")
            raw = {
                "prompts": {
                    tier: {
                        "rendered_relative_path": f"rendered-{tier}.txt",
                        "token_ids": [2, 3, 4],
                    }
                    for tier in ("short", "medium", "long")
                },
                "runs": [
                    {
                        "id": "short-01",
                        "output_relative_path": "outputs/short.txt",
                        "emitted_token_ids": [10, 11, 12],
                        "runtime_benchmark_info": {
                            "prefill_turns_before": 0,
                            "prefill_turns_after": 0,
                            "decode_turns_before": 0,
                            "decode_turns_after": 0,
                        },
                        "timing": {"prefill_seconds": None},
                        "missing_reasons": {
                            "timing.prefill_seconds": "optional runtime turn absent"
                        },
                    }
                ],
            }
            (source / "runner-result.json").write_text(json.dumps(raw))

            result = MODULE.finalize(
                source, destination, "host_smoke", True, None
            )

            output = destination / result["runs"][0]["output"]["path"]
            self.assertEqual("A sensible response.\n", output.read_text())
            self.assertIsNone(result["runs"][0]["timing"]["prefill_seconds"])
            self.assertEqual(
                0,
                result["runs"][0]["runtime_benchmark_info"]["decode_turns_after"],
            )
            self.assertEqual(
                {"looks_sensible": True, "issue_notes": None},
                result["runs"][0]["output_sanity"],
            )


if __name__ == "__main__":
    unittest.main()

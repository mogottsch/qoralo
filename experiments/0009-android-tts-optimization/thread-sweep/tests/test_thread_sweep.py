from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
PLAN = json.loads((ROOT / "protocol" / "sweep-plan.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((ROOT / "descriptors" / "manifest.json").read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_plan(value: str) -> Path:
    return (ROOT / "protocol" / value).resolve()


class ThreadSweepContractTest(unittest.TestCase):
    def test_frozen_transcript_and_exact_variants(self) -> None:
        transcript = resolve_plan(PLAN["transcript"]["source"])
        payload = transcript.read_bytes()
        self.assertEqual(len(payload), 230)
        self.assertFalse(payload.endswith(b"\n"))
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f",
        )
        self.assertEqual(
            {candidate: spec["deployment_variant"] for candidate, spec in PLAN["candidates"].items()},
            {
                "pocket": "sherpa-onnx-pocket-tts-int8-2026-01-26",
                "kokoro": "kokoro-multi-lang-v1_0",
                "supertonic_3": "sherpa-onnx-supertonic-3-tts-int8-2026-05-11",
            },
        )
        self.assertEqual(PLAN["candidates"]["pocket"]["actual_voice"], "packaged Bria reference")
        self.assertFalse(PLAN["candidates"]["pocket"]["voice_match"])
        self.assertEqual(PLAN["candidates"]["kokoro"]["speaker_id"], 3)
        self.assertEqual(PLAN["candidates"]["supertonic_3"]["speaker_id"], 5)

    def test_order_is_a_balanced_complete_rotation(self) -> None:
        blocks = PLAN["thermal_and_order"]["blocks"]
        self.assertEqual(len(blocks), 3)
        all_rows = []
        for block in blocks:
            self.assertEqual(len(block), 3)
            self.assertEqual({row["candidate"] for row in block}, set(PLAN["candidates"]))
            self.assertEqual({row["threads"] for row in block}, {1, 2, 4})
            all_rows.extend((row["candidate"], row["threads"]) for row in block)
        self.assertEqual(len(all_rows), len(set(all_rows)))
        self.assertEqual(len(all_rows), 9)
        self.assertEqual(
            set(all_rows),
            {(candidate, threads) for candidate in PLAN["candidates"] for threads in (1, 2, 4)},
        )
        thermal = PLAN["thermal_and_order"]
        self.assertEqual(thermal["eligible_android_thermal_statuses"], ["NONE", "LIGHT"])
        self.assertEqual(thermal["ineligible_android_thermal_statuses"][0], "MODERATE")
        self.assertEqual(thermal["minimum_stabilization_seconds_between_runs"], 0)
        self.assertEqual(thermal["minimum_stabilization_seconds_between_blocks"], 0)
        self.assertNotIn("maximum_battery_temperature_c", thermal)
        self.assertNotIn("maximum_above_campaign_baseline_c", thermal)
        self.assertIn("do not use it as an eligibility gate", thermal["battery_temperature_policy"])
        amendment = PLAN["protocol_amendments"]
        self.assertEqual(len(amendment), 1)
        self.assertEqual(amendment[0]["effective_sequence"], 7)
        self.assertEqual(
            amendment[0]["supersedes_plan_sha256"],
            "ddbf787ad8e82cbb89a3295f4376b76ce3942333add7378053c4950f240ca7dc",
        )
        self.assertIn("below 5-10%", amendment[0]["interpretation_disclosure"])

    def test_status_only_thermal_gate_accepts_light_and_rejects_moderate(self) -> None:
        spec = importlib.util.spec_from_file_location("thread_sweep_runner", ROOT / "tools" / "run_sweep.py")
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class Commands:
            def run(self, argv, *, timeout=None):
                del timeout
                command = " ".join(argv)
                if "dumpsys thermalservice" in command:
                    return SimpleNamespace(returncode=0, stdout="Thermal Status: 1\n", stderr="")
                if "dumpsys battery" in command:
                    return SimpleNamespace(returncode=0, stdout="  temperature: 999\n", stderr="")
                raise AssertionError(f"unexpected command: {argv}")

        runner = module.SweepDeviceRunner(
            Commands(),
            lock_path=ROOT / "tests" / "unused.lock",
            artifact_dir=ROOT / "tests" / "unused-artifacts",
        )
        runner.serial = "test-serial"
        polls = runner.thermal_wait(baseline_c=-100.0, maximum_wait_seconds=0, poll_seconds=60)
        self.assertEqual(len(polls), 1)
        self.assertTrue(polls[0].eligible)
        self.assertEqual(polls[0].status, "STATUS_1")
        self.assertEqual(polls[0].battery_temperature_c, 99.9)
        self.assertTrue(module.thermal_is_eligible("NONE"))
        self.assertTrue(module.thermal_is_eligible("LIGHT"))
        self.assertTrue(module.thermal_is_eligible("STATUS_1"))
        self.assertFalse(module.thermal_is_eligible("MODERATE"))
        self.assertFalse(module.thermal_is_eligible("STATUS_2"))
        self.assertFalse(module.thermal_is_eligible(None))

        class ModerateCommands(Commands):
            def run(self, argv, *, timeout=None):
                result = super().run(argv, timeout=timeout)
                if "dumpsys thermalservice" in " ".join(argv):
                    result.stdout = "Thermal Status: 2\n"
                return result

        moderate = module.SweepDeviceRunner(
            ModerateCommands(),
            lock_path=ROOT / "tests" / "unused-moderate.lock",
            artifact_dir=ROOT / "tests" / "unused-moderate-artifacts",
        )
        moderate.serial = "test-serial"
        with self.assertRaises(module.ThermalEligibilityError):
            moderate.thermal_wait(baseline_c=None, maximum_wait_seconds=0, poll_seconds=10)

    def test_generated_descriptors_change_only_thread_count(self) -> None:
        self.assertEqual(len(MANIFEST["descriptors"]), 9)
        for row in MANIFEST["descriptors"]:
            generated_path = ROOT / "descriptors" / row["path"]
            source_path = resolve_plan(row["source_path"])
            self.assertEqual(generated_path.stat().st_size, row["bytes"])
            self.assertEqual(digest(generated_path), row["sha256"])
            self.assertEqual(digest(source_path), row["source_sha256"])
            generated = json.loads(generated_path.read_text(encoding="utf-8"))
            source = json.loads(source_path.read_text(encoding="utf-8"))
            self.assertEqual(source["num_threads"], 1)
            expected = dict(source)
            expected["num_threads"] = row["threads"]
            self.assertEqual(generated, expected)
            self.assertEqual(generated["provider"], "cpu")
            self.assertEqual(generated["warm_runs"], 3)
            self.assertEqual(generated["transcript_sha256"], MANIFEST["transcript_sha256"])

    def test_descriptor_generator_check_mode(self) -> None:
        result = subprocess.run(
            ["python3", str(ROOT / "tools" / "generate_descriptors.py"), "--check"],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_harness_change_is_narrow_and_build_was_gated(self) -> None:
        patch = (ROOT / "android" / "allow-four-threads.patch").read_text(encoding="utf-8")
        self.assertEqual(patch.count("@@"), 2)
        self.assertEqual(patch.count("numThreads != 1 && numThreads != 2 && numThreads != 4"), 1)
        self.assertIn("provider must be cpu", patch)
        provenance_path = ROOT / "results" / "build-provenance.json"
        self.assertTrue(provenance_path.is_file())
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        self.assertEqual(provenance["runtime"]["provider"], "cpu")
        self.assertEqual(provenance["runtime"]["aar_sha256"], PLAN["runtime"]["aar_sha256"])
        self.assertEqual(provenance["build"]["unit_tests"], "passed")
        self.assertEqual(provenance["build"]["build_result"], "passed")
        self.assertEqual(provenance["apk_inspection"]["abi"], "arm64-v8a")
        self.assertFalse(provenance["apk_inspection"]["bundled_models_archives_or_audio"])

    def test_completed_measured_report_contract(self) -> None:
        report_path = ROOT / "results" / "measured-thread-sweep.json"
        markdown_path = ROOT / "results" / "measured-thread-sweep.md"
        handoff_path = ROOT / "WORKER_HANDOFF.md"
        self.assertTrue(report_path.is_file())
        self.assertTrue(markdown_path.is_file())
        self.assertTrue(handoff_path.is_file())
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "measured_complete")
        self.assertTrue(report["no_estimated_cells"])
        self.assertEqual(len(report["configurations"]), 9)
        self.assertEqual(
            {(row["candidate"], row["threads"]) for row in report["configurations"]},
            {(candidate, threads) for candidate in PLAN["candidates"] for threads in (1, 2, 4)},
        )
        validation = report["validation"]
        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["wav_count"], 36)
        self.assertEqual(validation["independently_decoded_wav_count"], 36)
        self.assertEqual(validation["valid_nonempty_telemetry_file_count"], 9)
        self.assertTrue(validation["all_host_run_evidence_hashes_match"])
        self.assertEqual(
            report["interpretation_rules"]["required_disclosure"],
            "Differences below 5-10% are inconclusive.",
        )
        markdown = markdown_path.read_text(encoding="utf-8")
        handoff = handoff_path.read_text(encoding="utf-8")
        for text in (markdown, handoff):
            self.assertIn("Differences below 5", text)
            self.assertIn("NONE", text)
            self.assertIn("LIGHT", text)
            self.assertIn("MODERATE", text)

    def test_runner_contains_no_tuning_or_root_commands(self) -> None:
        runner = (ROOT / "tools" / "run_sweep.py").read_text(encoding="utf-8").lower()
        for forbidden in ("settings put", "adb root", " shell su ", "setprop "):
            self.assertNotIn(forbidden, runner)
        self.assertIn('"settings", "get", "global", "low_power"', runner)
        self.assertNotIn("generatewith", runner)  # the host never splits or synthesizes text itself
        self.assertNotIn("time.sleep(seconds)", runner)
        self.assertIn('"--resume-campaign"', runner)
        self.assertIn("verify_resume_ledger", runner)
        self.assertIn("verify_completed_run", runner)


if __name__ == "__main__":
    unittest.main()

import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((EXP / "protocol/experiment-contract.json").read_text())
RESULT_PATH = EXP / "results/host-context-smoke/host-context-functional-smoke.json"
RESULT = json.loads(RESULT_PATH.read_text())
CLEAN_PATH = EXP / "results/clean-host-setup/clean-setup-result.json"
CLEAN = json.loads(CLEAN_PATH.read_text())
PREPARATION_PATH = EXP / "results/phone-preparation.json"
PREPARATION = json.loads(PREPARATION_PATH.read_text())
TRANSPORT_PATH = EXP / "protocol/phone-transport-contract.json"
TRANSPORT = json.loads(TRANSPORT_PATH.read_text())
PHONE_RESULT_PATH = EXP / "results/phone-campaign/phone-result.json"
PHONE_RESULT = json.loads(PHONE_RESULT_PATH.read_text())
TRANSCRIPT_SHA = "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"
EXPECTED_GRAPHS = {
    "duration": "8a1875ef0f6960ca16fc06814509b1c3258e8f50b04a5d590d3ab6db8c775016",
    "text": "769fd1d257674e8624bdea941f7a903d9460051f9845b604cd2c2980f281a8c3",
    "vector": "f2318c54726a034dcc89aa9818a91f1c3db0e3067b9932c7c2dae65957897c7b",
    "vocoder": "35b90eeae4a01d06f82dccc903a63d23c95eb2d9095ffa0d62f2cf151817c7c7",
}


class HostContextSmokeTest(unittest.TestCase):
    def test_legacy_transcript_is_exact(self):
        payload = (EXP / "protocol/transcript.txt").read_bytes()
        self.assertEqual(len(payload), 230)
        self.assertFalse(payload.endswith(b"\n"))
        self.assertEqual(hashlib.sha256(payload).hexdigest(), TRANSCRIPT_SHA)
        self.assertEqual(RESULT["input"]["transcript"]["sha256"], TRANSCRIPT_SHA)

    def test_scope_is_pragmatic_0011_route(self):
        self.assertIn("experiment 0011", CONTRACT["scope"]["baseline_route"])
        self.assertEqual(CONTRACT["scope"]["latent_length"], 238)
        self.assertEqual(CONTRACT["scope"]["trimmed_samples"], 729746)
        self.assertEqual(CONTRACT["runtime"]["session.disable_cpu_ep_fallback"], "1")
        self.assertEqual(CONTRACT["minimum_measurements"]["fresh_process_setup_runs_per_arm"], 3)
        self.assertFalse(CONTRACT["minimum_measurements"]["setup_processes_run_inference"])
        self.assertEqual(CONTRACT["minimum_measurements"]["complete_generation_runs_per_e2e_process"], 6)

    def test_all_four_components_pass_functionally(self):
        self.assertEqual(set(RESULT["components"]), set(EXPECTED_GRAPHS))
        self.assertTrue(RESULT["aggregate"]["all_functional_checks_passed"])
        self.assertTrue(RESULT["aggregate"]["all_ort_node_events_qnn_only"])
        self.assertEqual(RESULT["aggregate"]["components"], 4)
        for name, component in RESULT["components"].items():
            self.assertEqual(component["source_graph"]["sha256"], EXPECTED_GRAPHS[name])
            self.assertTrue(all(component["functional_checks"].values()))
            self.assertTrue(component["profiles"]["generation_ort"]["qnn_only_nodes"])
            self.assertTrue(component["profiles"]["reload_ort"]["qnn_only_nodes"])
            self.assertTrue(component["profiles"]["generation_qnn"]["has_accelerator_execute_cycles"])
            self.assertTrue(component["profiles"]["reload_qnn"]["has_accelerator_execute_cycles"])
            self.assertTrue(component["profiles"]["generation_qnn"]["has_finalize_event"])
            self.assertTrue(component["profiles"]["reload_qnn"]["has_load_binary_event"])

    def test_external_context_artifacts_and_copied_evidence_are_hash_bound(self):
        total = 0
        evidence_root = EXP / "results/host-context-smoke"
        for component in RESULT["components"].values():
            descriptor = component["external_context"]["descriptor"]
            binary = component["external_context"]["binary"]
            self.assertRegex(descriptor["sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(binary["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(descriptor["bytes"], 0)
            self.assertGreater(binary["bytes"], 0)
            total += descriptor["bytes"] + binary["bytes"]
            for kind, copied in component["copied_evidence"].items():
                folder = "profiles" if "profile" in kind else "raw"
                path = evidence_root / folder / copied["path"]
                self.assertTrue(path.is_file(), path)
                self.assertEqual(path.stat().st_size, copied["bytes"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), copied["sha256"])
        self.assertEqual(total, RESULT["aggregate"]["total_external_context_bytes"])

    def test_overlap_is_explicit_and_timings_cannot_support_claims(self):
        exclusion = RESULT["coordination_and_timing_exclusion"]
        self.assertIn("overlapped experiment 0017", exclusion["reason"])
        self.assertFalse(exclusion["performance_claim_permitted"])
        self.assertFalse(exclusion["resource_claim_permitted"])
        self.assertEqual(len(exclusion["overlap_windows_utc"]), 3)
        self.assertIn("three clean fresh-process", exclusion["required_follow_up"])
        self.assertIn("isolated setup performance or speedup", RESULT["claim_boundary"]["not_established"])
        self.assertIn("physical phone HTP execution", RESULT["claim_boundary"]["not_established"])

    def test_clean_campaign_has_five_fresh_balanced_runs_per_arm(self):
        isolation = CLEAN["campaign_isolation"]
        self.assertEqual(isolation["fresh_processes_per_arm"], 5)
        self.assertTrue(isolation["fresh_container_per_run"])
        self.assertFalse(isolation["other_qnn_campaign_overlap"])
        self.assertFalse(isolation["phone_access"])
        self.assertEqual(
            isolation["balanced_schedule"],
            ["source", "context", "context", "source", "context", "source", "source", "context", "source", "context"],
        )
        self.assertIn("held by the parent shell for the full campaign", isolation["lock"])
        self.assertEqual(len(CLEAN["schedule"]), 10)
        self.assertTrue(all(item["exit_code"] == 0 for item in CLEAN["schedule"]))

    def test_clean_session_sequence_distribution_and_delta_are_exact(self):
        source = CLEAN["session_sequence"]["source"]
        context = CLEAN["session_sequence"]["context"]
        self.assertEqual(source["count"], 5)
        self.assertEqual(context["count"], 5)
        self.assertEqual(
            source["values_seconds"],
            [24.77686643799825, 24.01408597900081, 24.545940363997943, 24.731559668001864, 25.09281176800141],
        )
        self.assertEqual(
            context["values_seconds"],
            [0.20134365400008392, 0.20715009700143128, 0.1922275830002036, 0.18710627899781684, 0.2008688030000485],
        )
        comparison = CLEAN["comparison"]
        self.assertAlmostEqual(comparison["source_median_seconds"], source["median_seconds"])
        self.assertAlmostEqual(comparison["context_median_seconds"], context["median_seconds"])
        self.assertAlmostEqual(
            comparison["source_minus_context_median_seconds"],
            source["median_seconds"] - context["median_seconds"],
        )
        self.assertGreater(comparison["source_over_context_median_ratio"], 100.0)
        self.assertGreater(comparison["context_setup_reduction_percent"], 99.0)
        self.assertLess(comparison["context_setup_reduction_percent"], 100.0)

    def test_clean_artifacts_and_provider_boundary_match_functional_proof(self):
        for component, expected in EXPECTED_GRAPHS.items():
            self.assertEqual(
                CLEAN["artifact_identities"]["source"][component]["model"]["sha256"], expected
            )
            functional_context = RESULT["components"][component]["external_context"]
            clean_context = CLEAN["artifact_identities"]["context"][component]
            self.assertEqual(clean_context["model"]["sha256"], functional_context["descriptor"]["sha256"])
            self.assertEqual(
                clean_context["external_context_binary"]["sha256"], functional_context["binary"]["sha256"]
            )
        provider = CLEAN["provider_and_fallback_evidence"]
        self.assertEqual(
            provider["functional_companion"]["sha256"], hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest()
        )
        self.assertTrue(provider["functional_companion"]["same_artifact_identities"])
        self.assertTrue(provider["functional_companion"]["all_ort_node_events_qnn_only"])
        self.assertFalse(provider["physical_phone_proof"])
        self.assertIn("Profiling was disabled", provider["timed_processes"])

    def test_clean_raw_results_are_committed_and_hash_bound(self):
        root = EXP / "results/clean-host-setup/raw"
        for item in CLEAN["schedule"]:
            copied = item["raw_record"]
            path = root / copied["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(path.stat().st_size, copied["bytes"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), copied["sha256"])
        self.assertIn("inference latency or end-to-end RTF", CLEAN["claim_boundary"]["not_established"])
        self.assertIn("cold OS filesystem-cache behavior", CLEAN["claim_boundary"]["not_established"])

    def test_native_linux_adb_transport_is_frozen_safely(self):
        self.assertEqual(TRANSPORT["status"], "executed_passed")
        self.assertEqual(TRANSPORT["platform_adaptation"]["selected_transport"], "/usr/bin/adb")
        self.assertFalse(TRANSPORT["platform_adaptation"]["historical_path_present"])
        self.assertEqual(
            TRANSPORT["adb"]["sha256"],
            "506163fd859265bc895b64eeba28252fb0f7864decf8b42dac3cbf9711240f9f",
        )
        self.assertIn("not set", TRANSPORT["adb"]["ADB_LIBUSB"])
        self.assertEqual(TRANSPORT["lock"]["path"], "artifacts/locks/phone.lock")
        self.assertTrue(TRANSPORT["device_gate"]["exactly_one_authorized_device_state"])
        self.assertEqual(TRANSPORT["device_gate"]["serial"], "R5CW81PR8SY")
        self.assertFalse(TRANSPORT["safety"]["app_install"])

    def test_phone_runner_stage_is_prepared_but_not_executed(self):
        self.assertEqual(PREPARATION["status"], "phone_campaign_prepared_not_executed")
        self.assertTrue(PREPARATION["host_setup_review_input"]["accepted_by_pi"])
        self.assertEqual(PREPARATION["stage"]["manifest"]["entries"], 26)
        self.assertRegex(PREPARATION["stage"]["manifest"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("ARM aarch64", PREPARATION["runner"]["binary"]["file_output"])
        self.assertEqual(PREPARATION["runner"]["android_api"], 28)
        self.assertTrue(PREPARATION["runner"]["stage_executable"])
        self.assertEqual(PREPARATION["runner"]["stage_mode_octal"], "0o755")
        self.assertEqual(
            PREPARATION["runtime_adaptation"]["sha256"],
            "643c6f6fd3d2b375ca8f2407a1695acaf55320b8e947adc4284665640fdc3ae9",
        )
        self.assertFalse(PREPARATION["runtime_adaptation"]["historical_0011_binary_available"])
        self.assertFalse(PREPARATION["validation"]["phone_access_during_preparation"])
        self.assertEqual(PREPARATION["validation"]["stage_hash_check"], "passed")
        source_paths = {
            "source": EXP / "phone/supertonic_qnn_context_runner.cc",
            "build_script": EXP / "tools/build_phone_runner.sh",
        }
        for key, path in source_paths.items():
            record = PREPARATION["runner"][key]
            self.assertEqual(record["bytes"], path.stat().st_size)
            self.assertEqual(record["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        campaign_paths = {
            "script": EXP / "device/run_phone_campaign.sh",
            "local_stage_preflight": EXP / "tools/check_phone_stage_preflight.py",
        }
        for key, path in campaign_paths.items():
            record = PREPARATION["campaign"][key]
            self.assertEqual(record["bytes"], path.stat().st_size)
            self.assertEqual(record["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(
            PREPARATION["campaign"]["validator"]["sha256"],
            "579ccb6df80efa5c65cb47dad95ed89f00209bc573d8ed04adaa953e5b3cd09e",
        )

    def test_phone_campaign_is_bounded_and_source_absent_for_context(self):
        campaign = (EXP / "device/run_phone_campaign.sh").read_text()
        runner = (EXP / "phone/supertonic_qnn_context_runner.cc").read_text()
        validator = (EXP / "tools/validate_phone_campaign.py").read_text()
        self.assertIn('ADB=/usr/bin/adb', campaign)
        self.assertIn('flock -n 9', campaign)
        self.assertIn('unset ADB_LIBUSB', campaign)
        self.assertIn('for index in 1 2 3', campaign)
        self.assertIn('run_native source-e2e source e2e', campaign)
        self.assertIn('run_native context-e2e context e2e', campaign)
        self.assertIn('run_native context-proof context proof', campaign)
        self.assertLess(campaign.index("rm -rf '$REMOTE/source-models'"), campaign.index('run_native "context-setup-$index"'))
        self.assertIn('a.action == "e2e" ? 6 : 1', runner)
        self.assertIn('session.disable_cpu_ep_fallback', runner)
        self.assertIn('ep.context_file_path', runner)
        self.assertIn('if (a.action == "setup")', runner)
        self.assertIn('HISTORICAL_ACCEPTED_WAV', validator)
        self.assertIn('descriptive only; no numerical acceptance gate', validator)

    def test_failed_phone_attempt_is_preserved_as_pre_adb(self):
        blocker = json.loads((EXP / "results/phone-preflight-blocker.json").read_text())
        self.assertEqual(blocker["result"], "failed_closed_before_adb")
        self.assertEqual(blocker["exit_code"], 5)
        self.assertTrue(blocker["scope"]["phone_lock_acquired_nonblocking"])
        self.assertTrue(blocker["scope"]["phone_lock_released"])
        self.assertFalse(blocker["scope"]["adb_or_device_commands_executed"])
        self.assertFalse(blocker["scope"]["remote_stage_created"])
        self.assertEqual(blocker["scope"]["cleanup_verification"], "not_created")

    def test_completed_phone_campaign_setup_e2e_physical_and_cleanup(self):
        self.assertEqual(PHONE_RESULT["status"], "phone_campaign_passed")
        self.assertEqual(PHONE_RESULT["setup"]["source"]["sequence_values_seconds"], [22.1599, 21.6129, 20.9571])
        self.assertEqual(PHONE_RESULT["setup"]["context"]["sequence_values_seconds"], [0.785324, 0.496524, 0.497816])
        comparison = PHONE_RESULT["setup_comparison"]
        self.assertAlmostEqual(comparison["source_median_seconds"], 21.6129)
        self.assertAlmostEqual(comparison["context_median_seconds"], 0.497816)
        self.assertAlmostEqual(comparison["source_minus_context_median_seconds"], 21.115084)
        self.assertGreater(comparison["context_setup_reduction_percent"], 97.0)
        self.assertEqual(PHONE_RESULT["e2e"]["source"]["runner"]["runs"], 6)
        self.assertEqual(PHONE_RESULT["e2e"]["context"]["runner"]["runs"], 6)
        self.assertEqual(PHONE_RESULT["e2e"]["source"]["listening"]["status"], "accepted")
        self.assertEqual(PHONE_RESULT["e2e"]["context"]["listening"]["status"], "accepted")
        self.assertEqual(
            PHONE_RESULT["e2e"]["source"]["wav"]["sha256"],
            "47c30043ccc053fe11b908a383c2bc9996c003b85ec293bae122c5794294783c",
        )
        self.assertEqual(
            PHONE_RESULT["e2e"]["source"]["wav"]["sha256"],
            PHONE_RESULT["e2e"]["context"]["wav"]["sha256"],
        )
        self.assertTrue(PHONE_RESULT["source_vs_context_raw_comparison"]["byte_identical"])
        self.assertTrue(PHONE_RESULT["physical_proof"]["physical_qnn_htp_proven"])
        self.assertTrue(PHONE_RESULT["physical_proof"]["fallback_disabled"])
        self.assertTrue(PHONE_RESULT["physical_proof"]["source_onnx_unavailable"])
        for profile in PHONE_RESULT["physical_proof"]["ort_profiles"]:
            self.assertEqual(profile["providers"], ["QNNExecutionProvider"])
        for profile in PHONE_RESULT["physical_proof"]["qnn_profiles"]:
            self.assertEqual(set(profile["hvx_thread_values"]), {4})
            self.assertGreater(profile["rpc_events"], 0)
            self.assertGreater(profile["accelerator_us_events"], 0)
            self.assertGreater(profile["accelerator_cycle_events"], 0)
        self.assertEqual(PHONE_RESULT["context_source_unavailable_gate"], "passed")
        self.assertEqual(PHONE_RESULT["cleanup"]["remote_cleanup_exit_code"], 0)
        self.assertTrue(PHONE_RESULT["cleanup"]["remote_root_absence_verified"])
        self.assertTrue(PHONE_RESULT["cleanup"]["phone_lock_release_verified_nonblocking"])
        self.assertFalse(PHONE_RESULT["parser_incident"]["phone_rerun"])
        sample = EXP / "samples/supertonic-stable-softplus-qnn-context.wav"
        self.assertEqual(sample.stat().st_size, 1459536)
        self.assertEqual(
            hashlib.sha256(sample.read_bytes()).hexdigest(),
            "47c30043ccc053fe11b908a383c2bc9996c003b85ec293bae122c5794294783c",
        )

    def test_phone_evidence_manifest_and_raw_stdout_are_byte_preserved(self):
        root = EXP / "results/phone-campaign"
        for item in PHONE_RESULT["evidence_manifest"]:
            path = root / item["path"]
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.stat().st_size, item["bytes"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"])
        for arm in ("source", "context"):
            for run in PHONE_RESULT["setup"][arm]["runs"]:
                diagnostic = run["runner_output"]
                path = root / "evidence" / f"{arm}-setup-{run['run_index']}" / "stdout.json"
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), diagnostic["raw"]["sha256"])
        self.assertGreater(PHONE_RESULT["setup"]["source"]["runs"][0]["runner_output"]["stripped_prefix_bytes"], 0)
        self.assertEqual(PHONE_RESULT["setup"]["context"]["runs"][0]["runner_output"]["stripped_prefix_bytes"], 0)
        sidecar = json.loads((root / "sha256-manifest.json").read_text())
        for item in sidecar:
            path = root / item["path"]
            self.assertEqual(path.stat().st_size, item["bytes"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"])
        validator = EXP / "tools/validate_phone_campaign.py"
        finalizer = EXP / "tools/finalize_phone_campaign.py"
        self.assertEqual(PHONE_RESULT["execution"]["offline_validator"]["sha256"], hashlib.sha256(validator.read_bytes()).hexdigest())
        self.assertEqual(PHONE_RESULT["execution"]["finalizer"]["sha256"], hashlib.sha256(finalizer.read_bytes()).hexdigest())

    def test_phone_runner_output_parser_fixtures(self):
        module_path = EXP / "tools/validate_phone_campaign.py"
        spec = importlib.util.spec_from_file_location("validate_phone_campaign", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clean = root / "clean.txt"
            clean.write_text('{"result":"passed"}\n')
            value, diagnostics = module.parse_runner_output(clean)
            self.assertEqual(value, {"result": "passed"})
            self.assertEqual(diagnostics["prefix_bytes"], 0)

            prefixed = root / "prefixed.txt"
            prefix = " # LIBNATIVE: diagnostic line\n"
            prefixed.write_text(prefix + '{"result":"passed"}\n')
            value, diagnostics = module.parse_runner_output(prefixed)
            self.assertEqual(value, {"result": "passed"})
            self.assertEqual(diagnostics["prefix_utf8"], prefix)
            self.assertEqual(
                diagnostics["stripped_prefix_sha256"],
                hashlib.sha256(prefix.strip().encode()).hexdigest(),
            )

            malformed = root / "malformed.txt"
            malformed.write_text('{"result":\n')
            with self.assertRaises(SystemExit):
                module.parse_runner_output(malformed)

            ambiguous = root / "ambiguous.txt"
            ambiguous.write_text('{"first":1}\n{"second":2}\n')
            with self.assertRaises(SystemExit):
                module.parse_runner_output(ambiguous)

    def test_exact_phone_stage_preflight_checks_hash_type_symlink_and_executable(self):
        checker = EXP / "tools/check_phone_stage_preflight.py"
        payload = b"deterministic-test-runner"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            runner = stage / "runner"
            runner.write_bytes(payload)
            runner.chmod(0o755)
            (stage / "stage-manifest.sha256").write_text(f"{digest}  runner\n")
            command = [
                "python3",
                str(checker),
                "--stage",
                str(stage),
                "--expected-runner-sha",
                digest,
            ]
            passed = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(passed.returncode, 0, passed.stderr)
            self.assertIn("runner_mode=0o755", passed.stdout)

            runner.chmod(0o644)
            not_executable = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(not_executable.returncode, 0)
            self.assertIn("not executable", not_executable.stderr)

            runner.unlink()
            target = stage / "runner-target"
            target.write_bytes(payload)
            target.chmod(0o755)
            os.symlink(target.name, runner)
            symlink = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(symlink.returncode, 0)
            self.assertIn("must not be a symlink", symlink.stderr)


if __name__ == "__main__":
    unittest.main()

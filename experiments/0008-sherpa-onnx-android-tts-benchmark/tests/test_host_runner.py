from __future__ import annotations

import fcntl
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from host_runner.runner import (  # noqa: E402
    CommandFailed,
    Completed,
    DeviceNotReady,
    DeviceRunner,
    LockConflict,
    PhoneLock,
    RunnerError,
    load_inventory,
    parse_battery_temperature,
    parse_devices,
    parse_thermal_status,
)


class FakeCommands:
    def __init__(self, *, devices="SER device product:dm3q model:SM-S918B\n", model="SM-S918B",
                 abi="arm64-v8a", boot="1", policy="mShowingLockscreen=false"):
        self.devices, self.model, self.abi, self.boot, self.policy = devices, model, abi, boot, policy
        self.calls: list[tuple[str, ...]] = []
        self.free_kib = 10_000_000
        self.hashes: dict[str, str] = {}
        self.test_results: list[int] = []
        self.pids: list[str] = []
        self.result_text = "{}"
        self.logcat = ""
        self.pulled: dict[str, bytes] = {}

    @staticmethod
    def _plain(argv):
        args = list(argv)
        if len(args) >= 3 and args[0] == "adb" and args[1] == "-s":
            args = ["adb", *args[3:]]
        return args

    def run(self, argv, *, timeout=None):
        del timeout
        self.calls.append(tuple(argv))
        args = self._plain(argv)
        if args == ["adb", "devices", "-l"]:
            return Completed(0, "List of devices attached\n" + self.devices)
        if args[-2:] == ["getprop", "ro.product.model"]:
            return Completed(0, self.model + "\n")
        if args[-2:] == ["getprop", "ro.product.cpu.abi"]:
            return Completed(0, self.abi + "\n")
        if args[-2:] == ["getprop", "sys.boot_completed"]:
            return Completed(0, self.boot + "\n")
        if args[-3:] == ["dumpsys", "window", "policy"]:
            return Completed(0, self.policy)
        if "df" in args:
            return Completed(0, f"Filesystem 1K-blocks Used Available Use% Mounted\n/data 1 0 {self.free_kib} 0% /data\n")
        if "sha256sum" in args:
            remote = args[-1]
            return Completed(0, self.hashes.get(remote, "0" * 64) + "  " + remote + "\n")
        if args[-2:] == ["dumpsys", "thermalservice"]:
            return Completed(0, "Thermal Status: 0\n")
        if args[-2:] == ["dumpsys", "battery"]:
            return Completed(0, " temperature: 320\n")
        if "test" in args and "-f" in args:
            return Completed(self.test_results.pop(0) if self.test_results else 1)
        if len(args) >= 4 and args[-3:-1] == ["shell", "pidof"]:
            return Completed(0, (self.pids.pop(0) if self.pids else "123") + "\n")
        if len(args) >= 3 and args[-2:] == ["logcat", "-d"]:
            return Completed(0, self.logcat)
        if "logcat" in args:
            return Completed(0, self.logcat)
        if len(args) >= 3 and args[-2:] and "cat" in args and "exec-out" in args:
            return Completed(0, self.result_text)
        if "pull" in args:
            remote, destination = args[-2:]
            payload = self.pulled.get(remote)
            if payload is None and len(self.pulled) == 1:
                payload = next(iter(self.pulled.values()))
            Path(destination).write_bytes(payload)
            return Completed(0)
        return Completed(0)

    def mutating(self):
        markers = {"install", "push", "mkdir", "mv", "rm", "force-stop", "start"}
        return [call for call in self.calls if markers.intersection(call)]


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class HostRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def runner(self, fake, clock=None):
        clock = clock or Clock()
        return DeviceRunner(fake, lock_path=self.dir / "artifacts/locks/phone.lock",
                            artifact_dir=self.dir / "runs", clock=clock, sleep=clock.sleep)

    def test_device_parser_keeps_non_device_states(self):
        rows = parse_devices("List of devices attached\na unauthorized model:x\nb offline model:y\n")
        self.assertEqual([(x.serial, x.state) for x in rows], [("a", "unauthorized"), ("b", "offline")])

    def test_absent_multiple_unauthorized_and_offline_are_read_only(self):
        cases = ("", "a device\nb device\n", "a unauthorized\n", "a offline\n")
        for listing in cases:
            with self.subTest(listing=listing):
                fake = FakeCommands(devices=listing)
                with self.assertRaises(DeviceNotReady):
                    with self.runner(fake).safe_session():
                        pass
                self.assertEqual(fake.mutating(), [])

    def test_samsung_keyguard_delegate_unlock_format_is_accepted(self):
        fake = FakeCommands(policy="KeyguardServiceDelegate\n  showing=false\n  secure=true")
        with self.runner(fake).safe_session() as device:
            self.assertEqual(device["model"], "SM-S918B")

    def test_wrong_model_locked_booting_and_wrong_abi_are_read_only(self):
        cases = ({"model": "SM-S911B"}, {"policy": "KeyguardServiceDelegate\n  showing=true\n  secure=true"},
                 {"boot": "0"}, {"abi": "x86_64"})
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                fake = FakeCommands(**kwargs)
                with self.assertRaises(DeviceNotReady):
                    with self.runner(fake).safe_session():
                        pass
                self.assertEqual(fake.mutating(), [])

    def test_lock_conflict_prevents_even_adb_read(self):
        path = self.dir / "artifacts/locks/phone.lock"
        path.parent.mkdir(parents=True)
        with path.open("a+") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fake = FakeCommands()
            with self.assertRaises(LockConflict):
                with self.runner(fake).safe_session():
                    pass
            self.assertEqual(fake.calls, [])

    def make_inventory(self):
        model = self.dir / "model"
        model.mkdir()
        payload = model / "a.bin"
        payload.write_bytes(b"verified")
        digest = hashlib.sha256(payload.read_bytes()).hexdigest()
        inventory = self.dir / "inventory.json"
        inventory.write_text(json.dumps({"files": [{"path": "a.bin", "size": 8, "sha256": digest}]}))
        apk = self.dir / "app.apk"
        apk.write_bytes(b"apk")
        return apk, model, inventory, digest

    def test_inventory_hash_failure_happens_before_adb(self):
        apk, model, inventory, _ = self.make_inventory()
        (model / "a.bin").write_bytes(b"changed")
        fake = FakeCommands()
        with self.assertRaises(RunnerError):
            self.runner(fake).stage(apk, hashlib.sha256(apk.read_bytes()).hexdigest(),
                                    "pocket", inventory, model)
        self.assertEqual(fake.calls, [])

    def test_shell_metacharacters_are_rejected_before_adb(self):
        apk, model, inventory, _ = self.make_inventory()
        digest = hashlib.sha256(apk.read_bytes()).hexdigest()
        for model_id in ("pocket;reboot", "-pocket", "pocket model", "pocket/$HOME"):
            with self.subTest(model_id=model_id):
                fake = FakeCommands()
                with self.assertRaises(RunnerError):
                    self.runner(fake).stage(apk, digest, model_id, inventory, model)
                self.assertEqual(fake.calls, [])

    def test_low_storage_is_read_only(self):
        apk, model, inventory, _ = self.make_inventory()
        fake = FakeCommands()
        fake.free_kib = 0
        with self.assertRaises(DeviceNotReady):
            self.runner(fake).stage(apk, hashlib.sha256(apk.read_bytes()).hexdigest(),
                                    "pocket", inventory, model)
        self.assertEqual(fake.mutating(), [])

    def test_inventory_accepts_canonical_bytes_field(self):
        apk, model, inventory, digest = self.make_inventory()
        inventory.write_text(json.dumps({"files": [{"path": "a.bin", "bytes": 8, "sha256": digest}]}))
        rows = load_inventory(inventory, model)
        self.assertEqual(rows[0].size, 8)

    def test_inventory_accepts_real_espeak_bang_directory(self):
        model = self.dir / "model"
        source = model / "voices/!v/Mr serious"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"voice")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        inventory = self.dir / "inventory.json"
        inventory.write_text(json.dumps({"files": [{"path": "voices/!v/Mr serious", "bytes": 5, "sha256": digest}]}))
        self.assertEqual(load_inventory(inventory, model)[0].relative_path, "voices/!v/Mr serious")

    def test_stage_installs_then_pushes_and_verifies(self):
        apk, model, inventory, digest = self.make_inventory()
        fake = FakeCommands()
        # Temporary name is random; answer every sha command with the expected value.
        original = fake.run
        def run(argv, **kwargs):
            if "sha256sum" in argv:
                fake.calls.append(tuple(argv))
                return Completed(0, digest + "  remote\n")
            return original(argv, **kwargs)
        fake.run = run
        result = self.runner(fake).stage(apk, hashlib.sha256(apk.read_bytes()).hexdigest(),
                                         "pocket", inventory, model)
        self.assertEqual(result["files"][0]["sha256"], digest)
        mutations = fake.mutating()
        self.assertTrue(any("install" in call for call in mutations))
        self.assertTrue(any("push" in call for call in mutations))
        self.assertTrue(any("mv" in call for call in mutations))

    def test_complete_deployment_stages_at_app_files_root(self):
        apk, model, inventory, digest = self.make_inventory()
        fake = FakeCommands()
        original = fake.run
        def run(argv, **kwargs):
            if "sha256sum" in argv:
                fake.calls.append(tuple(argv))
                return Completed(0, digest + "  remote\n")
            return original(argv, **kwargs)
        fake.run = run
        result = self.runner(fake).stage(apk, hashlib.sha256(apk.read_bytes()).hexdigest(),
                                         "complete", inventory, model, app_files_root=True)
        self.assertEqual(result["remote_root"], "app_external_files")
        pushes = [call for call in fake.calls if "push" in call]
        self.assertIn("/sdcard/Android/data/dev.moket.ttsbench/files/a.bin.incoming-", " ".join(pushes[0]))

    def test_thermal_parser_and_baseline_policy(self):
        self.assertEqual(parse_thermal_status("Thermal Status: NONE"), "NONE")
        self.assertEqual(parse_battery_temperature(" temperature: 349\n"), 34.9)
        fake = FakeCommands()
        clock = Clock()
        polls = self.runner(fake, clock).thermal_wait(baseline_c=33.0, maximum_wait_seconds=60, poll_seconds=60)
        self.assertTrue(polls[0].eligible)

    def test_hot_device_times_out_without_setting_changes(self):
        fake = FakeCommands()
        original = fake.run
        def hot(argv, **kwargs):
            args = FakeCommands._plain(argv)
            if args[-2:] == ["dumpsys", "battery"]:
                fake.calls.append(tuple(argv)); return Completed(0, " temperature: 360\n")
            return original(argv, **kwargs)
        fake.run = hot
        clock = Clock()
        with self.assertRaises(DeviceNotReady):
            self.runner(fake, clock).thermal_wait(baseline_c=None, maximum_wait_seconds=60, poll_seconds=60)
        self.assertFalse(any("settings" in call for call in fake.calls))

    def test_timeout_writes_failure_and_preserves_telemetry_and_log(self):
        fake = FakeCommands()
        fake.test_results = [1, 1, 1]
        fake.pids = ["123", "123", "123"]
        clock = Clock()
        path = self.runner(fake, clock).run_candidate("pocket", "models/pocket/descriptor.json", "0" * 64,
                                                       baseline_c=32.0, timeout_seconds=2, poll_seconds=1)
        failure = json.loads((path / "failure.json").read_text())
        self.assertEqual(failure["outcome"], "timeout")
        self.assertTrue((path / "telemetry.jsonl").exists())
        self.assertTrue((path / "logcat.txt").exists())

    def test_crash_and_oom_classification(self):
        for text, outcome in (("Fatal signal 11", "native_crash"), ("OutOfMemoryError", "oom")):
            with self.subTest(outcome=outcome):
                fake = FakeCommands()
                fake.test_results = [1, 1]
                fake.pids = ["44", ""]
                fake.logcat = text
                path = self.runner(fake).run_candidate("kokoro", "d.json", "0" * 64, baseline_c=32.0, timeout_seconds=10)
                self.assertEqual(json.loads((path / "failure.json").read_text())["outcome"], outcome)

    def test_malformed_and_partial_result_remain_visible(self):
        fake = FakeCommands()
        fake.test_results = [0]
        fake.result_text = "{not-json"
        path = self.runner(fake).run_candidate("pocket", "d.json", "0" * 64, baseline_c=32.0)
        self.assertTrue((path / "malformed-device-result.txt").exists())
        self.assertEqual(json.loads((path / "failure.json").read_text())["exit_state"], "result_written")

    def test_pull_is_hash_verified_and_collision_free(self):
        data = b"wav-data"
        digest = hashlib.sha256(data).hexdigest()
        fake = FakeCommands()
        fake.test_results = [0]
        fake.result_text = json.dumps({"artifacts": [{"path": "pocket/out.wav", "sha256": digest}]})
        remote = "/sdcard/Android/data/dev.moket.ttsbench/files/results/pocket/out.wav"
        fake.pulled[remote] = data
        runner = self.runner(fake)
        first = runner.run_candidate("pocket", "d.json", "0" * 64, baseline_c=32.0)
        fake.test_results = [0]
        second = runner.run_candidate("pocket", "d.json", "0" * 64, baseline_c=32.0)
        self.assertNotEqual(first, second)
        self.assertEqual((first / "device/pocket/out.wav").read_bytes(), data)
        self.assertTrue((first / "host-run.json").exists())

    def test_pull_hash_mismatch_keeps_partial_result(self):
        fake = FakeCommands()
        fake.test_results = [0]
        fake.result_text = json.dumps({"artifacts": [{"path": "out.wav", "sha256": "1" * 64}]})
        remote = "/sdcard/Android/data/dev.moket.ttsbench/files/results/out.wav"
        fake.pulled[remote] = b"wrong"
        path = self.runner(fake).run_candidate("supertonic_3", "d.json", "0" * 64, baseline_c=32.0)
        failure = json.loads((path / "failure.json").read_text())
        self.assertEqual(failure["exit_state"], "partial_result")
        self.assertTrue((path / "device-result.json").exists())

    def test_no_prohibited_device_operations_are_implemented(self):
        source = (BASE / "host_runner/runner.py").read_text().lower()
        forbidden = (" su ", "q" + "nn", "drop_" + "caches", "governor", "setprop", "pm grant")
        for term in forbidden:
            self.assertNotIn(term, source)


if __name__ == "__main__":
    unittest.main()

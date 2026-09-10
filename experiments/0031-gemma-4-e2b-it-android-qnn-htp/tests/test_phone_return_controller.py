"""All device traffic is FAKE. No real ADB, stage/model hash/load, or phone use."""
import fcntl
import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

EXP = Path(__file__).resolve().parents[1]
TRACK = EXP / 'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0, str(TRACK / 'tools'))
module = importlib.import_module('phone_return_controller')


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.fast = False
        self.controller = None
    def monotonic(self):
        return self.now
    def sleep(self, duration):
        self.now += 600 if self.fast and not self.controller.cleaning_up and duration == 1 else duration


class FakeAdb:
    def __init__(self):
        self.calls = []
        self.controller = None
        self.fail = {}
        self.mode = 'normal'
        self.dead = {role: True for role in module.ROLES}
        self.pids = {'model': 501, 'wrapper': 502, 'watchdog': 503}
        self.starts = {role: str(10000 + pid) for role, pid in self.pids.items()}
        self.bad_exe = self.bad_argv = self.reused_pid = self.missing_record = False
        self.extra_empty_argument = False
        self.exe_suffix = ''
        self.zombie_once = self.zombie_seen = False
        self.recheck_refusal = self.ignore_signals = False
        self.changed_record = False
        self.model_reads = 0

    def run(self, operation, argv, timeout, stdout_path, stderr_path):
        c = self.controller
        c._assert_adb_gate()
        assert argv[:3] == ['adb', '-s', module.SERIAL]
        assert c.lease.held and not os.get_inheritable(c.lease.fd)
        # A separate open-description cannot acquire the lease during ANY fake ADB action.
        fd = os.open(c.lease.path, os.O_RDWR)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise AssertionError('phone lock was not held')
        finally:
            os.close(fd)
        self.calls.append((operation, argv, timeout))
        if operation in self.fail:
            if operation == 'process.launch' and self.mode == 'launch_timeout':
                self.dead = {role: False for role in module.ROLES}
            if operation == 'raw.pull':
                partial = c.out / 'raw/device/evidence/short-output.txt'
                partial.parent.mkdir(parents=True)
                partial.write_bytes(b'partial FAKE pull retained')
            result = self.fail[operation]
            if isinstance(result, Exception):
                stdout_path.write_bytes(b'partial client output')
                stderr_path.write_bytes(b'interrupted client')
                raise result
        else:
            result = self.reply(operation)
        stdout_path.write_bytes(result.stdout)
        stderr_path.write_bytes(result.stderr)
        return result

    def reply(self, op):
        c = self.controller
        if op == 'identity.state': return module.Reply(0, b'device\n')
        if op == 'identity.serial': return module.Reply(0, (module.SERIAL + '\n').encode())
        if op.startswith('identity.'):
            return module.Reply(0, (module.PROPS[op.removeprefix('identity.')] + '\n').encode())
        if op == 'stage.storage':
            return module.Reply(0, b'Filesystem 1K-blocks Used Available Use% Mounted\n/dev/data 90000000 10000000 80000000 12% /data\n')
        if op == 'stage.manifest_hashes':
            text = f'{module.DIGEST}  frozen-manifest.json\n{module.sha(c.stage / "SHA256SUMS")}  SHA256SUMS\n'
            return module.Reply(0, text.encode())
        if op == 'stage.payload_hashes':
            return module.Reply(0, b'bin/genie-app: OK\nfirst-short.script: OK\nfrozen-manifest.json: OK\n')
        if op == 'stage.runner_mode': return module.Reply(0, b'555\n')
        if op == 'stage.control_hashes':
            text = ''.join(f'{module.sha(p)}  {p.name}\n' for p in sorted((c.out / 'control').iterdir()))
            return module.Reply(0, text.encode())
        if op == 'process.launch':
            self.dead = {role: False for role in module.ROLES}
            return module.Reply(0)
        if op == 'process.status':
            if self.mode == 'normal':
                self.dead = {role: True for role in module.ROLES}
                return module.Reply(0, b'EXIT 0\n')
            if self.mode == 'exit7':
                self.dead = {role: True for role in module.ROLES}
                return module.Reply(0, b'EXIT 7\n')
            if self.mode == 'remote_timeout': return module.Reply(0, b'TIMEOUT\n')
            return module.Reply(0, b'RUNNING\n')
        if op.startswith('pid.'):
            _, role, action = op.split('.')
            pid, born = self.pids[role], self.starts[role]
            if action == 'record':
                if role == 'model':
                    self.model_reads += 1
                    if self.missing_record: return module.Reply(0, b'MISSING\n')
                    if self.changed_record and self.model_reads > 1: born = '999999'
                return module.Reply(0, f'{pid}\n{born}\n'.encode())
            if role == 'model' and self.zombie_once and not self.zombie_seen:
                self.zombie_seen = True
                self.dead[role] = True
                fields = ['Z'] + ['0'] * 18 + [born] + ['0'] * 5
                return module.Reply(0, (f'{pid} (zombie) ' + ' '.join(fields) + '\n\nEXE\nCMD\n').encode())
            if self.dead[role]: return module.Reply(0, b'ABSENT\n')
            if role == 'model' and self.reused_pid: born = '999999'
            fields = ['R'] + ['0'] * 18 + [born] + ['0'] * 5
            raw_stat = f'{pid} (comm with spaces) ' + ' '.join(fields)
            if role == 'model':
                exe = c.remote + '/bin/genie-app'
                argv = [exe, '-s', 'first-short.script']
                if self.bad_exe: exe = '/system/bin/unrelated'
                exe += self.exe_suffix
                if self.bad_argv: argv = [c.remote + '/bin/genie-app', '-s', 'unapproved-long.script']
                if self.extra_empty_argument: argv.append('')
            else:
                exe = '/system/bin/mksh'
                argv = ['/system/bin/sh', c.remote + ('/launch.sh' if role == 'wrapper' else '/watchdog.sh')]
            return module.Reply(0, (raw_stat + '\n\nEXE\n' + exe + '\nCMD\n').encode() + b'\0'.join(x.encode() for x in argv) + b'\0')
        if op.startswith('signal.'):
            _, role, sig = op.split('.')
            if self.recheck_refusal: return module.Reply(64, b'REFUSED\n')
            if not self.ignore_signals: self.dead[role] = True
            return module.Reply(0, b'SIGNALLED\n')
        if op == 'raw.pull':
            dest = c.out / 'raw/device/evidence'
            dest.mkdir(parents=True)
            (dest / 'short-output.txt').write_bytes(b'partial or complete FAKE output')
            (dest / 'runner.stderr').write_bytes(b'FAKE native log')
            return module.Reply(0, b'fake files pulled\n')
        return module.Reply(0)


class ControllerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.stage = self.root / 'fake-stage'
        self.stage.mkdir()
        (self.stage / 'SHA256SUMS').write_text('fake-checksum-file\n')
        self.fake = FakeAdb()
        self.clock = FakeClock()
        self.controller = self.make_controller(self.fake, self.clock)

    def tearDown(self):
        self.temp.cleanup()

    def make_controller(self, fake, clock):
        controller = module.Controller(stage=self.stage, output_root=self.root / 'runs',
            slot_root=self.root / 'slots', lock_path=self.root / 'phone.lock', transport=fake,
            stage_verifier=lambda path, digest: {'files': {'bin/genie-app': {}, 'first-short.script': {}}}, clock=clock)
        fake.controller = clock.controller = controller
        return controller

    def execute(self, **kwargs):
        return self.controller.run(execute=True, reviewed_digest=module.DIGEST,
                                   pi_slot='pi-slot-01', run_id='short-01', **kwargs)

    def assert_free(self):
        self.assertFalse(self.controller.lease.held)
        with module.Lease(self.root / 'phone.lock'):
            pass

    def ops(self): return [x[0] for x in self.fake.calls]

    def test_default_plan_does_not_hash_stage_create_dirs_lock_or_call_adb(self):
        self.controller.stage_verifier = Mock(side_effect=AssertionError('not allowed in plan'))
        result = self.controller.run()
        self.assertEqual('plan_only', result['mode'])
        self.assertEqual([], self.fake.calls)
        self.assertFalse((self.root / 'runs').exists())
        self.assertFalse((self.root / 'phone.lock').exists())

    def test_missing_wrong_digest_slot_and_unsafe_run_id_fail_before_adb(self):
        for digest, slot, run in [(None, None, 'x'), ('0' * 64, 'pi-x', 'x'),
                                 (module.DIGEST, None, 'x'), (module.DIGEST, 'pi-x', '../x')]:
            with self.assertRaises(module.GuardError):
                self.controller.run(execute=True, reviewed_digest=digest, pi_slot=slot, run_id=run)
        self.assertEqual([], self.fake.calls)

    def test_low_level_call_outside_lease_is_forbidden(self):
        with self.assertRaises(module.GuardError):
            self.controller._adb('illegal', ['get-state'])
        self.assertFalse(self.fake.calls)

    def test_busy_lock_causes_zero_adb_and_no_slot_consumption(self):
        with module.Lease(self.root / 'phone.lock'):
            result = self.execute()
        self.assertEqual('phone_lock', result['error']['phase'])
        self.assertFalse(self.fake.calls)
        self.assertFalse((self.root / 'slots').exists())

    def test_host_manifest_failure_is_local_only(self):
        self.controller.stage_verifier = Mock(side_effect=RuntimeError('wrong manifest'))
        result = self.execute()
        self.assertEqual('host_stage_preflight', result['error']['phase'])
        self.assertFalse(self.fake.calls)
        self.assertFalse(result['launch_command_attempted'])

    def test_normal_collection_is_not_inference_claim_and_lease_covers_cleanup(self):
        result = self.execute()
        self.assertEqual('verified_absent', result['cleanup'])
        self.assertEqual(0, result['process_exit_code'])
        self.assertIsNone(result['runtime_success'])
        self.assertIsNone(result['provider_placement'])
        self.assertFalse(result['signal_guard_atomic'])
        self.assertEqual(1, self.ops().count('process.launch'))
        self.assertTrue(self.ops().index('raw.pull') < self.ops().index('cleanup.remove'))
        self.assertFalse(any(op.startswith('signal.') for op in self.ops()))
        self.assert_free()

    def test_same_output_and_controller_instance_are_not_reused(self):
        self.execute()
        with self.assertRaises(module.GuardError): self.execute()
        fake, clock = FakeAdb(), FakeClock()
        second = self.make_controller(fake, clock)
        with self.assertRaises(FileExistsError):
            second.run(execute=True, reviewed_digest=module.DIGEST, pi_slot='new-slot', run_id='short-01')
        self.assertEqual([], fake.calls)

    def test_slot_is_consumed_even_after_transport_failure_and_cannot_retry(self):
        self.fake.fail['identity.state'] = module.Reply(1, stderr=b'device not found')
        first = self.execute()
        self.assertFalse(first['launch_command_attempted'])
        fake, clock = FakeAdb(), FakeClock()
        second = self.make_controller(fake, clock)
        result = second.run(execute=True, reviewed_digest=module.DIGEST, pi_slot='pi-slot-01', run_id='short-02')
        self.assertEqual('slot_claim', result['error']['phase'])
        self.assertFalse(fake.calls)

    def test_wrong_device_build_stops_before_staging(self):
        self.fake.fail['identity.ro.build.fingerprint'] = module.Reply(0, b'other-build\n')
        result = self.execute()
        self.assertEqual('identity', result['error']['phase'])
        self.assertNotIn('stage.mkdir', self.ops())
        self.assertNotIn('process.launch', self.ops())

    def test_manifest_mode_and_full_hash_failures_never_launch(self):
        self.fake.fail['stage.payload_hashes'] = module.Reply(0, b'only-one: OK\n')
        result = self.execute()
        self.assertNotIn('process.launch', self.ops())
        self.assertTrue(result['raw_capture_attempted'])
        self.assertEqual('verified_absent', result['cleanup'])

    def test_runner_losing_execute_bits_is_not_silently_chmodded(self):
        self.fake.fail['stage.runner_mode'] = module.Reply(0, b'444\n')
        self.execute()
        self.assertNotIn('process.launch', self.ops())
        self.assertFalse(any('chmod' in ' '.join(argv) for _, argv, _ in self.fake.calls))

    def test_push_timeout_has_independent_raw_pull_and_cleanup_deadlines(self):
        self.fake.fail['stage.push'] = module.Reply(-15, stderr=b'push timed out', timed_out=True)
        result = self.execute()
        self.assertEqual('verified_absent', result['cleanup'])
        self.assertTrue(result['raw_pull_completed'])
        self.assertEqual(1, self.ops().count('stage.push'))
        self.assertEqual(180, next(t for op, _, t in self.fake.calls if op == 'raw.pull'))
        self.assertNotIn('process.launch', self.ops())
        self.assert_free()

    def test_native_error_retains_raw_before_optional_parser_failure(self):
        self.fake.mode = 'exit7'
        def bad_parser():
            self.assertTrue((self.controller.out / 'raw-capture-status.json').exists())
            self.assertTrue((self.controller.out / 'raw/device/evidence/short-output.txt').exists())
            raise ValueError('optional profile unavailable')
        self.controller.optional_metrics = bad_parser
        result = self.execute()
        self.assertEqual(7, result['process_exit_code'])
        self.assertTrue(result['raw_pull_completed'])
        self.assertIsNone(result['optional_metrics']['values'])
        self.assertEqual('verified_absent', result['cleanup'])

    def test_optional_parser_failure_does_not_erase_zero_exit_collection(self):
        def bad_parser():
            self.assertTrue((self.controller.out / 'raw-capture-status.json').exists())
            raise ValueError('optional profile missing')
        self.controller.optional_metrics = bad_parser
        result = self.execute()
        self.assertEqual(0, result['process_exit_code'])
        self.assertNotIn('error', result)
        self.assertEqual('verified_absent', result['cleanup'])
        self.assertIsNone(result['optional_metrics']['values'])
        self.assertIsNone(result['runtime_success'])

    def test_host_deadline_signals_only_fresh_verified_roles(self):
        self.fake.mode = 'hang'
        self.clock.fast = True
        result = self.execute()
        self.assertEqual('host_1800s_deadline', result['process_timeout'])
        self.assertTrue(result['native_process_observed'])
        signals = [(op, argv) for op, argv, _ in self.fake.calls if op.startswith('signal.')]
        self.assertTrue(signals)
        for op, argv in signals:
            shell = argv[-1]
            self.assertIn('/proc/$pid/cmdline', shell)
            self.assertIn('expected_start', shell)
            self.assertIn('role_matches "$role" "$pid" "$start" ||', shell)
            self.assertNotIn('pkill', shell)
        self.assertEqual('verified_absent', result['cleanup'])
        self.assertEqual(1, self.ops().count('process.launch'))
        self.assert_free()

    def test_pid_reuse_wrong_exe_wrong_cmdline_and_changed_records_refuse_kill(self):
        self.fake.mode = 'hang'
        self.fake.reused_pid = True
        result = self.execute()
        self.assertIn('PID reuse', result['error']['message'])
        self.assertFalse(any(op.startswith('signal.') for op in self.ops()))
        self.assertNotIn('cleanup.remove', self.ops())
        self.assertTrue(result['raw_capture_attempted'])
        self.assert_free()

    def test_wrong_executable_refuses_kill(self):
        self.fake.mode = 'hang'; self.fake.bad_exe = True
        self.execute()
        self.assertFalse(any(op.startswith('signal.') for op in self.ops()))
        self.assertNotIn('cleanup.remove', self.ops())

    def test_newline_suffix_in_executable_is_not_trimmed_into_valid_identity(self):
        self.fake.mode = 'hang'; self.fake.exe_suffix = '\n'
        self.execute()
        self.assertFalse(any(op.startswith('signal.') for op in self.ops()))
        self.assertNotIn('cleanup.remove', self.ops())

    def test_wrong_cmdline_refuses_kill(self):
        self.fake.mode = 'hang'; self.fake.bad_argv = True
        self.execute()
        self.assertFalse(any(op.startswith('signal.') for op in self.ops()))
        self.assertNotIn('cleanup.remove', self.ops())

    def test_extra_empty_argv_is_not_trimmed_into_a_valid_identity(self):
        self.fake.mode = 'hang'; self.fake.extra_empty_argument = True
        self.execute()
        self.assertFalse(any(op.startswith('signal.') for op in self.ops()))
        self.assertNotIn('cleanup.remove', self.ops())
        self.assertIn('expected_fields', module.common('/data/local/tmp/test'))

    def test_record_change_is_not_a_new_attempt(self):
        self.fake.mode = 'hang'; self.fake.changed_record = True
        result = self.execute()
        self.assertIn('record changed', result['error']['message'])
        self.assertEqual(1, self.ops().count('process.launch'))
        self.assertNotIn('cleanup.remove', self.ops())

    def test_signal_identity_recheck_refusal_blocks_cleanup(self):
        self.fake.mode = 'remote_timeout'; self.fake.recheck_refusal = True
        result = self.execute()
        self.assertEqual('remote_1800s_watchdog', result['process_timeout'])
        self.assertFalse(result['process_cleanup']['all_absent'])
        self.assertNotIn('cleanup.remove', self.ops())
        self.assertTrue(result['raw_pull_completed'])

    def test_unreadable_proc_identity_refuses_signal_and_destructive_cleanup(self):
        self.fake.mode = 'hang'
        self.fake.fail['pid.model.probe'] = module.Reply(1, stderr=b'permission denied')
        result = self.execute()
        self.assertFalse(any(op.startswith('signal.') for op in self.ops()))
        self.assertNotIn('cleanup.remove', self.ops())
        self.assertEqual(self.controller.remote, result['retained_remote_root'])
        self.assertTrue(result['raw_capture_attempted'])

    def test_missing_pid_record_never_means_absence(self):
        self.fake.mode = 'remote_timeout'; self.fake.missing_record = True
        result = self.execute()
        self.assertFalse(result['process_cleanup']['all_absent'])
        self.assertNotIn('cleanup.remove', self.ops())
        self.assertFalse(any(op.startswith('signal.') for op in self.ops()))

    def test_raw_pull_timeout_is_retained_and_not_retried(self):
        self.fake.fail['raw.pull'] = module.Reply(-15, timed_out=True)
        result = self.execute()
        self.assertFalse(result['raw_pull_completed'])
        self.assertTrue(result['raw_capture_attempted'])
        self.assertEqual(1, self.ops().count('raw.pull'))
        self.assertEqual('processes_absent_raw_incomplete_remote_root_retained', result['cleanup'])
        self.assertNotIn('cleanup.remove', self.ops())
        self.assertEqual(b'partial FAKE pull retained',
                         (self.controller.out / 'raw/device/evidence/short-output.txt').read_bytes())

    def test_remote_manifest_mismatch_never_launches(self):
        self.fake.fail['stage.manifest_hashes'] = module.Reply(0, ('0' * 64 + '  frozen-manifest.json\n').encode())
        self.execute()
        self.assertNotIn('process.launch', self.ops())
        self.assertNotIn('stage.payload_hashes', self.ops())

    def test_controller_script_mismatch_never_launches(self):
        self.fake.fail['stage.control_hashes'] = module.Reply(0, ('0' * 64 + '  control.sh\n').encode())
        self.execute()
        self.assertNotIn('process.launch', self.ops())

    def test_unconfirmed_mkdir_never_deletes_a_possible_preexisting_root(self):
        self.fake.fail['stage.mkdir'] = module.Reply(-15, timed_out=True)
        result = self.execute()
        self.assertEqual('unknown_creation', result['cleanup'])
        self.assertNotIn('cleanup.remove', self.ops())
        self.assertNotIn('process.launch', self.ops())

    def test_launch_transport_timeout_handles_possible_live_owned_process(self):
        self.fake.mode = 'launch_timeout'
        self.fake.fail['process.launch'] = module.Reply(-15, timed_out=True)
        result = self.execute()
        self.assertTrue(result['launch_command_attempted'])
        self.assertTrue(result['process_cleanup']['all_absent'])
        self.assertTrue(result['raw_pull_completed'])
        self.assertEqual(1, self.ops().count('process.launch'))
        self.assertTrue(any(op.startswith('signal.') for op in self.ops()))

    def test_unresponsive_process_is_not_reported_absent_or_deleted(self):
        self.fake.mode = 'remote_timeout'; self.fake.ignore_signals = True
        result = self.execute()
        self.assertFalse(result['process_cleanup']['all_absent'])
        self.assertIn('signal.model.TERM', self.ops())
        self.assertIn('signal.model.KILL', self.ops())
        self.assertNotIn('cleanup.remove', self.ops())
        self.assertTrue(result['raw_capture_attempted'])

    def test_exit_during_probe_is_recognized_without_signal(self):
        self.fake.fail['pid.model.probe'] = module.Reply(0, b'partial snapshot\nABSENT_AFTER_PROBE\n')
        result = self.execute()
        self.assertEqual('verified_absent', result['cleanup'])
        self.assertFalse(any(op.startswith('signal.') for op in self.ops()))

    def test_zombie_is_waited_for_not_signalled_or_claimed_absent_early(self):
        self.fake.zombie_once = True
        result = self.execute()
        self.assertTrue(self.fake.zombie_seen)
        self.assertEqual('verified_absent', result['cleanup'])
        self.assertFalse(any(op.startswith('signal.model') for op in self.ops()))

    def test_pid_one_or_malformed_record_is_never_signalled(self):
        self.fake.mode = 'remote_timeout'
        self.fake.fail['pid.model.record'] = module.Reply(0, b'1\n123\n')
        self.execute()
        self.assertFalse(any(op.startswith('signal.') for op in self.ops()))
        self.assertNotIn('cleanup.remove', self.ops())

    def test_cleanup_error_stays_unknown_no_retry(self):
        self.fake.fail['cleanup.absence'] = module.Reply(-15, timed_out=True)
        result = self.execute()
        self.assertEqual('unknown_transport_or_cleanup_error', result['cleanup'])
        self.assertEqual(1, self.ops().count('cleanup.absence'))
        self.assert_free()

    def test_interruption_in_adb_path_retains_and_cleans(self):
        self.fake.fail['process.status'] = InterruptedError('simulated SIGTERM')
        result = self.execute()
        self.assertEqual('InterruptedError', result['error']['type'])
        self.assertTrue(result['raw_capture_attempted'])
        self.assertEqual('verified_absent', result['cleanup'])
        self.assert_free()

    def test_real_transport_spawn_flags_close_lock_fd_and_reap_client_timeout(self):
        proc = Mock(pid=424242)
        proc.wait.side_effect = [subprocess.TimeoutExpired('fake-client', 1), -15]
        with patch.object(module.subprocess, 'Popen', return_value=proc) as popen, patch.object(module.os, 'killpg') as kill:
            reply = module.AdbTransport(lambda: None).run('fake-only', ['NOT-ADB'], 1, self.root / 'o', self.root / 'e')
        self.assertTrue(reply.timed_out)
        self.assertTrue(popen.call_args.kwargs['close_fds'])
        self.assertTrue(popen.call_args.kwargs['start_new_session'])
        self.assertNotIn('pass_fds', popen.call_args.kwargs)
        kill.assert_called_once_with(424242, signal.SIGTERM)

    def test_client_timeout_escalation_is_scoped_and_reaped(self):
        proc = Mock(pid=424243)
        proc.wait.side_effect = [subprocess.TimeoutExpired('fake', 1), subprocess.TimeoutExpired('fake', 2), -9]
        with patch.object(module.subprocess, 'Popen', return_value=proc), patch.object(module.os, 'killpg') as kill:
            reply = module.AdbTransport(lambda: None).run('fake-only', ['NOT-ADB'], 1, self.root / 'o', self.root / 'e')
        self.assertTrue(reply.timed_out)
        self.assertEqual([(424243, signal.SIGTERM), (424243, signal.SIGKILL)],
                         [call.args for call in kill.call_args_list])
        self.assertEqual(3, proc.wait.call_count)

    def test_transport_interruption_reaps_its_client_before_propagating(self):
        proc = Mock(pid=424244)
        proc.wait.side_effect = [InterruptedError('fake interrupt'), -15]
        with patch.object(module.subprocess, 'Popen', return_value=proc), patch.object(module.os, 'killpg') as kill:
            with self.assertRaises(InterruptedError):
                module.AdbTransport(lambda: None).run('fake-only', ['NOT-ADB'], 1, self.root / 'o', self.root / 'e')
        kill.assert_called_once_with(424244, signal.SIGTERM)
        self.assertEqual(2, proc.wait.call_count)

    def test_transport_without_authorization_guard_cannot_spawn(self):
        with patch.object(module.subprocess, 'Popen') as popen:
            with self.assertRaises(module.GuardError):
                module.AdbTransport().run('forbidden', ['adb'], 1, self.root / 'o', self.root / 'e')
            popen.assert_not_called()

    def test_generated_shell_is_syntax_only_checked_and_has_independent_watchdog(self):
        for name, text in module.scripts('/data/local/tmp/vibevoice-0031-fp16-test-only').items():
            path = self.root / name
            path.write_text(text)
            # Host parser only; never executes generated commands.
            subprocess.run(['bash', '-n', str(path)], check=True, capture_output=True)
        watch = (self.root / 'watchdog.sh').read_text()
        self.assertIn('start + 1800', watch)
        self.assertIn('/proc/uptime', watch)
        self.assertIn('signal_owned model', watch)
        entry = (self.root / 'model-entry.sh').read_text()
        self.assertLess(entry.index('record_self model'), entry.index('exec "$REMOTE/bin/genie-app"'))
        self.assertNotIn('long', entry)


if __name__ == '__main__':
    unittest.main()

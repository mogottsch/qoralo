"""Host-only scope tests, fake ADB, and one owned non-model FIFO dummy child."""
import errno
import hashlib
import importlib
import json
import os
from pathlib import Path
import select
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

EXP = Path(__file__).resolve().parents[1]
TRACK = EXP / 'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0, str(TRACK / 'tools'))
adapter = importlib.import_module('phone_return_long')
preparer = importlib.import_module('prepare_long_genie_stage')
short = importlib.import_module('phone_return_controller')
base_tests = importlib.import_module('test_phone_return_controller')


class LongFake(base_tests.FakeAdb):
    def reply(self, op):
        reply = super().reply(op)
        reply.stdout = reply.stdout.replace(b'first-short.script', b'exact-long.script')
        return reply


class LongScopeTest(unittest.TestCase):
    def test_materialization_is_exactly_the_enumerated_changes(self):
        controller, shell, changes = adapter.materialize_sources()
        restored = controller
        for change in reversed(changes):
            restored = adapter.replace_exact(restored, change['new'], change['old'], change['count'])
        self.assertEqual((TRACK / 'tools/phone_return_controller.py').read_text(), restored)
        self.assertEqual((TRACK / 'tools/phone_return_shell.py').read_text(),
                         shell.replace('exact-long.script', 'first-short.script'))
        self.assertNotIn('first-short.script', controller)
        self.assertNotIn('first-short.script', shell)

    def test_template_hash_mismatch_fails_before_materialization(self):
        with patch.object(adapter, 'BASE_CONTROLLER_SHA', '0' * 64):
            with self.assertRaisesRegex(RuntimeError, 'reviewed short lifecycle source changed'):
                adapter.materialize_sources()

    def test_long_plan_is_fixed_and_does_not_mutate_short_module(self):
        lifecycle, receipt = adapter.load_lifecycle()
        plan = lifecycle.Controller().run()
        self.assertEqual('plan_only', plan['mode'])
        self.assertEqual(adapter.LONG_DIGEST, plan['reviewed_stage_digest'])
        self.assertIn('exact-long', plan['scope'])
        self.assertTrue(plan['long_script'])
        self.assertEqual(1800, plan['process_deadline_seconds'])
        self.assertFalse(plan['signal_guard_atomic'])
        self.assertEqual(adapter.SHORT_DIGEST, short.DIGEST)
        self.assertFalse(short.plan()['long_script'])
        self.assertIn('first-short.script', short.scripts('/data/local/tmp/short')['model-entry.sh'])
        self.assertIn('exact-long.script', lifecycle.scripts('/data/local/tmp/long')['model-entry.sh'])
        self.assertEqual('81f4ede', receipt['gate_a_commit'])

    def test_long_reuses_lock_pid_deadline_retention_gates_with_fake_transport(self):
        lifecycle, _ = adapter.load_lifecycle()
        with tempfile.TemporaryDirectory() as directory, patch.object(base_tests, 'module', lifecycle):
            root = Path(directory); stage = root / 'fake-stage'; stage.mkdir()
            (stage / 'SHA256SUMS').write_text('fake\n')
            fake = LongFake(); fake.mode = 'hang'
            clock = base_tests.FakeClock(); clock.fast = True
            c = lifecycle.Controller(stage=stage, output_root=root/'runs', slot_root=root/'slots',
                lock_path=root/'phone.lock', transport=fake, clock=clock,
                stage_verifier=lambda *args: {'files': {'bin/genie-app': {}, 'exact-long.script': {}}})
            fake.controller = clock.controller = c
            result = c.run(execute=True, reviewed_digest=adapter.LONG_DIGEST, pi_slot='mock-long-slot', run_id='mock-long')
            self.assertEqual('host_1800s_deadline', result['process_timeout'])
            self.assertEqual('verified_absent', result['cleanup'])
            self.assertTrue(result['raw_pull_completed'])
            self.assertTrue(result['scope_adapter']['long_stage_digest'] == adapter.LONG_DIGEST)
            self.assertIsNone(result['runtime_success'])
            launch = next(argv[-1] for op, argv, _ in fake.calls if op == 'process.launch')
            self.assertNotIn('&&', launch)
            self.assertNotIn('cd ', launch)
            self.assertIn(c.remote + '/evidence/launcher.stdout', launch)
            self.assertEqual(1, sum(op == 'process.launch' for op, _, _ in fake.calls))
            signals = [argv[-1] for op, argv, _ in fake.calls if op.startswith('signal.')]
            self.assertTrue(signals)
            self.assertTrue(all('exact-long.script' in source and 'first-short.script' not in source for source in signals))

    def test_short_digest_cannot_authorize_long(self):
        lifecycle, _ = adapter.load_lifecycle()
        with self.assertRaises(lifecycle.GuardError):
            lifecycle.Controller().run(execute=True, reviewed_digest=adapter.SHORT_DIGEST,
                                       pi_slot='not-an-actual-slot', run_id='never-created')

    def test_long_script_is_one_fresh_exact_request_with_full_ceiling(self):
        lines = preparer.SCRIPT.splitlines()
        self.assertIn('dialog setMaxNumTokens dialog1 2048', lines)
        self.assertEqual(['dialog query dialog1 prompts/long.txt evidence/long-output.txt'],
                         [line for line in lines if line.startswith('dialog query ')])
        self.assertEqual(1, sum(line.startswith('dialog create ') for line in lines))
        self.assertNotIn('prompts/short.txt', preparer.SCRIPT)
        self.assertNotIn('rewind', preparer.SCRIPT)
        self.assertNotIn('export', preparer.SCRIPT)

    def test_direct_launch_pipe_closes_before_owned_dummy_finishes_and_dummy_is_reaped(self):
        # The transport shell explicitly closes its own pipes then waits/reaps its
        # child. Thus EOF before FIFO release proves the launched child does not
        # retain the transport pipe. No ADB or model is involved; no speed metric.
        with tempfile.TemporaryDirectory() as directory:
            remote = Path(directory) / 'owned dummy'
            (remote / 'evidence').mkdir(parents=True)
            fifo = remote / 'gate.fifo'; os.mkfifo(fifo, 0o600)
            script = remote / 'launch.sh'
            script.write_text('#!/bin/sh\nset -eu\ncd ' + shlex.quote(str(remote)) + '\n'
                              'printf "%s\\n" "$$" > evidence/dummy.pid\n'
                              'printf ready > evidence/ready\n'
                              'IFS= read -r value < gate.fifo\n'
                              'printf finished > evidence/finished\n')
            shell = shutil.which('sh')
            command = adapter.detached_launch_command(str(remote), shell=shell)
            command += '\nchild=$!\nexec >/dev/null 2>&1\nwait "$child"\n'
            proc = subprocess.Popen([shell, '-c', command], stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, start_new_session=True)
            try:
                ready, _, _ = select.select([proc.stdout], [], [], 5)
                self.assertTrue(ready, 'launch child retained the transport pipe')
                self.assertEqual(b'', proc.stdout.read(1))
                self.assertIsNone(proc.poll(), 'transport should still be waiting for its owned child')
                limit = time.monotonic() + 5
                while not (remote / 'evidence/ready').exists() and time.monotonic() < limit:
                    time.sleep(0.01)
                self.assertTrue((remote / 'evidence/ready').exists())
                self.assertFalse((remote / 'evidence/finished').exists())
                while True:
                    try:
                        fd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
                        break
                    except OSError as error:
                        if error.errno != errno.ENXIO or time.monotonic() >= limit:
                            raise
                        time.sleep(0.01)
                try: os.write(fd, b'finish\n')
                finally: os.close(fd)
                self.assertEqual(0, proc.wait(timeout=5))
                self.assertTrue((remote / 'evidence/finished').exists())
                # wait "$child" reaped the dummy before this shell exited;
                # proc.wait above reaped that transport shell.
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try: proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL); proc.wait(timeout=3)
                proc.stdout.close(); proc.stderr.close()


if __name__ == '__main__':
    unittest.main()

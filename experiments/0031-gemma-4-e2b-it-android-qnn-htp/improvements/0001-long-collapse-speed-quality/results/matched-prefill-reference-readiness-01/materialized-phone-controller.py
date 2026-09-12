#!/usr/bin/env python3
"""Plan-only by default. Real ADB needs reviewed bytes, one Pi slot and full lock.

This controller collects a single paired-prefill exact1929/max1 capture process, NOT a campaign.
No profile metrics or inference-success claims are inferred from exit code alone.
Tests inject a fake transport/stage verifier; the CLI exposes no fake/bypass mode.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time

from phone_return_shell import common, scripts
from prepare_frozen_genie_stage import verify as verify_stage

TRACK = Path(__file__).resolve().parents[1]
REPO = TRACK.parents[3]
STAGE = TRACK / '.local/frozen-stages/paired-prefill-capture-stage-01'
DIGEST = 'b99056c1faa1e25823fd9bcda2a0968a0445cb93458dc1069e7d269eb9c54953'
SERIAL = 'R5CW81PR8SY'
FINGERPRINT = 'samsung/dm3qxeea/dm3q:16/BP4A.251205.006/S918BXXSAFZG1:user/release-keys'
PROPS = {
    'ro.product.manufacturer': 'samsung', 'ro.product.model': 'SM-S918B',
    'ro.product.device': 'dm3q', 'ro.soc.model': 'SM8550',
    'ro.product.cpu.abi': 'arm64-v8a', 'ro.build.version.release': '16',
    'ro.build.version.sdk': '36', 'ro.build.fingerprint': FINGERPRINT,
    'sys.boot_completed': '1', 'ro.boot.verifiedbootstate': 'green', 'ro.boot.flash.locked': '1',
}
SAFE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z')
ROLES = ('model', 'wrapper', 'watchdog')


class GuardError(RuntimeError):
    pass


class AdbError(RuntimeError):
    pass


class UnsafePID(RuntimeError):
    pass


@dataclass
class Reply:
    code: int | None
    stdout: bytes = b''
    stderr: bytes = b''
    timed_out: bool = False


class Clock:
    monotonic = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)


class Lease:
    def __init__(self, path):
        self.path, self.fd, self.held = Path(path), None, False

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
        os.set_inheritable(self.fd, False)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise
        self.held = True
        return self

    def __exit__(self, *exc):
        self.held = False
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None


class AdbTransport:
    def __init__(self, authorize=None):
        self.authorize = authorize

    def run(self, operation, argv, timeout, stdout_path, stderr_path):
        if self.authorize is None:
            raise GuardError('ADB transport requires the controller lease/authorization guard')
        self.authorize()
        with stdout_path.open('xb') as out, stderr_path.open('xb') as err:
            # The server cannot inherit the lease: fd is CLOEXEC AND all extra
            # descriptors are closed before the adb client executes/spawns it.
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                    close_fds=True, start_new_session=True)
            timed_out = False
            try:
                stdout_path.with_suffix('.host-pid.json').write_text(json.dumps({
                    'host_client_pid': proc.pid, 'host_process_group': proc.pid,
                    'close_fds': True, 'start_new_session': True,
                    'boundary': 'spawn identity only; not a later liveness/reaping assertion'}, indent=2) + '\n')
                code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                code = self._terminate(proc)
            except BaseException:
                self._terminate(proc)
                raise
        return Reply(code, stdout_path.read_bytes(), stderr_path.read_bytes(), timed_out)

    @staticmethod
    def _terminate(proc):
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            return proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            return proc.wait(timeout=3)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def stat_fields(data):
    end = data.rfind(b') ')
    if end < 0:
        raise UnsafePID('malformed /proc stat')
    fields = data[end + 2:].split()
    if len(fields) <= 19 or not fields[19].isdigit():
        raise UnsafePID('missing process starttime')
    return fields[0].decode('ascii'), fields[19].decode('ascii')


def plan():
    return {'mode': 'plan_only', 'adb_calls': 0, 'runtime_loaded': False,
            'stage': str(STAGE), 'reviewed_stage_digest': DIGEST,
            'requires': ['--execute', '--reviewed-stage-digest', '--pi-slot', '--run-id',
                         'full phone.lock before every ADB action', 'fresh one-use slot record'],
            'device_serial': SERIAL, 'reviewed_fingerprint': FINGERPRINT,
            'scope': 'same precision-path candidate: one fresh-dialog exact1929/max1 input/logit capture only',
            'process_deadline_seconds': 300, 'remote_watchdog': True,
            'long_script': True, 'auto_retry': False,
            'raw_before_optional_metrics': True, 'phone_permission_granted_by_plan': False,
            'signal_guard_atomic': False,
            'signal_race_boundary': 'Sequential /proc identity checks then numeric-PID kill; no pidfd/kernel identity binding.'}


class Controller:
    def __init__(self, *, stage=STAGE, output_root=None, slot_root=None, lock_path=None,
                 transport=None, stage_verifier=verify_stage, clock=None, adb='adb'):
        self.stage = Path(stage)
        self.output_root = Path(output_root or TRACK / '.local/paired-prefill-phone-runs')
        self.slot_root = Path(slot_root or TRACK / '.local/phone-return-slots')
        self.lease = Lease(lock_path or REPO / 'artifacts/locks/phone.lock')
        self.transport = transport or AdbTransport(self._assert_adb_gate)
        self.stage_verifier, self.clock, self.adb = stage_verifier, clock or Clock(), adb
        self.authorized = self.stage_verified = self.slot_claimed = False
        self.remote_created = self.creation_attempted = self.launch_attempted = False
        self.records = {}
        self.events = []
        self.sequence = 0
        self.deadline = None
        self.result = {}
        self.out = None
        self.cleaning_up = False
        self.interrupt_seen = False

    def _assert_adb_gate(self):
        if not (self.authorized and self.stage_verified and self.slot_claimed and self.lease.held):
            raise GuardError('ADB forbidden without reviewed stage, Pi slot and held phone.lock')
        if self.lease.fd is None or os.get_inheritable(self.lease.fd):
            raise GuardError('phone lock descriptor must not be inheritable')

    def _adb(self, op, args, timeout=15, *, allow_error=False, deadline=None):
        self._assert_adb_gate()
        if deadline is not None:
            timeout = min(timeout, deadline - self.clock.monotonic())
        if timeout <= 0:
            raise AdbError(f'{op}: phase deadline expired')
        self.sequence += 1
        tag = f'{self.sequence:04d}-' + re.sub(r'[^A-Za-z0-9._-]', '_', op)
        root = self.out / 'raw/commands'
        argv = [self.adb, '-s', SERIAL, *map(str, args)]
        event = {'operation': op, 'argv': argv, 'timeout_seconds': timeout,
                 'lock_held': True, 'lock_fd_inheritable': False,
                 'stdout': f'raw/commands/{tag}.stdout', 'stderr': f'raw/commands/{tag}.stderr'}
        (root / f'{tag}.json').write_text(json.dumps(event, indent=2) + '\n')
        self.events.append(event)
        try:
            reply = self.transport.run(op, argv, timeout, root / f'{tag}.stdout', root / f'{tag}.stderr')
        except BaseException as error:
            event.update(code=None, exception_type=type(error).__name__, exception_message=str(error))
            (root / f'{tag}.json').write_text(json.dumps(event, indent=2) + '\n')
            raise
        event.update(code=reply.code, timed_out=reply.timed_out)
        (root / f'{tag}.json').write_text(json.dumps(event, indent=2) + '\n')
        if reply.timed_out or (reply.code != 0 and not allow_error):
            raise AdbError(f'{op}: ' + ('timeout' if reply.timed_out else f'exit{reply.code}'))
        return reply

    def _shell(self, op, command, timeout=15, **kwargs):
        return self._adb(op, ['shell', command], timeout, **kwargs)

    def _identity(self):
        state = self._adb('identity.state', ['get-state']).stdout.strip()
        serial = self._adb('identity.serial', ['get-serialno']).stdout.strip()
        if state != b'device' or serial != SERIAL.encode():
            raise GuardError('device transport/serial mismatch')
        identity = {'serial': serial.decode()}
        self.result['identity'] = identity
        for name, expected in PROPS.items():
            value = self._shell('identity.' + name, 'getprop ' + name).stdout.decode().strip()
            identity[name] = value
            if value != expected:
                raise GuardError(f'reviewed device/build property mismatch: {name}')
        self.result['identity_verified'] = True

    def _telemetry(self, label):
        for service in ('battery', 'thermalservice'):
            try:
                self._shell(f'telemetry.{label}.{service}', f'dumpsys {service}', 10)
            except Exception as error:
                self.result.setdefault('optional_errors', []).append(str(error))

    @staticmethod
    def _hash_lines(data):
        hashes = {}
        for line in data.decode().replace('\r', '').splitlines():
            match = re.fullmatch(r'([0-9a-f]{64})\s+\*?(.+)', line)
            if not match or match[2] in hashes:
                raise GuardError('malformed/duplicate remote hash observation')
            hashes[match[2]] = match[1]
        return hashes

    def _stage(self, manifest):
        space = self._shell('stage.storage', 'df -k /data/local/tmp').stdout.decode().splitlines()
        try:
            available = int(space[-1].split()[3])
        except (ValueError, IndexError):
            raise GuardError('remote free-space observation unavailable')
        if available < 6 * 1024**2:
            raise GuardError('less than6GiB remote free space')
        self.creation_attempted = True
        self._shell('stage.mkdir', f'mkdir -m 700 {shlex.quote(self.remote)}')
        self.remote_created = True
        self._shell('stage.evidence_dir', f'mkdir -m 700 {shlex.quote(self.remote + "/evidence")}')
        self._adb('stage.push', ['push', str(self.stage) + '/.', self.remote + '/'], 600)
        prefix = f'cd {shlex.quote(self.remote)} && '
        hashes = self._hash_lines(self._shell('stage.manifest_hashes', prefix +
                                  'sha256sum frozen-manifest.json SHA256SUMS', 30).stdout)
        if hashes != {'frozen-manifest.json': DIGEST, 'SHA256SUMS': sha(self.stage / 'SHA256SUMS')}:
            raise GuardError('remote manifest/checksum identity mismatch')
        checked = self._shell('stage.payload_hashes', prefix + 'sha256sum -c SHA256SUMS', 180).stdout
        lines = checked.decode().replace('\r', '').splitlines()
        expected = {name + ': OK' for name in manifest['files']} | {'frozen-manifest.json: OK'}
        if len(lines) != len(expected) or set(lines) != expected:
            raise GuardError('remote full payload hash check mismatch')
        mode = self._shell('stage.runner_mode', prefix + "stat -c '%a' bin/genie-app").stdout.strip()
        if mode != b'555':
            raise GuardError('remote runner is not0555')
        self._shell('stage.shell_tools', 'for t in nohup sleep readlink tr awk wc; do command -v "$t" || exit 1; done')
        control = self.out / 'control'
        control.mkdir()
        control_hashes = {}
        for name, text in scripts(self.remote).items():
            path = control / name
            path.write_text(text)
            path.chmod(0o400)
            control_hashes[name] = sha(path)
        self._adb('stage.control_push', ['push', str(control) + '/.', self.remote + '/'], 60)
        remote = self._hash_lines(self._shell('stage.control_hashes', prefix +
                                 'sha256sum ' + ' '.join(sorted(control_hashes)), 20).stdout)
        if remote != control_hashes:
            raise GuardError('remote controller script hash mismatch')
        self.result['input_hashes_verified'] = True
        self.result['controller_script_hashes'] = control_hashes

    def _record(self, role, deadline):
        root = shlex.quote(self.remote + '/evidence/' + role)
        command = f'if [ -s {root}.pid ] && [ -s {root}.start ]; then cat {root}.pid {root}.start; else printf "MISSING\\n"; fi'
        data = self._shell(f'pid.{role}.record', command, 10, deadline=deadline).stdout.strip()
        if data == b'MISSING':
            return None
        fields = data.split()
        if len(fields) != 2 or not all(x.isdigit() for x in fields) or int(fields[0]) <= 1:
            raise UnsafePID(f'{role}: malformed PID/starttime record')
        record = (int(fields[0]), fields[1].decode())
        if role in self.records and self.records[role] != record:
            raise UnsafePID(f'{role}: PID/starttime record changed; no replacement/retry allowed')
        self.records[role] = record
        return record

    def _probe(self, role, deadline):
        record = self._record(role, deadline)
        if record is None:
            return 'missing', None
        pid, born = record
        base = f'/proc/{pid}'
        command = (f'if [ ! -d {base} ]; then printf "ABSENT\\n"; else '
                   f'rc=0; st=$(cat {base}/stat) || rc=1; tail=${{st##*) }}; state=${{tail%% *}}; '
                   'printf "%s\\n\\nEXE\\n" "$st"; '
                   f'if [ "$state" = Z ]; then printf "CMD\\n"; else '
                   f'readlink {base}/exe || rc=1; printf "CMD\\n"; cat {base}/cmdline || rc=1; fi; '
                   f'if [ ! -d {base} ]; then printf "\\nABSENT_AFTER_PROBE\\n"; '
                   'elif [ "$rc" != 0 ]; then exit 1; fi; fi')
        reply = self._shell(f'pid.{role}.probe', command, 10, deadline=deadline)
        if reply.stdout.strip() == b'ABSENT' or reply.stdout.endswith(b'\nABSENT_AFTER_PROBE\n'):
            return 'absent', record
        try:
            raw_stat, remaining = reply.stdout.split(b'\nEXE\n', 1)
            raw_exe, cmd = remaining.split(b'CMD\n', 1)
            state, actual_start = stat_fields(raw_stat)
        except (ValueError, UnicodeError) as error:
            raise UnsafePID(f'{role}: unreadable process identity') from error
        if actual_start != born:
            raise UnsafePID(f'{role}: process starttime changed (PID reuse)')
        if state == 'Z':
            return 'zombie', record
        expected_native_exe = (self.remote + '/bin/genie-app').encode()
        expected_native_cmd = b'\0'.join([expected_native_exe, b'-s', b'exact-long.script']) + b'\0'
        native = raw_exe == expected_native_exe + b'\n' and cmd == expected_native_cmd
        script = {'model': 'model-entry.sh', 'wrapper': 'launch.sh', 'watchdog': 'watchdog.sh'}[role]
        expected_shell_cmd = b'/system/bin/sh\0' + (self.remote + '/' + script).encode() + b'\0'
        shell = raw_exe in (b'/system/bin/sh\n', b'/system/bin/mksh\n') and cmd == expected_shell_cmd
        if not ((role == 'model' and native) or shell):
            raise UnsafePID(f'{role}: executable/cmdline not owned by this exact run')
        if role == 'model' and native:
            self.result['native_process_observed'] = True
        return 'verified', record

    def _signal(self, role, record, sig, deadline):
        pid, born = record
        # The helper is inlined from trusted host source, not sourced from a
        # potentially changed device file. It rechecks immediately before kill,
        # but is NOT atomic: numeric-PID signalling retains a check-to-signal race.
        command = common(self.remote) + f'\nsignal_owned {role} {pid} {born} {sig}\n'
        reply = self._shell(f'signal.{role}.{sig}', command, 10, allow_error=True, deadline=deadline)
        if reply.code != 0 or reply.stdout.strip() not in (b'ABSENT', b'SIGNALLED', b''):
            raise UnsafePID(f'{role}: fresh signal identity guard refused')

    def _launch_and_wait(self):
        self._telemetry('before')
        self.launch_attempted = True
        start = self.clock.monotonic()
        self.deadline = start + 300
        command = _VALUE_DETACHED_LAUNCH(self.remote)
        self._shell('process.launch', command, 15, deadline=self.deadline)
        while True:
            if self.clock.monotonic() >= self.deadline:
                self.result['process_timeout'] = 'host_300s_deadline'
                return
            root = shlex.quote(self.remote + '/evidence')
            command = (f'if [ -f {root}/watchdog-timeout.txt ]; then printf "TIMEOUT\\n"; '
                       f'elif [ -f {root}/exit-code.txt ]; then printf "EXIT "; cat {root}/exit-code.txt; '
                       f'else printf "RUNNING\\n"; fi')
            status = self._shell('process.status', command, 10, deadline=self.deadline).stdout.strip()
            if status == b'TIMEOUT':
                self.result['process_timeout'] = 'remote_300s_watchdog'
                return
            if status.startswith(b'EXIT '):
                try:
                    exit_code = int(status[5:])
                    if not 0 <= exit_code <= 255:
                        raise ValueError('shell exit code outside0..255')
                    self.result['process_exit_code'] = exit_code
                except ValueError as error:
                    raise GuardError('malformed process exit status') from error
                return
            if status != b'RUNNING':
                raise GuardError('unexpected process status')
            state, _ = self._probe('model', self.deadline)
            if state == 'missing' and self.clock.monotonic() - start >= 60:
                raise GuardError('model identity record missing after60s startup deadline')
            self.clock.sleep(1)

    def _stop_owned(self):
        deadline = self.clock.monotonic() + 120
        if not self.launch_attempted:
            return {'all_absent': True, 'basis': 'no launch command attempted'}
        for role in ROLES:
            state, record = self._probe(role, deadline)
            if state == 'missing':
                raise UnsafePID(f'{role}: missing identity record; cannot prove cleanup')
            if state == 'verified':
                self._signal(role, record, 'TERM', deadline)
            grace = min(deadline, self.clock.monotonic() + 5)
            while state in ('verified', 'zombie') and self.clock.monotonic() < grace:
                self.clock.sleep(0.5)
                state, record = self._probe(role, deadline)
            if state == 'verified':
                self._signal(role, record, 'KILL', deadline)
                self.clock.sleep(1)
                state, _ = self._probe(role, deadline)
            if state != 'absent':
                raise UnsafePID(f'{role}: process absence not verified')
        # Generated watchdog has only <=1s sleep children; allow them to settle,
        # then independently recheck every recorded role before deleting its root.
        self.clock.sleep(1.1)
        for role in ROLES:
            state, _ = self._probe(role, deadline)
            if state != 'absent':
                raise UnsafePID(f'{role}: final process absence not verified')
        return {'all_absent': True, 'basis': 'fresh scoped PID/starttime probes; no name-wide kill'}

    def _pull_raw(self):
        try:
            self._adb('raw.pull', ['pull', self.remote + '/evidence', str(self.out / 'raw/device')], 180)
            self.result['raw_pull_completed'] = True
        except Exception as error:
            self.result['raw_pull_completed'] = False
            self.result.setdefault('capture_errors', []).append(str(error))
        # This marker is persisted BEFORE any optional metric function can run.
        self.result['raw_capture_attempted'] = True
        (self.out / 'raw-capture-status.json').write_text(json.dumps({
            'attempted': True, 'completed': self.result['raw_pull_completed'],
            'errors': self.result.get('capture_errors', [])}, indent=2) + '\n')

    def optional_metrics(self):
        return {'values': None, 'reason': 'Offline profile/provider/query review is separate; controller does not infer metrics.'}

    def _finish_remote(self):
        if not self.remote_created:
            self.result['cleanup'] = 'unknown_creation' if self.creation_attempted else 'not_created'
            return
        stopped = False
        try:
            self.result['process_cleanup'] = self._stop_owned()
            stopped = True
        except Exception as error:
            self.result['process_cleanup'] = {'all_absent': False, 'error': str(error)}
        self._pull_raw()  # also executed on process/identity/timeout errors
        if self.result['raw_pull_completed']:
            try:
                self.result['optional_metrics'] = self.optional_metrics()
            except Exception as error:
                self.result['optional_metrics'] = {'values': None, 'reason': str(error)}
        else:
            self.result['optional_metrics'] = {'values': None, 'reason': 'raw pull incomplete; no parsing attempted'}
        self._telemetry('after')
        if not stopped:
            self.result['cleanup'] = 'unknown_process_state_remote_root_retained'
            self.result['retained_remote_root'] = self.remote
            return
        if not self.result['raw_pull_completed']:
            self.result['cleanup'] = 'processes_absent_raw_incomplete_remote_root_retained'
            self.result['retained_remote_root'] = self.remote
            return  # never delete the only remaining raw evidence after a failed pull
        deadline = self.clock.monotonic() + 60
        try:
            self._shell('cleanup.remove', f'rm -rf {shlex.quote(self.remote)}', 30, deadline=deadline)
            self._shell('cleanup.absence', f'test ! -e {shlex.quote(self.remote)}', 15, deadline=deadline)
            self.result['cleanup'] = 'verified_absent'
        except Exception as error:
            self.result['cleanup'] = 'unknown_transport_or_cleanup_error'
            self.result['cleanup_error'] = str(error)

    def run(self, *, execute=False, reviewed_digest=None, pi_slot=None, run_id=None):
        if not execute:
            return plan()
        if self.out is not None:
            raise GuardError('controller instance is single-use; no in-place retry')
        if reviewed_digest != DIGEST or not pi_slot or not SAFE_ID.fullmatch(pi_slot):
            raise GuardError('execute requires the exact reviewed stage digest and an explicit one-use Pi slot ID')
        if not run_id or not SAFE_ID.fullmatch(run_id):
            raise GuardError('execute requires a safe fresh run ID')
        self.authorized = True
        self.remote = '/data/local/tmp/vibevoice-0031-paired-' + run_id
        self.output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.out = self.output_root / run_id
        self.out.mkdir(parents=True, exist_ok=False, mode=0o700)
        (self.out / 'raw/commands').mkdir(parents=True, mode=0o700)
        self.result = {'classification': 'collection_not_inference_validation', 'run_id': run_id,
                       'scope_adapter': _VALUE_SCOPE_RECEIPT,
                       'pi_slot': pi_slot, 'reviewed_stage_digest': reviewed_digest,
                       'scope': 'paired-prefill capture only; no AR continuation', 'remote_root': self.remote,
                       'controller_sources': {name: sha(Path(__file__).with_name(name)) for name in
                                              ('phone_return_controller.py', 'phone_return_shell.py', 'prepare_frozen_genie_stage.py')},
                       'native_process_observed': False, 'process_exit_code': None,
                       'runtime_success': None, 'provider_placement': None, 'fidelity': None,
                       'automatic_retry': False, 'long_script': True,
                       'raw_capture_attempted': False, 'raw_pull_completed': False,
                       'signal_guard_atomic': False,
                       'signal_race_boundary': 'Sequential /proc starttime/executable/argv checks then numeric-PID kill; no kernel pidfd binding.',
                       'optional_metrics': {'values': None, 'reason': 'no confirmed raw device evidence yet'}}
        phase = 'host_stage_preflight'
        try:
            manifest = self.stage_verifier(self.stage, reviewed_digest)
            self.stage_verified = True
            phase = 'phone_lock'
            with self.lease:
                try:
                    phase = 'slot_claim'
                    self.slot_root.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with (self.slot_root / (pi_slot + '.json')).open('x') as marker:
                        marker.write(json.dumps({'run_id': run_id, 'digest': reviewed_digest,
                                                 'consumed_before_first_adb': True}) + '\n')
                    self.slot_claimed = True
                    phase = 'identity'
                    self._identity()
                    phase = 'staging'
                    self._stage(manifest)
                    phase = 'bounded_process'
                    self._launch_and_wait()
                except Exception as error:
                    self.result['error'] = {'phase': phase, 'type': type(error).__name__, 'message': str(error)}
                finally:
                    self.cleaning_up = True
                    try:
                        self._finish_remote()
                    except Exception as error:
                        self.result['cleanup'] = 'unknown_controller_cleanup_error'
                        self.result['cleanup_error'] = str(error)
        except Exception as error:
            self.result['error'] = {'phase': phase, 'type': type(error).__name__, 'message': str(error)}
        finally:
            self.result['launch_command_attempted'] = self.launch_attempted
            self.result['remote_creation_confirmed'] = self.remote_created
            self.result['phone_lock_released'] = not self.lease.held
            self.result['adb_command_count'] = len(self.events)
            self.result.setdefault('cleanup', 'not_created')
            (self.out / 'collection.json').write_text(json.dumps(self.result, indent=2, sort_keys=True) + '\n')
            # No normalization/truncation of raw bytes; retain hashes of partial files too.
            files = sorted(p for p in self.out.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
            (self.out / 'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(self.out)}\n' for p in files))
        return self.result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--reviewed-stage-digest')
    p.add_argument('--pi-slot', help='Manual attestation of an actual Pi-granted one-use slot; not permission by itself')
    p.add_argument('--run-id')
    args = p.parse_args()
    try:
        controller = Controller()
        def request_stop(signum, frame):
            if controller.cleaning_up or controller.interrupt_seen:
                return  # cleanup remains bounded by its independent deadlines
            controller.interrupt_seen = True
            raise InterruptedError(f'controller signal {signum}; retain and clean up')
        if args.execute:
            os.umask(0o077)
            signal.signal(signal.SIGINT, request_stop)
            signal.signal(signal.SIGTERM, request_stop)
        result = controller.run(execute=args.execute, reviewed_digest=args.reviewed_stage_digest,
                                pi_slot=args.pi_slot, run_id=args.run_id)
    except Exception as error:
        print(f'{type(error).__name__}: {error}', file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    if result.get('mode') == 'plan_only':
        return 0
    return 0 if not result.get('error') and not result.get('process_timeout') and result.get('process_exit_code') == 0 and result.get('cleanup') == 'verified_absent' else 1


if __name__ == '__main__':
    raise SystemExit(main())

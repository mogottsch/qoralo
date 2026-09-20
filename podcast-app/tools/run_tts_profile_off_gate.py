#!/usr/bin/env python3
"""Plan-only by default; separately approved one-long-request profile-OFF diagnostic."""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess

from prepare_wiring_gate import PROJECT, digest
from run_wiring_gate import APP, TEST_APP, Device, DeviceSettings, stop_child
from duration_phone_guard import PhoneGuard, close_inherited_fds, host_identity
from run_tts_only_gate import capture_conditions

CONTRACT_SHA = '8d6b93557a2ac9d191b731735015bad6ce9d95c9b605861dc3c930cf9c82cd35'
PACK_ID = 'supertonic-3-t2048-l2048-parity'
OLD_MANIFEST_SHA = 'dc4ac737924d7d62e57ff5e166707198095c49e51d77cfed04a44d9e9435952d'
PRIVACY_SOURCE_SHA = '0d4a150fd4ae76d996d015bd79a172a9ad68220c24ea83ad3c917161cbf64120'


def check_controller(args):
    if digest(Path(__file__)) != args.approved_tts_controller_sha256:
        raise ValueError('reviewed long TTS controller changed under lock')
    if digest(PROJECT / 'tools/run_tts_only_gate.py') != PRIVACY_SOURCE_SHA:
        raise ValueError('reviewed private-condition capture dependency changed')


def verify_local_pack(entry, pinned):
    root = Path(entry['root'])
    if root != PROJECT / '.local/model-packs' / PACK_ID / 'current' or root.is_symlink():
        raise ValueError('only the new exact long-pack namespace is allowed')
    if entry['manifestSha256'] != pinned['supertonicManifestSha256'] or digest(root / 'manifest.json') != entry['manifestSha256']:
        raise ValueError('new local pack manifest changed')
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest['id'] != PACK_ID or len(manifest['files']) != 13:
        raise ValueError('unexpected new pack identity/inventory')
    if any(p.is_symlink() for p in root.rglob('*')):
        raise ValueError('unsafe pack link')
    if {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} != {'manifest.json', *(f['path'] for f in manifest['files'])}:
        raise ValueError('unlisted/missing pack file')
    for f in manifest['files']:
        p = root / f['path']
        if p.stat().st_size != f['bytes'] or digest(p) != f['sha256']:
            raise ValueError('new pack bytes changed: ' + f['path'])


def old_pack_identity(device):
    observed = device.shell(f'run-as {APP} sha256sum no_backup/model-packs/supertonic-3/current/manifest.json')
    if observed.split()[0] != OLD_MANIFEST_SHA:
        raise ValueError('accepted old pack manifest mismatch; do not repair or replace')


def stage_new_pack(device, entry, remote, cleanup):
    """Only the new namespace; keep partial private staging on failure, no retry/repair."""
    namespace = f'no_backup/model-packs/{PACK_ID}'
    destination = namespace + '/current'
    def shell(script, **kwargs):
        return device.shell(f'run-as {APP} sh -c {shlex.quote(script)}', **kwargs)
    observed = shell(f'if test -L {namespace} || test -L {destination}; then echo UNSAFE; '
                     f'elif test -f {destination}/manifest.json; then sha256sum {destination}/manifest.json; '
                     f'elif test -e {namespace}; then echo INCOMPLETE; else echo ABSENT; fi').strip()
    if observed == 'ABSENT':
        cleanup['scratchCreationAttempted'] = True
        device.shell(f'mkdir {remote}')  # no -p: never take ownership of an existing scratch root
        cleanup['scratchCreated'] = True
        incoming = remote + '/current'
        device.run(['push', entry['root'], incoming], timeout=180)
        device.shell(f'chmod -R a+rX {incoming}')
        # mkdir reserves only this new namespace. Never overwrite or clear any existing current pack.
        shell(f'set -e; mkdir {namespace}; cp -R {incoming} {namespace}/.incoming; '
              f'test ! -e {destination}; mv {namespace}/.incoming {destination}', timeout=120)
        observed = shell(f'sha256sum {destination}/manifest.json').strip()
    if not observed or observed.split()[0] != entry['manifestSha256']:
        raise ValueError('new device pack absent/partial/mismatched; preserve it and stop')
    # Full authenticated 13-file verification runs in :generation before any constructor.
    old_pack_identity(device)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--approved-candidate-sha256')
    parser.add_argument('--approved-host-guard-sha256')
    parser.add_argument('--approved-tts-controller-sha256')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', default='R5CW81PR8SY')
    args = parser.parse_args()
    value = json.loads(args.candidate.read_text())
    if not re.fullmatch(r'tts-long-[a-z0-9-]{1,64}', args.run_id):
        raise ValueError('unsafe long probe run ID')
    if value.get('sourceDirty') or value.get('kind') != 'tts-long-profile-off' or value['contractSha256'] != CONTRACT_SHA:
        raise ValueError('unreviewable long probe candidate')
    pinned_path = PROJECT / 'app/src/debug/assets/tts-long-profile-off/contract.json'
    pinned = json.loads(pinned_path.read_text())
    if digest(pinned_path) != CONTRACT_SHA or value['contract'] != pinned:
        raise ValueError('long probe contract changed')
    for kind in ('app', 'test'):
        item = value[kind]; path = Path(item['path'])
        if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            raise ValueError('probe APK changed since preflight')
    verify_local_pack(value['modelPack'], pinned)
    host = host_identity()
    if not args.execute:
        print(json.dumps({'mode': 'plan_only', 'kind': 'tts-long-profile-off', 'collectProfiles': False, 'profileEvidence': 'UNAVAILABLE_BY_DESIGN', 'adbUsed': False, 'logicalTtsRequests': 1,
                          'gemmaRequests': 0, 'capacityProbes': 1, 'hostTimeoutSeconds': 450,
                          'packPushSeconds': 180, 'packCopySeconds': 120, 'packId': PACK_ID,
                          'ttsControllerSha256': digest(Path(__file__)), 'privacySourceSha256': PRIVACY_SOURCE_SHA, 'hostGuard': host}))
        return
    if (os.environ.get('PODCAST_PHONE_PRIORITY') != 'approved' or args.approved_candidate_sha256 != digest(args.candidate)
            or args.approved_host_guard_sha256 != host['sha256']
            or args.approved_tts_controller_sha256 != digest(Path(__file__))):
        raise SystemExit('separate Pi phone slot, exact NEW pack/candidate, guard AND long controller approval required')
    check_controller(args)
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'candidate.json').write_text(json.dumps(value, indent=2))
    lock = (PROJECT.parent / 'artifacts/locks/phone.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    os.set_inheritable(lock.fileno(), False)
    (args.output / 'host-guard-identity.json').write_text(json.dumps({**host, 'lockInheritable': os.get_inheritable(lock.fileno()), 'ttsControllerSha256': digest(Path(__file__)), 'privacySourceSha256': PRIVACY_SOURCE_SHA}, indent=2))
    device = Device(args.adb, args.serial, args.output)
    guard = PhoneGuard(device, args.output, args.candidate, args.approved_candidate_sha256, args.approved_host_guard_sha256)
    settings = DeviceSettings(device.shell)
    identity_ok = False; launched = False; logs = None
    remote = '/data/local/tmp/podcast-' + args.run_id
    cleanup = {'errors': [], 'settingsErrors': [], 'scratchCreated': False, 'packagesRetained': True}
    def interrupted(signum, frame):
        raise InterruptedError(f'signal {signum}; cleanup only, no retry')
    signal.signal(signal.SIGINT, interrupted); signal.signal(signal.SIGTERM, interrupted)
    try:
        guard.identity(); identity_ok = True
        (args.output / 'settings-before.json').write_text(json.dumps(settings.capture(), indent=2))
        capture_conditions(device, args.output, 'before')
        old_pack_identity(device)
        check_controller(args); guard.checkpoint('before-app-install')
        device.run(['install', '-r', '-t', '--user', '0', value['app']['path']], timeout=180)
        check_controller(args); guard.checkpoint('before-test-install')
        device.run(['install', '-r', '-t', '--user', '0', value['test']['path']], timeout=180)
        check_controller(args); guard.idle(); verify_local_pack(value['modelPack'], pinned)
        stage_new_pack(device, value['modelPack'], remote, cleanup)
        with (args.output / 'logcat.txt').open('wb') as out, (args.output / 'logcat.stderr').open('wb') as err:
            logs = subprocess.Popen(device.prefix + ['logcat', '-v', 'threadtime', '-T', '1'], stdout=out, stderr=err, start_new_session=True, close_fds=True)
        command = ('am instrument -w -r -e class dev.qoralo.podcast.wiring.TtsOnlyTest'
                   f' -e ttsOnlyApproved {CONTRACT_SHA} -e ttsOnlyRunId {args.run_id}'
                   f" -e appApkSha256 {value['app']['sha256']} -e testApkSha256 {value['test']['sha256']}"
                   f' {TEST_APP}/androidx.test.runner.AndroidJUnitRunner')
        check_controller(args); guard.checkpoint('before-instrument')
        launched = True
        output = device.shell(command, timeout=450)
        (args.output / 'controller-result.json').write_text(json.dumps({'instrumentationCompleted': 'OK (' in output and 'FAILURES!!!' not in output,
            'nativeOutcome': 'inspect saved service-result.json; collection success is not synthesis/provider/listening approval',
            'neuralInferenceRequested': True, 'logicalTtsRequestsAuthorized': 1, 'gemmaRequests': 0, 'noncanonicalCapacityProbe': True, 'collectProfiles': False, 'profileEvidence': 'UNAVAILABLE_BY_DESIGN'}))
        if 'OK (' not in output or 'FAILURES!!!' in output:
            raise RuntimeError('probe instrumentation failed; preserve raw evidence')
    except BaseException as error:
        (args.output / 'controller-failure.json').write_text(json.dumps({'error': repr(error), 'launched': launched}))
        raise
    finally:
        device.enforce_quota = False
        signal.signal(signal.SIGINT, signal.SIG_IGN); signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if launched:
            for name, action in [
                ('stop-app', lambda: device.shell(f'am force-stop {APP}; am force-stop {TEST_APP}')),
                ('pull', lambda: device.run(['exec-out', 'run-as', APP, 'tar', '-cf', '-', f'files/tts-long/{args.run_id}'], timeout=120, binary=True)),
                ('pid-absence', lambda: device.shell(f'pidof {APP} {APP}:generation {TEST_APP}', check=False)),
            ]:
                try:
                    result = action()
                    if name == 'pull': result.rename(args.output / 'private-evidence.tar')
                    elif name == 'pid-absence':
                        cleanup['pidStdout'] = result
                        last = args.output / f'{device.counter:03d}-command'
                        absent = last.with_suffix('.exit').read_text() == '1' and not result.strip() and not last.with_suffix('.stderr').read_text().strip()
                        cleanup['appGenerationTestPidsAbsent'] = absent
                        if not absent: raise RuntimeError('process still present or absence unproven; no additional action')
                except Exception as error:
                    cleanup['errors'].append({'phase': name, 'error': repr(error)})
        if cleanup['scratchCreated']:
            try:
                device.shell(f'rm -rf {remote}')
                check = device.shell(f'if test -e {remote}; then echo PRESENT; else echo ABSENT; fi')
                if check.strip() != 'ABSENT': raise RuntimeError('owned scratch removal unproven')
                cleanup['scratchRemoved'] = True
            except Exception as error:
                cleanup['errors'].append({'phase': 'owned-pack-scratch', 'error': repr(error)})
        elif cleanup.get('scratchCreationAttempted'):
            cleanup['errors'].append({'phase': 'owned-pack-scratch', 'error': 'creation did not return success; ownership/absence unproven, no deletion attempted'})
        if identity_ok:
            try:
                old_pack_identity(device)
                capture_conditions(device, args.output, 'after')
            except Exception as error:
                cleanup['errors'].append({'phase': 'old-pack-and-conditions-after', 'error': repr(error)})
        if identity_ok and not launched:
            try: guard.idle(); cleanup['appGenerationTestPidsAbsent'] = True
            except Exception as error: cleanup['errors'].append({'phase': 'prelaunch-pid-absence', 'error': repr(error)})
        cleanup['settingsErrors'] = settings.restore() + guard.readback_settings()
        if logs is not None:
            try: stop_child(logs)
            except Exception as error: cleanup['errors'].append({'phase': 'logcat-reap', 'error': repr(error)})
        (args.output / 'cleanup.json').write_text(json.dumps(cleanup, indent=2))
        fcntl.flock(lock, fcntl.LOCK_UN); lock.close()
        if cleanup['errors'] or cleanup['settingsErrors']:
            raise RuntimeError('cleanup incomplete; see retained cleanup.json')


if __name__ == '__main__':
    close_inherited_fds()
    main()

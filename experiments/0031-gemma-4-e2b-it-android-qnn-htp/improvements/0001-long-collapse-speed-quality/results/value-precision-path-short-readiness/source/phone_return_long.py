#!/usr/bin/env python3
"""Fixed exact-long scope over the hash-pinned reviewed lifecycle, plan-only default.

No edits to the short controller/shell or stage. Materialize only enumerated
scope literals and the separately reviewed launch redirection correction in
isolated Python modules. This is not an arbitrary prompt/controller framework.
"""
import hashlib
import json
from pathlib import Path
import shlex
import sys
import types

TOOLS = Path(__file__).resolve().parent
TRACK = TOOLS.parent
BASE_CONTROLLER_SHA = 'e0e91e1855239a5ab349555f81ea050b94ea2997ba01e59c9c705444cdc6e9d2'
BASE_SHELL_SHA = '4ce478abf5b44ea0ae32cb9f490eb319f37fd54243fa91fb1433883c8be9b7bb'
SHORT_DIGEST = '584841604ecf97a1a916c9a7f765e49ff9f7a2ee751a61fda9e9e6588f02fe25'
LONG_DIGEST = '047dd808fe49656105934a9afed521fc3c4acdd0c6d278d0ed5685a98a0b846e'
LONG_STAGE_NAME = 'stage-freeze-long-20260910T163842Z-01'
GATE_A_SHA = '1290cc51948e82fd974b175c46a1a67cd0ff0db382ad1db047993f9ad7849aff'
OLD_LAUNCH = '''        prefix = shlex.quote(self.remote)
        command = (f'cd {prefix} && nohup /system/bin/sh {shlex.quote(self.remote + "/launch.sh")} '
                   f'</dev/null >evidence/launcher.stdout 2>evidence/launcher.stderr &')'''
NEW_LAUNCH = '''        command = _LONG_DETACHED_LAUNCH(self.remote)'''


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def detached_launch_command(remote, shell='/system/bin/sh'):
    # No background AND-list whose intermediary shell can retain transport pipes.
    # launch.sh already sets its own cwd. All three standard streams are explicit.
    return (f'nohup {shlex.quote(shell)} {shlex.quote(remote + "/launch.sh")} '
            f'</dev/null >{shlex.quote(remote + "/evidence/launcher.stdout")} '
            f'2>{shlex.quote(remote + "/evidence/launcher.stderr")} &')


def replace_exact(source, old, new, count):
    if source.count(old) != count:
        raise RuntimeError(f'reviewed source substitution count mismatch: {old[:70]!r}')
    return source.replace(old, new)


def materialize_sources():
    controller_bytes = (TOOLS / 'phone_return_controller.py').read_bytes()
    shell_bytes = (TOOLS / 'phone_return_shell.py').read_bytes()
    if sha_bytes(controller_bytes) != BASE_CONTROLLER_SHA or sha_bytes(shell_bytes) != BASE_SHELL_SHA:
        raise RuntimeError('reviewed short lifecycle source changed; new review required')
    controller = controller_bytes.decode()
    changes = [
        ('single engineering short/max16 process', 'single engineering exact-long/max2048 process', 1),
        ('stage-freeze-20260910T105830Z-01', LONG_STAGE_NAME, 1),
        (SHORT_DIGEST, LONG_DIGEST, 1),
        ('one fresh-dialog first-short engineering/noncanonical max16 only',
         'one fresh-dialog exact-long engineering/max2048 only (not a campaign)', 1),
        ('first-short engineering max16 only', 'exact-long engineering max2048 only (not a campaign)', 1),
        ("'.local/phone-return-runs'", "'.local/phone-return-long-runs'", 1),
        ('first-short.script', 'exact-long.script', 1),
        ("'long_script': False", "'long_script': True", 2),
        ("'classification': 'collection_not_inference_validation', 'run_id': run_id,",
         "'classification': 'collection_not_inference_validation', 'run_id': run_id,\n                       'scope_adapter': _LONG_SCOPE_RECEIPT,", 1),
        (OLD_LAUNCH, NEW_LAUNCH, 1),
    ]
    for old, new, count in changes:
        controller = replace_exact(controller, old, new, count)
    shell = replace_exact(shell_bytes.decode(), 'first-short.script', 'exact-long.script', 2)
    return controller, shell, [{'old': old, 'new': new, 'count': count} for old, new, count in changes]


def load_lifecycle():
    gate_path = TRACK / 'results/phone-return-short-attempt-01/result.json'
    gate_bytes = gate_path.read_bytes()
    if sha_bytes(gate_bytes) != GATE_A_SHA:
        raise RuntimeError('accepted GateA evidence identity changed')
    gate = json.loads(gate_bytes)
    if gate['analysis_issues'] or not gate['observations']['query_completion_observed_beyond_exit_code']:
        raise RuntimeError('GateA completion prerequisite not met')
    controller_source, shell_source, changes = materialize_sources()
    receipt = {'scope': 'one exact-long/max2048 request; preparation is not phone permission',
               'base_reviewed_commit': '62b8a16', 'gate_a_commit': '81f4ede',
               'gate_a_result_sha256': GATE_A_SHA, 'long_stage_digest': LONG_DIGEST,
               'template_controller_sha256': BASE_CONTROLLER_SHA, 'template_shell_sha256': BASE_SHELL_SHA,
               'materialized_controller_sha256': sha_bytes(controller_source.encode()),
               'materialized_shell_sha256': sha_bytes(shell_source.encode()),
               'adapter_sha256': sha_bytes(Path(__file__).read_bytes()),
               'source_changes': changes,
               'launch_change': 'direct nohup, no cd/AND-list, absolute stdin/stdout/stderr redirections',
               'original_short_sources_modified': False, 'signal_guard_atomic': False}
    shell = types.ModuleType('gemma_fp16_long_shell')
    shell.__file__ = str(TOOLS / 'phone_return_shell.py')
    sys.modules[shell.__name__] = shell
    exec(compile(shell_source, shell.__file__, 'exec'), shell.__dict__)
    controller = types.ModuleType('gemma_fp16_long_controller')
    controller.__file__ = str(TOOLS / 'phone_return_controller.py')
    sys.modules[controller.__name__] = controller
    controller._LONG_DETACHED_LAUNCH = detached_launch_command
    controller._LONG_SCOPE_RECEIPT = receipt
    exec(compile(controller_source, controller.__file__, 'exec'), controller.__dict__)
    # Only the isolated module's function references are changed, never the
    # imported short module or its files. Rechecks and watchdog get exact-long argv.
    controller.common, controller.scripts = shell.common, shell.scripts
    return controller, receipt


if __name__ == '__main__':
    lifecycle, _ = load_lifecycle()
    raise SystemExit(lifecycle.main())

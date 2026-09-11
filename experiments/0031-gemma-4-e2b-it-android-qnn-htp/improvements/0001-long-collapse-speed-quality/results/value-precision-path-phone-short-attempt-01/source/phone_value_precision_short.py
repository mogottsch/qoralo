#!/usr/bin/env python3
"""New precision-path short scope over the preserved, guarded phone lifecycle.

Plan-only unless an actual Pi-granted slot is explicitly supplied with --execute.
The only changes are frozen identities, scope/output names, an audit receipt,
and the already tested direct-nohup launch. No old source/stage is modified.
"""
import hashlib
import json
from pathlib import Path
import sys
import types

TOOLS = Path(__file__).resolve().parent
TRACK = TOOLS.parent
BASE_CONTROLLER_SHA = 'e0e91e1855239a5ab349555f81ea050b94ea2997ba01e59c9c705444cdc6e9d2'
BASE_SHELL_SHA = '4ce478abf5b44ea0ae32cb9f490eb319f37fd54243fa91fb1433883c8be9b7bb'
COPY_HELPER_SHA = '34c56e7a2ec92c68a7a781ca7c7230a3ad8ce60d249dbd93e6c4cd359b403ccf'
LAUNCH_HELPER_SHA = '63377f368f83c9b2bfe5e09fec7a276ad2ddc2481acb1f97d1987e38d90235e0'
STAGE_NAME = 'value-path-short-20260911T115043Z-01'
STAGE_DIGEST = '206ca960a69f915f81cb5c61dde5684259f8fbee8a37e14ef8b8bbf9fcafc78b'
CONTEXT_SHA = '27e19e32ef479dfb39b53e6530cd25105c3c8e9ccf9fa4b9e9af4b5d770fabdd'
CONTEXT_RESULT_SHA = 'ca2d724d2d16c54459db8de4351e2d7681221083c7e53a8128d72ecc796e7228'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def materialize_sources():
    pins = {'phone_return_controller.py': BASE_CONTROLLER_SHA,
            'phone_return_shell.py': BASE_SHELL_SHA,
            'prepare_frozen_genie_stage.py': COPY_HELPER_SHA,
            'phone_return_long.py': LAUNCH_HELPER_SHA}
    sources = {name: (TOOLS/name).read_bytes() for name in pins}
    if any(digest(sources[name]) != expected for name, expected in pins.items()):
        raise RuntimeError('pinned lifecycle/helper source changed')
    # Importing this utility does not call its old candidate load_lifecycle gate.
    from phone_return_long import OLD_LAUNCH, detached_launch_command, replace_exact
    changes = [
        ('stage-freeze-20260910T105830Z-01', STAGE_NAME, 1),
        ('584841604ecf97a1a916c9a7f765e49ff9f7a2ee751a61fda9e9e6588f02fe25', STAGE_DIGEST, 1),
        ("'.local/phone-return-runs'", "'.local/value-precision-phone-short-runs'", 1),
        ("'/data/local/tmp/vibevoice-0031-fp16-'", "'/data/local/tmp/vibevoice-0031-value-'", 1),
        ('one fresh-dialog first-short engineering/noncanonical max16 only',
         'precision-path candidate: one fresh-dialog first-short engineering/noncanonical max16 only', 1),
        ("'scope': 'first-short engineering max16 only'",
         "'scope': 'precision-path first-short engineering max16 only'", 1),
        ("'classification': 'collection_not_inference_validation', 'run_id': run_id,",
         "'classification': 'collection_not_inference_validation', 'run_id': run_id,\n                       'scope_adapter': _VALUE_SCOPE_RECEIPT,", 1),
        (OLD_LAUNCH, '        command = _VALUE_DETACHED_LAUNCH(self.remote)', 1),
    ]
    controller = sources['phone_return_controller.py'].decode()
    for old, new, count in changes:
        controller = replace_exact(controller, old, new, count)
    return controller, sources['phone_return_shell.py'].decode(), changes, detached_launch_command


def load_lifecycle():
    result_bytes = (TRACK/'results/value-precision-path-context-attempt-01/result.json').read_bytes()
    if digest(result_bytes) != CONTEXT_RESULT_SHA:
        raise RuntimeError('precision-path context evidence changed')
    result = json.loads(result_bytes)
    if (result['context']['sha256'] != CONTEXT_SHA or
            not result['metadata_validation']['metadata_gate_passed']):
        raise RuntimeError('precision-path compiled context prerequisite failed')
    source, shell_source, changes, launch = materialize_sources()
    receipt = {
        'scope': 'precision-path short/max16; not permission, inference proof or canonical campaign',
        'context_sha256': CONTEXT_SHA, 'context_result_sha256': CONTEXT_RESULT_SHA,
        'context_commit': 'ef0bbb0', 'stage_digest': STAGE_DIGEST,
        'template_controller_sha256': BASE_CONTROLLER_SHA, 'template_shell_sha256': BASE_SHELL_SHA,
        'copy_helper_sha256': COPY_HELPER_SHA, 'launch_helper_sha256': LAUNCH_HELPER_SHA,
        'materialized_controller_sha256': digest(source.encode()),
        'materialized_shell_sha256': digest(shell_source.encode()),
        'adapter_sha256': digest(Path(__file__).read_bytes()),
        'source_changes': [{'old': old, 'new': new, 'count': count} for old, new, count in changes],
        'original_sources_or_stages_modified': False, 'signal_guard_atomic': False,
    }
    module = types.ModuleType('gemma_value_precision_short_controller')
    module.__file__ = str(TOOLS/'phone_return_controller.py')
    sys.modules[module.__name__] = module
    module._VALUE_DETACHED_LAUNCH = launch
    module._VALUE_SCOPE_RECEIPT = receipt
    exec(compile(source, module.__file__, 'exec'), module.__dict__)
    return module, receipt


if __name__ == '__main__':
    lifecycle, _ = load_lifecycle()
    raise SystemExit(lifecycle.main())

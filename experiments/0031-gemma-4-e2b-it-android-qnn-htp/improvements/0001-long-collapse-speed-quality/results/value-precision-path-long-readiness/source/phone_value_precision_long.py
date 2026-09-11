#!/usr/bin/env python3
"""Exact-long scope for the new candidate; plan-only without a fresh Pi slot."""
import hashlib
import json
from pathlib import Path
import sys
import types

import phone_value_precision_short as short

TOOLS = Path(__file__).resolve().parent
TRACK = TOOLS.parent
SHORT_ADAPTER_SHA = '4b864c442b56b2730aedc89808a8a96337027889a6c54a6243dc2cd383ce3e20'
SHORT_RESULT_SHA = '6bd6114f2fcaddf10db666727bc36712ea9aa1b6dae46ab640eba8bfd24d0f3f'
STAGE_NAME = 'value-path-long-20260911T125353Z-01'
STAGE_DIGEST = '373ca1b67b3ce65920127eede27df84b2832a783aee14d934d328835bc9f0996'
CONTEXT_SHA = short.CONTEXT_SHA


def materialize_sources():
    if short.digest((TOOLS/'phone_value_precision_short.py').read_bytes()) != SHORT_ADAPTER_SHA:
        raise RuntimeError('new candidate short adapter changed')
    source, shell, _, launch = short.materialize_sources()
    changes = [
        (short.STAGE_NAME, STAGE_NAME, 1), (short.STAGE_DIGEST, STAGE_DIGEST, 1),
        ("'.local/value-precision-phone-short-runs'", "'.local/value-precision-phone-long-runs'", 1),
        ('single engineering short/max16 process', 'single engineering exact-long/max2048 process', 1),
        ('precision-path candidate: one fresh-dialog first-short engineering/noncanonical max16 only',
         'precision-path candidate: one fresh-dialog exact-long/max2048 diagnostic only', 1),
        ('precision-path first-short engineering max16 only', 'precision-path exact-long engineering max2048 only', 1),
        ('first-short.script', 'exact-long.script', 1),
        ("'long_script': False", "'long_script': True", 2),
    ]
    from phone_return_long import replace_exact
    for old, new, count in changes:
        source = replace_exact(source, old, new, count)
    shell = replace_exact(shell, 'first-short.script', 'exact-long.script', 2)
    return source, shell, changes, launch


def load_lifecycle():
    path = TRACK/'results/value-precision-path-phone-short-attempt-01/result.json'
    data = path.read_bytes()
    if short.digest(data) != SHORT_RESULT_SHA:
        raise RuntimeError('new candidate short evidence changed')
    gate = json.loads(data)
    if gate['analysis_issues'] or not gate['observations']['query_completion_observed_beyond_exit_code']:
        raise RuntimeError('new candidate short prerequisite failed')
    # Also retain the compiled-context prerequisite without changing old modules.
    _, short_receipt = short.load_lifecycle()
    source, shell_source, changes, launch = materialize_sources()
    receipt = {'scope': 'one precision-path exact-long/max2048 diagnostic; not phone permission',
        'context_sha256': CONTEXT_SHA, 'stage_digest': STAGE_DIGEST,
        'short_result_sha256': SHORT_RESULT_SHA, 'short_result_commit': 'df07102',
        'short_adapter_sha256': SHORT_ADAPTER_SHA, 'short_scope_receipt': short_receipt,
        'materialized_controller_sha256': short.digest(source.encode()),
        'materialized_shell_sha256': short.digest(shell_source.encode()),
        'source_changes': [{'old': a, 'new': b, 'count': c} for a,b,c in changes],
        'adapter_sha256': short.digest(Path(__file__).read_bytes()),
        'original_sources_or_stages_modified': False, 'signal_guard_atomic': False}
    shell = types.ModuleType('gemma_value_precision_long_shell')
    shell.__file__ = str(TOOLS/'phone_return_shell.py')
    sys.modules[shell.__name__] = shell
    exec(compile(shell_source, shell.__file__, 'exec'), shell.__dict__)
    module = types.ModuleType('gemma_value_precision_long_controller')
    module.__file__ = str(TOOLS/'phone_return_controller.py')
    sys.modules[module.__name__] = module
    module._VALUE_DETACHED_LAUNCH = launch
    module._VALUE_SCOPE_RECEIPT = receipt
    exec(compile(source, module.__file__, 'exec'), module.__dict__)
    module.common, module.scripts = shell.common, shell.scripts
    return module, receipt


if __name__ == '__main__':
    lifecycle, _ = load_lifecycle()
    raise SystemExit(lifecycle.main())

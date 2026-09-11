#!/usr/bin/env python3
"""Serial case-specific exactT preparation/export; no neural forward or phone use."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from materialize import REPO, ROOT, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--vector-result', type=Path, required=True)
    p.add_argument('--vocoder-graph-result', type=Path, required=True)
    args = p.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'.local').resolve()):
        p.error('private campaign output only')
    args.output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads((ROOT.parent/'protocol/inputs.json').read_text())
    frozen = json.loads((ROOT.parent/'protocol/freeze.json').read_text())
    ts = list(dict.fromkeys(c['text_extent'] for c in protocol['chunks']))
    proof_python = REPO/'experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/.local/proof-venv/bin/python'
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='4', MKL_NUM_THREADS='1')
    cpus = sorted(os.sched_getaffinity(0))[:4]
    started = time.monotonic()
    summary = dict(status='started', campaign_seconds_bound=1800, generic_app_ready_pack=False, native_text_extents=ts,
                   freeze_sha256=sha(ROOT.parent/'protocol/freeze.json'),
                   bundle_manifest_sha256=frozen['bundle_manifest_sha256'], components=[])
    def save():
        (args.output/'campaign.json').write_text(json.dumps(summary, indent=2)+'\n')
    def record(label, result_path):
        result = json.loads(result_path.read_text())
        if result['status'] != 'constructor_export_passed_not_execution_proof' or result['session_Run_calls'] != 0:
            raise ValueError('constructor/export did not pass, no retries')
        summary['components'].append(dict(name=label, compile_result=str(result_path.resolve()),
            compile_result_sha256=sha(result_path)))
        save()
    def compile(label, graph_result):
        if time.monotonic()-started > 1200:
            raise TimeoutError('do not start another constructor without its full600s cleanup allowance')
        phase = args.output/('compile-'+label)
        with (args.output/(label+'-launcher.log')).open('x') as log:
            subprocess.run([sys.executable, str(ROOT/'tools/compile_context.py'), '--graph-result', str(graph_result),
                            '--phase', str(phase)], stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
        record(label, phase/'data/result.json')
    def limits():
        resource.setrlimit(resource.RLIMIT_AS, (8 << 30, 8 << 30))
        os.sched_setaffinity(0, cpus)
    save()
    try:
        record('vector', args.vector_result)
        compile('vocoder', args.vocoder_graph_result)
        for t in ts:
            for component in ('duration', 'text'):
                label = f'{component}-t{t}'
                graph_dir = args.output/'derivatives'/label
                if time.monotonic()-started > 1200:
                    raise TimeoutError('campaign budget exhausted before next derivative')
                with (REPO/'artifacts/locks/heavy-ram.lock').open('a') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    with (args.output/(label+'-materialize.log')).open('x') as log:
                        subprocess.run([str(proof_python), str(ROOT/'tools/materialize.py'), '--component', component,
                            '--text-length', str(t), '--output-dir', str(graph_dir)], env=env, preexec_fn=limits,
                            stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)
                compile(label, graph_dir/'result.json')
                print(label+': prepared and exported, zero Run', flush=True)
        summary['status'] = 'all_contexts_exported_not_physical_execution_proof'
    except BaseException as e:
        summary.update(status='error', error=str(e))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()

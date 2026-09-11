#!/usr/bin/env python3
"""QNN System binary metadata only; conservative per-context signed-size gate.

Sum declared storage, add128MiB, round64MiB, require another64MiB below INT32_MAX.
This is a planning margin, not the proprietary allocator formula or measured RSS.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from materialize import ROOT, sha

SDK = Path('/home/moritz/opt/qairt/2.49.0.260730')
IMAGE = 'sha256:b170f55a61548cc3a78eb667837934e0f2f8659bf7cd0db7a71ec40e90d2f321'
MiB = 1024**2


def footprint(graph):
    v2 = graph['graphBlobInfoV2']
    values = {k: int(v2[k]) for k in ('ioTensorSize', 'opDataSize', 'constSize', 'ddrTensorSize', 'sharedWeightsSize')}
    values['spillFillBufferSize'] = int(graph['graphBlobInfo']['info']['spillFillBufferSize'])
    base = sum(values.values())
    aligned = ((base + 128*MiB + 64*MiB-1)//(64*MiB))*(64*MiB)
    margin = 2**31-1-aligned
    return dict(declared_storage_bytes=values, summed_declared_bytes=base,
        extra_planning_allowance_bytes=128*MiB, conservative_rounding_bytes=64*MiB,
        aligned_planning_estimate_bytes=aligned, signed_size_limit_bytes=2**31-1,
        remaining_signed_margin_bytes=margin, passes_conservative_gate=margin >= 64*MiB)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--campaign', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to((ROOT/'.local').resolve()):
        p.error('private output required')
    campaign = json.loads(args.campaign.read_text())
    if campaign['status'] != 'all_contexts_exported_not_physical_execution_proof':
        raise ValueError('incomplete context campaign')
    out.mkdir(parents=True, exist_ok=False)
    entries, pins = [], {}
    for item in campaign['components']:
        label, result_path = item['name'], Path(item['compile_result'])
        if sha(result_path) != item['compile_result_sha256']:
            raise ValueError('compile receipt changed')
        result = json.loads(result_path.read_text())
        filename = result['component']+'-context_qnn.bin'
        binary = result_path.parent/filename
        pin = result['artifacts'][filename]
        if sha(binary) != pin['sha256'] or binary.stat().st_size != pin['bytes']:
            raise ValueError('context binary changed')
        if not binary.resolve().is_relative_to((ROOT/'.local').resolve()):
            raise ValueError('context outside private HTP tree')
        entries += [label, '/input/'+str(binary.relative_to(ROOT))]
        pins[label] = pin
    if len(pins) != 32:
        raise ValueError('expected32 case-specific contexts')
    script = 'set -e; while [ "$#" -gt 0 ]; do label="$1"; binary="$2"; shift 2; /sdk/bin/x86_64-linux-clang/qnn-context-binary-utility --context_binary="$binary" --json_file="/output/$label.json"; done'
    argv = ['docker', 'create', '--init', '--pull=never', '--network=none', '--memory=1g', '--memory-swap=1g',
        '--cpus=1', '--pids-limit=64', '--user', f'{os.getuid()}:{os.getgid()}',
        '--mount', f'type=bind,src={SDK},dst=/sdk,readonly',
        '--mount', f'type=bind,src={ROOT},dst=/input,readonly',
        '--mount', f'type=bind,src={out},dst=/output',
        '--env', 'LD_LIBRARY_PATH=/sdk/lib/x86_64-linux-clang', IMAGE, 'bash', '-c', script, 'metadata', *entries]
    (out/'command.json').write_text(json.dumps(argv, indent=2)+'\n')
    cid = subprocess.run(argv, capture_output=True, text=True, check=True, timeout=10).stdout.strip()
    if len(cid) != 64 or any(c not in '0123456789abcdef' for c in cid):
        raise ValueError('Docker did not return immutable CID')
    started = time.monotonic()
    try:
        process = subprocess.run(['docker', 'start', '-a', cid], capture_output=True, text=True, timeout=90)
        (out/'stdout.log').write_text(process.stdout)
        (out/'stderr.log').write_text(process.stderr)
        process.check_returncode()
    finally:
        subprocess.run(['docker', 'rm', '-f', cid], capture_output=True, text=True, check=True, timeout=10)
        absent = subprocess.run(['docker', 'container', 'inspect', cid], capture_output=True, text=True, timeout=10)
        (out/'cleanup.json').write_text(json.dumps(dict(cid=cid, exit=absent.returncode, stderr=absent.stderr), indent=2)+'\n')
        if absent.returncode == 0 or 'No such container' not in absent.stderr:
            raise RuntimeError('owned container cleanup unverified')
    rows = []
    for label, pin in pins.items():
        graphs = json.loads((out/(label+'.json')).read_text())['info']['graphs']
        if len(graphs) != 1:
            raise ValueError('expected exactly one graph per context')
        rows.append(dict(component=label, context_binary=pin, **footprint(graphs[0]['info'])))
    result = dict(evidence_class='offline_QNN_System_metadata_no_context_load_or_Run', components=rows,
        all_pass=all(r['passes_conservative_gate'] for r in rows),
        claim_boundary='Storage sum plus conservative headroom/rounding, not guaranteed allocation or measured peak.',
        elapsed_seconds=time.monotonic()-started, utility_sha256=sha(SDK/'bin/x86_64-linux-clang/qnn-context-binary-utility'),
        container_absent=True)
    (out/'footprints.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(all_pass=result['all_pass'], contexts=len(rows),
        max_aligned_estimate=max(r['aligned_planning_estimate_bytes'] for r in rows),
        min_signed_margin=min(r['remaining_signed_margin_bytes'] for r in rows)), indent=2))


if __name__ == '__main__':
    main()

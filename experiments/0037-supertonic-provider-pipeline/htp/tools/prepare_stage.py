#!/usr/bin/env python3
"""Private standalone stage: no CPU durations/features, raw text, app or device writes."""
import argparse
import json
from pathlib import Path
import shutil
from materialize import REPO, ROOT, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--campaign', type=Path, required=True)
    p.add_argument('--footprints', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'.local').resolve()):
        p.error('private stage only')
    campaign = json.loads(args.campaign.read_text())
    footprints = json.loads(args.footprints.read_text())
    freeze = json.loads((ROOT.parent/'protocol/freeze.json').read_text())
    runtime = json.loads((ROOT/'protocol/runtime.json').read_text())
    bundle = ROOT.parent/'.local/common/bundle'
    if campaign['status'] != 'all_contexts_exported_not_physical_execution_proof' or not footprints['all_pass']:
        raise ValueError('export/allocation gates incomplete')
    expected_names={'vector','vocoder'} | {f'{c}-t{t}' for t in campaign['native_text_extents'] for c in ('duration','text')}
    if len(expected_names)!=32 or {x['name'] for x in campaign['components']}!=expected_names or len(campaign['components'])!=32:
        raise ValueError('case-specific context inventory mismatch')
    if sha(ROOT.parent/'protocol/freeze.json') != campaign['freeze_sha256']:
        raise ValueError('freeze changed')
    for name, expected in freeze['bundle_files_sha256'].items():
        if sha(bundle/name) != expected:
            raise ValueError('shared input changed')
    for line in (ROOT/'.local/bin/build.sha256').read_text().splitlines():
        expected, path = line.split(None, 1)
        if sha(Path(path)) != expected:
            raise ValueError('runner build/source changed')
    args.output.mkdir(parents=True, exist_ok=False)
    def copy(source, relative, pin=None):
        if pin and (sha(source) != pin['sha256'] or source.stat().st_size != pin['bytes']):
            raise ValueError('source pin changed: '+source.name)
        dest = args.output/relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        if sha(source) != sha(dest):
            raise ValueError('copy changed bytes')
    copy(ROOT/'.local/bin/runner', 'runner')
    copy(ROOT/'phone/run_remote.sh', 'run_remote.sh')
    for name, pin in runtime['libraries'].items():
        copy(REPO/runtime['library_source_directory']/name, 'lib/'+name, pin)
    by_name = {x['component']: x for x in footprints['components']}
    for item in campaign['components']:
        path = Path(item['compile_result'])
        if sha(path) != item['compile_result_sha256']:
            raise ValueError('export receipt changed')
        result = json.loads(path.read_text())
        if result['session_Run_calls'] != 0 or result['profiling_enabled'] or result['session_config']['session.disable_cpu_ep_fallback'] != '1':
            raise ValueError('not the fail-closed zero-Run export')
        binary = result['component']+'-context_qnn.bin'
        if by_name[item['name']]['context_binary'] != result['artifacts'][binary]:
            raise ValueError('allocation audit bound to different binary')
        for filename, pin in result['artifacts'].items():
            copy(path.parent/filename, 'contexts/'+item['name']+'/'+filename, pin)
    names = ['runner-config.txt', 'style_dp.f32', 'style_ttl.f32', 'noise_stream.f32', 'current_steps.f32', 'total_steps.f32']
    for i in range(15):
        names += [f'{i:03d}/text_ids.i64', f'{i:03d}/text_mask.f32']
    for name in names:
        copy(bundle/name, 'bundle/'+name)
    files = {str(p.relative_to(args.output)): dict(bytes=p.stat().st_size, sha256=sha(p))
             for p in sorted(args.output.rglob('*')) if p.is_file()}
    provenance = dict(context_count=32, case_specific_exactT_pack=True, generic_app_ready_pack=False,
        frozen_bundle_manifest_sha256=freeze['bundle_manifest_sha256'], source_ONNX_staged=False,
        cpu_durations_or_features_staged=False, raw_text_staged=False, profiling_enabled=False,
        cpu_fallback_disabled=True, native_edge_indices='generated_on_device_from_own_HTP_nativeL',
        session_lifecycle='two_shared_heavy_sessions_plus_current_exactT_pair_cache_capacity1',
        strict_source_numerical_gate='failed_preserved_not_relabelled',
        campaign_sha256=sha(args.campaign), footprints_sha256=sha(args.footprints),
        files=files, payload_bytes=sum(v['bytes'] for v in files.values()))
    (args.output/'stage-provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    with (args.output/'stage-manifest.sha256').open('x') as f:
        for path in sorted(args.output.rglob('*')):
            if path.is_file() and path.name != 'stage-manifest.sha256':
                f.write(sha(path)+'  '+str(path.relative_to(args.output))+'\n')
    print(json.dumps(dict(payload_bytes=provenance['payload_bytes'], context_count=32,
                         manifest_sha256=sha(args.output/'stage-manifest.sha256')), indent=2))


if __name__ == '__main__':
    main()

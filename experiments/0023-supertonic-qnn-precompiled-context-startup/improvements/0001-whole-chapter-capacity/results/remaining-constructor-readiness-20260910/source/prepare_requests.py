#!/usr/bin/env python3
"""Prepare three NOT_APPROVED requests using saved ABI evidence and file hashes only."""
import copy
import hashlib
import json
from pathlib import Path
import types

ROOT=Path(__file__).resolve().parents[3]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')


def main():
    base_path=ROOT/'protocol/next-constructor-request-disk-scratch.json'
    assert sha(base_path)=='aeee2b8a2e4c1306de6cf3ed84b9364e954347ea077588808630bb0cc842fa19'
    base=json.loads(base_path.read_text())
    worker_path=ROOT/'tools/compile_component_context.py';launcher_path=ROOT/'tools/run_component_constructor.py'
    worker=types.ModuleType('component_worker');worker.__file__=str(worker_path)
    exec(compile(worker_path.read_bytes(),str(worker_path),'exec'),worker.__dict__)
    artifacts={v['component']:v for v in json.loads((ROOT/'results/materialization-20260910/local-artifacts.json').read_text())}
    batch={'status':'NOT_APPROVED_NO_REMAINING_CONSTRUCTORS_EXECUTED','execution_order':['text','vector','vocoder'],'serial':True,'one_constructor_each':True,'Session_Run_calls_allowed':0,'stop_on_first_failure':True,'automatic_retry':False,'worker_sha256':sha(worker_path),'launcher_sha256':sha(launcher_path),'request_derivation_base_sha256':sha(base_path),'requests':[]}
    for component in batch['execution_order']:
        request=copy.deepcopy(base);inputs,outputs=worker.SPECS[component]
        artifact=artifacts[component];source=Path(artifact['path'])
        # Streaming hash only; no ONNX/model deserialization or runtime import.
        assert source.stat().st_size==artifact['bytes'] and sha(source)==artifact['sha256']
        metadata_path=ROOT/f'results/host-preparation-20260910/raw/inspect-{component}-01/data/metadata.json'
        delta_path=ROOT/f'results/materialization-20260910/raw/{component}/data/structural-delta.json'
        metadata=json.loads(metadata_path.read_text());delta=json.loads(delta_path.read_text())
        for direction,expected in [('input',inputs),('output',outputs)]:
            assert [v['name'] for v in expected]==[v['name'] for v in metadata[direction+'s']]
            assert [v['type'] for v in expected]==[('tensor(int64)' if v['dtype']==7 else 'tensor(float)' if v['dtype']==1 else None) for v in metadata[direction+'s']]
            assert {v['name']:v['shape'] for v in expected}==delta[direction+'_shapes']
        phase=ROOT/f'.local/constructor-{component}-t2048-l2048-attempt-01'
        approval=ROOT/f'.local/approvals/{component}-context.json'
        assert not phase.exists() and not approval.exists()
        request.update(component=component,source={k:artifact[k] for k in ('path','bytes','sha256')},expected_inputs=inputs,expected_outputs=outputs,
            io_sha256=worker.io_sha256(component),phase_dir=str(phase),output_dir=str(phase/'data'),approval_path=str(approval),
            container_name=f'supertonic-chapter-{component}-context-attempt-01',worker_sha256=sha(worker_path),launcher_sha256=sha(launcher_path))
        for name in ('TMPDIR','QAIRT_TMP_DIR','TMP','TEMP'):request['environment'][name]=str(phase/'scratch')
        request_path=ROOT/f'protocol/remaining-constructors/{component}.request.NOT_APPROVED.json'
        write(request_path,request)
        release={'approved':False,'permission':f'one_{component}_EPContext_constructor_no_Run','request_sha256':sha(request_path),'worker_sha256':sha(worker_path),'output_dir':str(phase/'data')}
        release_path=ROOT/f'protocol/remaining-constructors/{component}.release.NOT_APPROVED.json';write(release_path,release)
        batch['requests'].append({'component':component,'path':str(request_path.relative_to(ROOT)),'sha256':sha(request_path),'release_template':str(release_path.relative_to(ROOT)),
            'graph_sha256':artifact['sha256'],'graph_bytes':artifact['bytes'],'io_sha256':request['io_sha256'],
            'metadata_path':str(metadata_path.relative_to(ROOT)),'metadata_sha256':sha(metadata_path),'delta_path':str(delta_path.relative_to(ROOT)),'delta_sha256':sha(delta_path)})
    batch['io_hash_format']='SHA256 of UTF-8 json.dumps({inputs:ordered rows,outputs:ordered rows},sort_keys=True,separators=(comma,colon)); no trailing newline'
    batch['runtime_or_model_imports']=0;batch['model_deserializations']=0;batch['SDK_calls']=0
    write(ROOT/'protocol/remaining-constructors/batch.NOT_APPROVED.json',batch)
    print(json.dumps(batch,indent=2))


if __name__=='__main__':main()

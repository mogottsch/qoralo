#!/usr/bin/env python3
"""Data-only reference-layout export; no copy, model load, SDK or subprocess calls."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DEST=Path(__file__).resolve().parent
SOURCES={
    'duration':('duration-context-constructor-20260910-attempt-01','5c2e413'),
    'text':('remaining-context-constructors-20260910-attempt-01/text','b652a2c'),
    'vector':('remaining-context-constructors-20260910-attempt-01/vector','b652a2c'),
    'vocoder':('vocoder-parity-constructor-20260910-attempt-01','5d9cf99'),
}


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    components={};files=[];requests=[]
    for component,(relative,commit) in SOURCES.items():
        evidence=ROOT/'results'/relative;request_path=evidence/'request.json';request=json.loads(request_path.read_text());requests.append(request)
        result=json.loads((evidence/'raw/data/result.json').read_text());assert result['python_InferenceSession_calls']==1 and result['Session_Run_calls']==0
        descriptor=Path(result['session_config']['ep.context_file_path']);binary=descriptor.parent/result['external_context']['external_binary']
        assert descriptor.name==component+'-context.onnx' and binary.name==component+'-context_qnn.bin'
        assert '/' not in result['external_context']['external_binary']
        entries=[]
        for role,path,record in [('descriptor',descriptor,result['external_context']['descriptor']),('companion_binary',binary,result['external_context']['binary'])]:
            assert path.is_file() and not path.is_symlink() and path.stat().st_size==record['bytes'] and sha(path)==record['sha256']
            entry={'component':component,'role':role,'source_path':str(path),'layout_path':'contexts/'+path.name,**record,'LOCAL_ONLY':True,'preserve_bytes_exactly':True};entries.append(entry);files.append(entry)
        components[component]={'actual_inputs':result['actual_inputs'],'actual_outputs':result['actual_outputs'],'source_graph':request['source'],'constructor_request_sha256':sha(request_path),'evidence_directory':str(evidence.relative_to(ROOT)),'evidence_commit':commit,'descriptor_external_binary_basename':binary.name,'descriptor_rebinding_required':False,'files':entries}
    for request in requests:
        assert request['runtime_pins']==requests[0]['runtime_pins'];assert request['provider_options']==requests[0]['provider_options']
        assert request['ort_version']=='1.27.1' and request['qairt_version']=='2.49.0.260730'
    manifest={'schema':'supertonic-context-reference-layout-v1','namespace':'supertonic-3-t2048-l2048-parity','owner_scope':'Ben: eight context-file byte identities, relative layout and source/ABI/compile provenance ONLY. Janek: final app-pack/schema2 manifest/debug trust and five reused companion asset bindings.',
              'export_kind':'reference_layout_no_duplicate_pack_build','layout_only_not_app_pack_or_trust_authority':True,'context_file_count':8,'total_context_file_bytes':sum(v['bytes'] for v in files),'descriptor_bytes_changed':False,'new_context_or_model_calls':0,
              'components':components,'files':files,
              'required_host_compile_runtime':{'ORT':'1.27.1','QAIRT':'2.49.0.260730','SDK_build':'v2.49.0.260730134355','soc_model':'43','target':'SM8550/HTPv73','provider_options':requests[0]['provider_options'],'session_disable_cpu_ep_fallback':'1','ep_context_embed_mode':'0','selected_host_runtime_pins':requests[0]['runtime_pins'],'scope_note':'These are host compile provenance pins, not Android library files to add to the pack. Keep accepted native9/executables unchanged.'},
              'model_provenance':{'official_revision':'724fb5abbf5502583fb520898d45929e62f02c0b','license':'OpenRAIL-M','public_shapes':'T2048/L2048;144latent channels; waveform cap6291456samples@44100Hz','original_materialization':'results/materialization-20260910/','vector_positional_change':'Exactly INT64 arange1000->2048, original1000prefix/theta/all learned bytes preserved; same seven-node stable Softplus identity. Padding/position extension are not quality-neutral.','vocoder_change':'Onlyconvnext.1/.4 dilation2/kernel7/group512 replaced bytwo batch1 d1/k7 branches after original causalEDGE Pad(12,0), originalsharedW/bias, exactfeature-timeinterleave;103originalinitializer bytes unchanged +7nonlearnedINT64controls.','vocoder_source_materialization':'results/vocoder-parity-materialization-20260910-attempt-01/','vocoder_source_commit':'83eb55e','synthetic_design_commit':'49281cb'},
              'preserved_app_contract':{'voice':'M1','SID':5,'steps':5,'speed':1.0,'normalization':'existing app English tags/NFKD','randomness':'chapter StableSeed +xorshift64*/Box-Muller; retain prepared arrays/masks/noise for comparisons','logical_render':'duration1/text1/vector5/vocoder1 ->one naturally trimmed complete WAV; no text/audio chunks, stitching or fallback','canonical_239_238_pack':'unchanged'},
              'companion_assets_not_in_eight_file_export':['config','tokenizer','unicode-indexer.i32','voice.bin','voice-style.json'],'companion_policy':'Janek reuses exact five accepted companion bytes and pins them in the final new pack/trust contract; no modification of accepted/current packs.',
              'evidence_boundary':'Four reviewed constructor/export pairs; no reload, model forward, phone or long-speech/fidelity/listening acceptance. Preserve four nonfatal StridedSlice tiler warnings; they do not block preparation or justify changing/recompiling these artifacts.','deployment_or_execution_authorized':False,'push_held':True}
    with (DEST/'context-export.json').open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
    with (DEST/'CONTEXT_SHA256SUMS').open('x') as f:f.write(''.join(v['sha256']+'  '+v['layout_path']+'\n' for v in files))
    print(json.dumps({'manifest':str(DEST/'context-export.json'),'sha256':sha(DEST/'context-export.json'),'files':len(files),'total_bytes':manifest['total_context_file_bytes'],'descriptor_rebinding_required':False,'model_or_SDK_calls':0},indent=2))


if __name__=='__main__':main()

from pathlib import Path
import json,sys,copy
track=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality');launch=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/paired-allocation-observer/stage-01-launch');sys.path.insert(0,str(track/'tools'))
from prepare_frozen_genie_stage import copy_bound,write_input,verify,sha256
base=track/'.local/frozen-stages/paired-prefill-capture-stage-01';stage=track/'.local/frozen-stages/paired-allocation-observer-stage-01';source=json.loads((base/'frozen-manifest.json').read_text());build=json.loads((track/'.local/paired-allocation-observer/build-01/build-result.json').read_text());stage.mkdir(mode=0o700);files={}
for name,identity in source['files'].items():
 if name=='lib/libGenie.so':files[name]=copy_bound(Path(build['binary']),stage/name,{'sha256':build['binary_sha256'],'bytes':build['binary_bytes']})
 else:files[name]=copy_bound(base/name,stage/name,identity)
manifest=copy.deepcopy(source);manifest.update(classification='frozen_allocation_stage_observation',stage_id=stage.name,files=files,payload_bytes=sum(x['bytes'] for x in files.values()),phone_authorized=False,model_loaded=False,runtime_loaded=False)
manifest['allocation_observer']={'build':build,'fixed_stack_no_heap_logging':True,'errno_label':'errno-at-observation, not proof malloc set it','requested_size_arithmetic':'overflow checked diagnostically; original expressions unchanged','log_max_bytes':65536,'log_max_events':64,'model_AS_cap_token_cap_and_call_order_changed':False}
manifest['capture_build']=build;manifest['trace_runtime']['libGenie_sha256']=build['binary_sha256'];manifest['copy_policy']='Only observer library changes from paired-prefill stage. Model/LUT/config/script/cap1 unchanged.'
write_input(stage/'frozen-manifest.json',(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode());h=sha256(stage/'frozen-manifest.json');write_input(stage/'SHA256SUMS',(''.join(f'{v["sha256"]}  {k}\n' for k,v in sorted(files.items()))+f'{h}  frozen-manifest.json\n').encode());verify(stage,h)
result={'stage':str(stage),'manifest_sha256':h,'files':len(files),'bytes':manifest['payload_bytes'],'only_payload_change':'lib/libGenie.so','model_or_phone_executed':False};(launch/'stage-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

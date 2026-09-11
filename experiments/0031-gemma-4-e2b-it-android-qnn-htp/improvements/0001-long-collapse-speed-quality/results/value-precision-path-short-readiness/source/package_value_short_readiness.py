import hashlib,importlib,json,os,shutil,subprocess,sys
from pathlib import Path
os.umask(0o077); os.nice(15)
t=Path(__file__).resolve().parents[1]; exp=t.parents[1]; repo=exp.parents[1]
sys.path.insert(0,str(t/'tools')); a=importlib.import_module('phone_value_precision_short')
r=t/'results/value-precision-path-short-readiness'; r.mkdir(parents=True,exist_ok=False)
def save(name,data):
 p=r/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2)+'\n')
def copy(src,dest):
 p=r/dest;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,p)
prep=t/'.local/stage-preparation-runs/value-stage-20260911T115043Z-01'
stage=t/'.local/frozen-stages'/a.STAGE_NAME
for p in sorted(prep.rglob('*')):
 if p.is_file():copy(p,'preparation/'+str(p.relative_to(prep)))
for name in ['frozen-manifest.json','SHA256SUMS','first-short.script','gemma4-e2b-htp-cl4096-greedy.json']:
 copy(stage/name,'stage/'+name)
for name in ['prepare_value_precision_stage.py','phone_value_precision_short.py','phone_return_controller.py','phone_return_shell.py','phone_return_long.py','prepare_frozen_genie_stage.py']:
 copy(t/'tools'/name,'source/'+name)
copy(Path(__file__),'source/package_value_short_readiness.py')
for name in ['test_phone_value_precision_short.py','test_value_precision_stage.py','test_phone_return_controller.py']:
 copy(exp/'tests'/name,'source/tests/'+name)
c,s,changes,_=a.materialize_sources()
(r/'materialized-controller.py').write_text(c);(r/'materialized-shell.py').write_text(s)
_,receipt=a.load_lifecycle();save('scope-receipt.json',receipt)
commands=[('plan',['python3','-B',str(t/'tools/phone_value_precision_short.py')],repo),
 ('workload-check',['sha256sum','-c','SHA256SUMS'],repo/'protocols/android-llm-benchmark/workloads/inference-v1'),
 ('tests',['python3','-B','-m','unittest','discover','-s',str(exp/'tests'),'-v'],repo)]
for name,cmd,cwd in commands:
 result=subprocess.run(cmd,cwd=cwd,capture_output=True,timeout=120)
 (r/(name+'.stdout')).write_bytes(result.stdout);(r/(name+'.stderr')).write_bytes(result.stderr)
 save(name+'-execution.json',{'argv':cmd,'cwd':str(cwd),'exit_code':result.returncode,'actual_child_exit_saved':True,'adb':False})
 if result.returncode:raise RuntimeError(f'{name} failed; saved first outcome')
manifest=json.loads((stage/'frozen-manifest.json').read_text())
assert hashlib.sha256((stage/'frozen-manifest.json').read_bytes()).hexdigest()==a.STAGE_DIGEST
assert manifest['context_sha256']==a.CONTEXT_SHA
assert hashlib.sha256((t/'tools/prepare_value_precision_stage.py').read_bytes()).hexdigest()==(prep/'source.sha256').read_text().strip()
save('result.json',{'classification':'host_frozen_stage_and_guarded_short_readiness_only',
 'stage':str(stage),'stage_manifest_sha256':a.STAGE_DIGEST,'context_sha256':a.CONTEXT_SHA,
 'context_result_sha256':a.CONTEXT_RESULT_SHA,'payload_bytes':manifest['payload_bytes'],
 'payload_files':len(manifest['files']),'preparation_verified':json.loads((prep/'prepared/result.json').read_text())['verified'],
 'preparation_unit_exit_code':None,'preparation_exit_limitation':'Verified stage receipt saved; independent service exit receipt not captured before unit collection. Watcher exit is not service exit proof.',
 'scope_receipt':receipt,'inference_performed':False,'adb_used':False,'phone_slot_granted':False,
 'canonical_campaign_unchanged':True,'prior_exact_long_negative_unchanged':True,
 'registry_eligible':False,'physical_output_sanity':{'looks_sensible':None,'issue_notes':None}})
print(r)

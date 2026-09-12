from pathlib import Path
import sys,json,subprocess,hashlib,shutil
track=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality');root=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/matched-prefill-reference/verification-01');sys.path.insert(0,str(track/'tools'))
import declared_dlc_reference as r
import matched_prefill_inputs as inputs
import numpy,scipy
p=track/'.local/matched-prefill-reference/policy-01/policy.json';ref=r.DeclaredDlcReference(p);statics=ref.verify_static_bindings();memory=r.memory_plan(ref.policy)
ledger_path=track/'.local/matched-prefill-reference/inputs-01/ledger.json';ledger=json.loads(ledger_path.read_text());count=0
for record in list(ledger['initial_caches'].values())+[v for step in ledger['chunks'] for v in step['input_files'].values()]:
 assert inputs.sha(ledger_path.parent/record['file'])==record['sha256'];count+=1
float_mm=[o for o in ref.policy['operators'] if o['type']=='MatMul' and all(ref.policy['tensors'][n]['datatype']=='Float_16' for n in o['inputs']+o['outputs'])]
assert len(float_mm)==56
with (root/'tests.stdout').open('wb') as so,(root/'tests.stderr').open('wb') as se:
 cmd=[sys.executable,'-B','-m','unittest','discover','-s',str(track.parents[1]/'tests'),'-p','test_matched_prefill_reference.py','-v'];test=subprocess.run(cmd,stdout=so,stderr=se,timeout=90)
assert test.returncode==0,(root/'tests.stderr').read_text()
# Repeat the tiny header compile/run under explicit resource caps. Prior tiny
# preliminary receipt stays retained; no model or phone is involved.
old=track/'.local/paired-prefill-capture/header-test-01';shutil.copyfile(old/'test.cpp',root/'header-test.cpp');(root/'capture').mkdir()
inc=track/'.local/paired-prefill-capture/build-01/sdk-source/examples/Genie/Genie/src/qualla/include'
cmd=['g++','-std=c++20','-O0','-pthread','-I'+str(track/'tools'),'-I'+str(inc),str(root/'header-test.cpp'),'-o',str(root/'header-test')]
compiled=subprocess.run(cmd,capture_output=True,timeout=60);(root/'compile.stderr').write_bytes(compiled.stderr);assert compiled.returncode==0
ran=subprocess.run([str(root/'header-test'),str(root/'capture')],capture_output=True,timeout=10);(root/'header.stderr').write_bytes(ran.stderr);assert ran.returncode==0
result={'policy_preflight':ref.preflight,'private_static_blobs_verified':statics,'prepared_input_cache_files_verified':count,'float16_MatMuls':len(float_mm),'memory_plan':memory,'numpy_version':numpy.__version__,'scipy_version':scipy.__version__,'synthetic_test_exit':test.returncode,'header_compile_exit':compiled.returncode,'header_test_exit':ran.returncode,'full_model_forwards':0,'ADB_calls':0,'policy_sha256':inputs.sha(p),'ledger_sha256':inputs.sha(ledger_path)}
(root/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

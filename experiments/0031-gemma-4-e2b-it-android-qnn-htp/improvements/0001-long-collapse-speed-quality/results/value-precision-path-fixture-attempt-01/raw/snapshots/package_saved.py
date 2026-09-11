#!/usr/bin/env python3
"""Package completed tiny/source fixtures only; never copy SDK/model binaries."""
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

os.umask(0o077)
ROOT = Path(__file__).resolve().parent
TRACK = ROOT.parents[2]
DEST = TRACK/'results/value-precision-path-fixture-attempt-01'
DEST.mkdir(parents=True, exist_ok=False)
IDENTITIES = []


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def retain(p, relative, compressed=False):
    content = p.read_bytes()
    dest = DEST/relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(gzip.compress(content, mtime=0) if compressed else content)
    IDENTITIES.append({'source': str(p), 'source_bytes': len(content), 'source_sha256': sha(p),
                       'retained': relative, 'lossless_gzip': compressed})


cases = []
for name, sub in [('ar128-control-01','fixture'), ('ar128-candidate-01','fixture'), ('ar1-candidate-01','fixture'),
                  ('derivative-ar128-control-01','converted'), ('derivative-ar128-candidate-01','converted'),
                  ('derivative-ar1-candidate-01','converted'), ('compile-ar128-candidate-01','compiled')]:
    run = ROOT/name
    result = json.loads((run/sub/'result.json').read_text())
    assert result['classification'].endswith('passed'), (name, result)
    for f in sorted(run.iterdir()):
        if f.is_file():
            retain(f, f'raw/{name}/{f.name}')
    for f in sorted((run/sub).iterdir()):
        if f.suffix in ('.dlc', '.onnx', '.bin'):
            continue
        if f.is_file():
            compress = f.name.endswith(('.csv','.stdout'))
            retain(f, f'raw/{name}/{sub}/{f.name}' + ('.gz' if compress else ''), compress)
    unit = 'gemma-value-fixture-20260911t101059z-' + name
    state = subprocess.run(['systemctl','--user','show',unit+'.service','-p','ActiveState','-p','SubState',
                            '-p','MainPID','-p','Result','-p','ExecMainStatus'],capture_output=True,text=True)
    assert 'MainPID=0' in state.stdout and 'Result=success' in state.stdout, (unit, state.stdout, state.stderr)
    (DEST/f'raw/{name}/final-unit.txt').write_text(state.stdout)
    cases.append({'name': name, 'result_path': f'raw/{name}/{sub}/result.json',
                  'result_sha256': sha(run/sub/'result.json'), 'classification': result['classification'],
                  'ar': result.get('ar',128), 'candidate': result.get('candidate',True),
                  'elapsed_seconds': result['elapsed_seconds'], 'dlc': result.get('dlc'),
                  'context': result.get('context'), 'parent_ru_maxrss_kib': result.get('parent_ru_maxrss_kib',result.get('ru_maxrss_kib')),
                  'memory_limit_bytes': 2*1024**3, 'swap_limit_bytes': 1024**3, 'cpu_quota': '100%',
                  'max_elapsed_seconds': 240, 'unit_result': 'success', 'main_pid_after': 0,
                  'memory_limitation': 'First authored fixture runner did not instrument RSS; transient unit peak unavailable after completion.'
                    if 'parent_ru_maxrss_kib' not in result and 'ru_maxrss_kib' not in result else None})

for ar in (1,128):
    p=ROOT/f'source-ar{ar}-01'
    for name in ('preparation.json','control.encodings','candidate.encodings'):
        retain(p/name,f'raw/source-ar{ar}/{name}')
    for suffix in ('stdout','stderr'):
        retain(ROOT/f'source-ar{ar}-01.{suffix}',f'raw/source-ar{ar}/preparation.{suffix}')

for f in ROOT.glob('launch-*.sh'):
    if f.name != 'launch-full.sh':
        retain(f, 'raw/snapshots/'+f.name)
for n in ('value_precision_path-fixture-snapshot.py','probe-fixture-snapshot.py'):
    retain(ROOT/n,'raw/snapshots/'+n)
for n in ('prepare_value_precision_derivative.py','convert_value_precision_derivative.py','compile_value_precision_fixture.py','value_precision_path.py'):
    retain(TRACK/'tools'/n,'raw/snapshots/'+n)
helper=(TRACK/'tools/value_precision_path.py').read_text().split('\n\ndef full_dlc_gate')[0].rstrip()+'\n'
assert hashlib.sha256(helper.encode()).hexdigest() == '01dd3fdfa298ee13bd59a013c71ab8ebfcd26b52a69ab143626b7d6131cea826'
(DEST/'raw/snapshots/value_precision_path-source-derivative-snapshot.py').write_text(helper)

spec=importlib.util.spec_from_file_location('path_gate',TRACK/'tools/value_precision_path.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
old_rejections=[]
for ar, old_csv in ((1,TRACK/'results/global-value-fp16-attempt-05/raw/inspection-02/ar1.csv.gz'),
                    (128,TRACK/'results/global-value-fp16-attempt-06/raw/inspection-01/ar128.csv.gz')):
    graph=g.parse_dlc_csv(old_csv)
    plan=json.loads((ROOT/f'source-ar{ar}-01/preparation.json').read_text())['all_layers']
    result=g.full_dlc_gate(graph,graph,plan)
    assert not result['passed']
    old_rejections.append({'ar':ar,'old_csv_path':str(old_csv),'old_csv_gzip_sha256':sha(old_csv),
                           'passed':result['passed'],'issues':result['issues'],
                           'scope':'metadata counterexample only; no replay or replacement of accepted GateB'})
(DEST/'raw/old-candidate-gate-counterexamples.json').write_text(json.dumps(old_rejections,indent=2)+'\n')

sdk=Path('/home/moritz/opt/qairt/2.49.40.260810')
sources=[]
for path, location in [('docs/QAIRT-Docs/QNN/OpDef/HtpOpDefSupplement.html','MatMul/Concat/RmsNorm sections'),
                       ('docs/QAIRT-Docs/QNN/general/quantization.html','Mixed Precision and FP16 Support'),
                       ('lib/python/qti/aisw/converters/common/backend_aware_configs/htp.json','op_type MatMul/Concat/RmsNorm floating kernels'),
                       ('lib/python/qti/aisw/converters/common/utils/convert_encodings.py','v1-to-v2 FLOAT discard branch'),
                       ('lib/python/qti/aisw/converters/common/converter_ir/op_graph.py','v1.0.0 processing; use_quantize_v2 boundary')]:
    p=sdk/path;sources.append({'path':str(p),'sha256':sha(p),'location':location,'sdk_content_copied':False})
result={'classification':'positive_small_fixture_and_exact_source_island_dlc_plus_sm8550_compile',
        'scope':'Preparation milestone of NEW precision-path assignment, not completion of full candidate or replacement of prior work',
        'cases':cases,'source_basis':sources,'retention':IDENTITIES,
        'source_derivative_helper_snapshot':'Reconstructed exact bytes from current file prefix, then verified against all three original run-recorded SHA256 identities.',
        'findings':['Explicit v1 FLOAT16 activation encodings remove tested post-normalization requantization.',
                    'Both MatMul operands and output are Float16; quantized probability is converted at boundary.',
                    'Exact source layer4/first-head derivative retains CL4096,width512 and AR1/128 geometry.',
                    'Small source AR128 graph compiles for SM8550/v73; no physical or numerical execution was performed.',
                    'Full source plan spans56 value MatMuls and71AR1/74AR128 activation encoding targets.'],
        'limitations':['Full Gemma DLC precision gate has not yet passed.','Compiled internal kernel arithmetic/rounding is not proved by context creation.',
                       'No performance, fidelity, repetition-cause or model-family quality verdict.',
                       'Upstream V-projection and probability computation remain quantized; this is a post-projection island.',
                       'No runtime route was executed. No phone use, app changes, Nik review, model-output repair or public binary distribution.'],
        'prior_exact_long_negative_unchanged':True,'full_model_conversion':'separate run in progress; not included in this milestone',
        'inference':False,'phone_access':False,'registry_update':False}
(DEST/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(DEST)

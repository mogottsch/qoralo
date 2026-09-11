#!/usr/bin/env python3
"""Package already-pulled device data and compare saved arrays; no ADB/SDK/model calls."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import numpy as np

OUT=Path(__file__).resolve().parent
EXP=OUT.parents[1]
BASE=EXP/'.local/k-cache-v73-20260911'
HOST=EXP/'.local/k-cache-boundary-probe-20260911/attempt-01'


def pin(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while b:=f.read(1024*1024):h.update(b)
    return {'path':str(p),'bytes':p.stat().st_size,'sha256':h.hexdigest()}


def save(name,data):
    with (OUT/name).open('x') as f:json.dump(data,f,indent=2,allow_nan=False);f.write('\n')


def metrics(a,b):
    d=np.abs(a.astype('f8')-b.astype('f8'))
    return {'bitwise_equal_values':int((a.view('u4')==b.view('u4')).sum()),'max_abs_fp64':float(d.max()),'mean_abs_fp64':float(d.mean())}


def main():
    device=BASE/'attempt-02/device';out=device/'out';bind=json.loads((BASE/'attempt-02/binding.json').read_text())
    assert (out/'exit-code.txt').read_text().strip()=='0'
    expected=''.join(x['remote_name']+': OK\n' for x in bind['files'])
    assert (out/'pre-run-hashes.txt').read_text()==expected and (out/'post-run-hashes.txt').read_text()==expected
    assert json.loads((device/'cleanup.json').read_text())['remote_absent']
    retained=[]
    for attempt in ('attempt-01','attempt-02'):
        for p in sorted((BASE/attempt).rglob('*')):
            if not p.is_file() or p.name=='PRESERVE.md':continue
            relative=p.relative_to(BASE)
            if p.suffix=='.raw':
                dest=OUT/'arrays'/Path(str(relative)+'.zst');dest.parent.mkdir(parents=True,exist_ok=True)
                with dest.open('xb') as f:subprocess.run(['zstd','-q','-3','-c',str(p)],stdout=f,check=True,timeout=20)
                raw=subprocess.run(['zstd','-q','-dc',str(dest)],stdout=subprocess.PIPE,check=True,timeout=20).stdout
                record=pin(p);assert len(raw)==record['bytes'] and hashlib.sha256(raw).hexdigest()==record['sha256']
                retained.append({'raw':record,'compressed':pin(dest),'full_recovery_verified':True})
            else:
                dest=OUT/'raw'/relative;dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists();shutil.copy2(p,dest)
    shutil.copy2(EXP/'tools/run_k_cache_v73.py',OUT/'controller-at-run02.py')
    comparisons=[]
    for i,state in enumerate((3,15)):
        p=out/f'output_0_{i}.raw';host=HOST/f'runtime/data/output-{i}.raw'
        a=np.fromfile(p,dtype='<f4').reshape(1,2,256,4096);h=np.fromfile(host,dtype='<f4').reshape(a.shape)
        assert a.tobytes()==h.tobytes()
        old=np.fromfile(HOST/f'prepare/cache{state}.f32le',dtype='<f4').reshape(1,2,256,4095)
        key=np.fromfile(HOST/f'prepare/key{state}.f32le',dtype='<f4').reshape(1,2,256,1)
        plain=np.concatenate((old,key),axis=-1)
        full=np.fromfile(HOST/f'prepare/fullchain-{i}.f32le',dtype='<f4').reshape(a.shape)
        alt=np.fromfile(HOST/f'prepare/catonly_hypothesis-{i}.f32le',dtype='<f4').reshape(a.shape)
        ix=(0,1,24,0)
        comparisons.append({'state':state,'shape':list(a.shape),'device_output':pin(p),'host_output':pin(host),'host_byte_identical':True,'finite_values':int(np.isfinite(a).sum()),'nonzero_values':int(np.count_nonzero(a)),
            'versus_fullchain':metrics(a,full),'versus_catonly_hypothesis':metrics(a,alt),'versus_plain_float_concat':metrics(a,plain),
            'anchor':{'actual':float(a[ix]),'host':float(h[ix]),'fullchain':float(full[ix]),'catonly_hypothesis':float(alt[ix]),'plain_float_concat':float(plain[ix])},
            'plain_float_reference_scope':'saved-array concatenation only; no unquantized full-model/attention forward'})
    log=out/'runner.stderr.log';lines=log.read_text().splitlines()
    keys=['RouterFastRPC create','libQnnHtpV73Stub.so using absolute','DSP ARCH graph is set to 73','Perform 0 inference','Start inference (0)','QnnGraph_execute started','transport execute dmahandles [status = 0]','QnnGraph_execute done. status 0x0','Total 1 inference','QnnContext_free done successfully','profile_level: kProfileOff']
    passages=[{'line':i+1,'text':s} for i,s in enumerate(lines) if any(k in s for k in keys)]
    assert sum('QnnGraph_execute started.' in s for s in lines)==1
    assert sum('QnnGraph_execute done. status 0x0' in s for s in lines)==1
    assert all(any(k in s for s in lines) for k in keys)
    intervals=re.findall(r'Total 1 inference took ([0-9.]+) ms',log.read_text());assert len(intervals)==1
    save('comparison.json',{'comparisons':comparisons,'new_model_SDK_ADB_calls':0})
    save('device-execution-evidence.json',{'log':pin(log),'passages':passages,'physical_route':'SM-S918B / SM8550 / ARM64 Android, QnnDsp HtpProvider RouterFastRPC V73Stub, DSP graph73','successful_graph_calls_observed':1,'new_phone_compile':0,'input_file_checks_pre_and_post':len(bind['files']),'canonical_campaign':False,'RPC_accelerator_cycles':None,'counter_null_reason':'QNN profiling off; retained transport success is execution evidence, not a precise counter/timing split','model_execution_interval_ms_from_driver':float(intervals[0]),'interval_limit':'one synthetic method call only, not a canonical throughput/TTFT/setup metric','peak_device_process_memory':None,'memory_null_reason':'No process peak sampling was captured in this short fixture; SDK memory estimates are not measured peak','internal_finalized_encodings':None})
    save('array-retention.json',{'outputs':retained,'originals_preserved':True})
    save('native-file-bindings.json',{'files':bind['files'],'policy':'native runner/PTE/context/libraries remain LOCAL-ONLY at original binding paths; all actual bytes must migrate'})
    print(json.dumps(comparisons,indent=2))


if __name__=='__main__':main()

#!/usr/bin/env python3
"""Saved grids + authored scalar/QnnCpu edge fixtures. Never replay the model/phone."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import numpy as np

TRACK=Path(__file__).resolve().parents[1]
POLICY=TRACK/'.local/matched-prefill-reference/policy-01/policy.json'
POLICY_SHA='7fffebe9208bc5e2b92d80ed6ed01b7b57263e8f23d188188588682754c18b59'
SDK=Path('/home/moritz/opt/qairt/2.49.40.260810')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def same_grid_zero_check(mean_scale,epsilon):
    words=np.arange(65536,dtype=np.uint16);values=words.astype(np.float32)*np.float32(mean_scale)
    after=np.clip(np.rint((values+np.float32(epsilon))/np.float32(mean_scale)),0,65535).astype(np.uint16)
    return {'all_representable_mean_codes_tested':65536,'codes_changed_by_epsilon':int(np.count_nonzero(words!=after)),'zero_mean_after_add_code':int(after[0]),'epsilon_in_output_grid_steps':float(np.float32(epsilon)/np.float32(mean_scale)),'half_output_grid_step':float(mean_scale)/2}


def audit(out,with_cpu=False):
    from declared_dlc_reference import decode
    if sha(POLICY)!=POLICY_SHA:raise ValueError('frozen policy changed')
    p=json.loads(POLICY.read_text());t=p['tensors'];ops=p['operators'][6291:6297]
    if ops[3]['name']!='node_pow_606':raise ValueError('recorded failure node changed')
    epsilon=t['val_54'];power=t['val_55'];mean=t['mean_445'];add=t['add_27410'];output=t['pow_606']
    def scalar(spec):
        path=POLICY.parent/spec['static']['file']
        if sha(path)!=spec['static']['npy_sha256']:raise ValueError('bound static scalar changed')
        data=np.load(path,mmap_mode='r',allow_pickle=False);return {'raw':data.tolist(),'decoded':float(decode(data,spec).reshape(-1)[0]),'raw_npy_sha256':sha(path)}
    e=scalar(epsilon);exponent=scalar(power)
    if exponent['decoded']!=-.5 or mean['grid']!=add['grid'] or mean['grid']['axis'] is not None or mean['grid']['offset']!=[0]:raise ValueError('unreviewed zero-power chain')
    check=same_grid_zero_check(mean['grid']['scale'][0],e['decoded'])
    with np.errstate(divide='ignore',invalid='raise'):
        ieee=float(np.power(np.float32(0),np.float32(exponent['decoded'])))
    if not np.isposinf(ieee):raise ValueError('IEEE zero-to-negative power not positive infinity')
    hypothetical=int(np.clip(np.float32(np.inf),0,65535))
    result={'classification':'saved_normalization_zero_edge_and_synthetic_operator_audit','model_prefill_replays':0,'phone_calls':0,'reference_implementation_changed':False,'policy_sha256':POLICY_SHA,'recorded_failure':{'chunk':5,'operator_index':6294,'name':'node_pow_606'},'chain':ops,'epsilon':e,'exponent':exponent,'mean_and_add_grid':mean['grid'],'power_output_grid':output['grid'],'same_grid_enumeration':check,'IEEE_portable_zero_power_result':'+Inf (pole), not NaN','hypothetical_positive_infinity_output_saturation_code':hypothetical,'saturation_is_NOT_yet_a_generalized_reference_repair':True,'actual_zero_row_index_or_upstream_values_saved':False,'QNN_compiler_fusion_or_HTP_edge_behavior_established':False,'scope':'Static scalar/grid and synthetic zero case only. CPU backend observations, if obtained, are not HTP equivalence.'}
    out.mkdir(parents=True,exist_ok=False);(out/'static-result.json').write_text(json.dumps(result,indent=2)+'\n')
    if with_cpu:
        cpp=TRACK/'tools/qnn_power_edge_fixture.cpp';binary=out/'qnn-power-edge';library=SDK/'lib/x86_64-linux-clang/libQnnCpu.so'
        cmd=['g++','-std=c++17','-O1','-I'+str(SDK/'include/QNN'),str(cpp),'-ldl','-o',str(binary)];(out/'compile-command.json').write_text(json.dumps(cmd,indent=2)+'\n');r=subprocess.run(cmd,capture_output=True,timeout=40);(out/'compile.stdout').write_bytes(r.stdout);(out/'compile.stderr').write_bytes(r.stderr)
        cpu={'compile_exit':r.returncode,'model_prefill_executed':False,'phone_or_HTP_used':False,'full_scalar_case_count':4,'source_sha256':sha(cpp),'QnnCpu_sha256':sha(library),'headers':{name:sha(SDK/'include/QNN'/name) for name in ['QnnTypes.h','QnnInterface.h','QnnOpDef.h']}}
        if r.returncode==0:
            env={'PATH':'/usr/bin:/bin','HOME':str(out),'TMPDIR':str(out),'LD_LIBRARY_PATH':str(library.parent),'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'}
            command=[str(binary),str(library)];(out/'native-command.json').write_text(json.dumps({'argv':command,'environment':env,'close_fds':True},indent=2)+'\n');r=subprocess.run(command,env=env,capture_output=True,timeout=60,close_fds=True);(out/'native.stdout').write_bytes(r.stdout);(out/'native.stderr').write_bytes(r.stderr);cpu['harness_exit']=r.returncode
            rows=[]
            for line in r.stdout.decode(errors='replace').splitlines():
                if line.startswith('{'):
                    try:rows.append(json.loads(line))
                    except json.JSONDecodeError:pass
            cpu['records']=rows;cpu['successful_graph_executions']=sum(row.get('stage')=='execute' and row.get('status')==0 for row in rows)
        (out/'cpu-result.json').write_text(json.dumps(cpu,indent=2)+'\n');result['CPU_fixture']=cpu
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,required=True);parser.add_argument('--with-cpu',action='store_true');a=parser.parse_args();out=a.output_dir.resolve()
    if not out.is_relative_to(TRACK/'.local/reference-zero-boundary'):parser.error('owned fresh scalar-audit root required')
    audit(out,a.with_cpu)

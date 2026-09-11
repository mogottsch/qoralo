#!/usr/bin/env python3
"""Retain first outcomes and analyze saved raw arrays only; no runtime import."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import numpy as np

OUT=Path(__file__).resolve().parent
EXP=OUT.parents[1]
WORK=EXP/'.local/k-cache-boundary-probe-20260911/attempt-01'


def pin(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while b:=f.read(1024*1024):h.update(b)
    return {'path':str(p),'bytes':p.stat().st_size,'sha256':h.hexdigest()}


def save(n,d):
    with (OUT/n).open('x') as f:json.dump(d,f,indent=2);f.write('\n')


def ordered(a):
    u=a.view('u4').astype('i8')
    return np.where(u<0x80000000,u+0x80000000,0x100000000-u)


def main():
    records=[];local=[]
    for p in sorted(WORK.rglob('*')):
        if not p.is_file() or p.name=='PRESERVE.md':continue
        rel=p.relative_to(WORK)
        if p.suffix in ('.pte','.bin'):
            local.append(pin(p));continue
        if p.suffix in ('.f32le','.raw'):
            dest=OUT/'arrays'/Path(str(rel)+'.zst');dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('xb') as f:subprocess.run(['zstd','-q','-3','-c',str(p)],stdout=f,check=True,timeout=20)
            # Complete byte recovery, not spot checking, before interpretation/publication.
            recovered=subprocess.run(['zstd','-q','-dc',str(dest)],stdout=subprocess.PIPE,check=True,timeout=20).stdout
            original=pin(p);assert len(recovered)==original['bytes'] and hashlib.sha256(recovered).hexdigest()==original['sha256']
            records.append({'original':original,'compressed':pin(dest),'full_recovery_verified':True});continue
        dest=OUT/'raw'/rel;dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists();shutil.copy2(p,dest)
    save('array-retention.json',{'arrays':records,'all_originals_preserved':True})
    save('local-native-artifacts.json',{'artifacts':local,'policy':'LOCAL-ONLY; originals and contexts must migrate; hashes are not replacement bytes'})
    rows=[]
    for i in range(2):
        actual=np.fromfile(WORK/f'runtime/data/output-{i}.raw',dtype='<f4').reshape(1,2,256,4096)
        full=np.fromfile(WORK/f'prepare/fullchain-{i}.f32le',dtype='<f4').reshape(actual.shape)
        alt=np.fromfile(WORK/f'prepare/catonly_hypothesis-{i}.f32le',dtype='<f4').reshape(actual.shape)
        coords=np.argwhere(actual!=0);sites=[]
        for c in coords:
            ix=tuple(c);sites.append({'coordinate':c.tolist(),'actual':float(actual[ix]),'fullchain':float(full[ix]),'catonly_hypothesis':float(alt[ix]),'actual_f32le_hex':actual[ix].tobytes().hex()})
        rows.append({'state_index':(3,15)[i],'nonzero_values':len(sites),'nonzero_sites':sites,
                     'finite_values':int(np.isfinite(actual).sum()),'elements':int(actual.size),
                     'fullchain_bitwise_mismatches':int((actual.view('u4')!=full.view('u4')).sum()),
                     'max_ULP_from_fullchain':int(np.abs(ordered(actual)-ordered(full)).max()),
                     'max_ULP_from_catonly_hypothesis':int(np.abs(ordered(actual)-ordered(alt)).max()),
                     'zero_values':int((actual==0).sum())})
    save('saved-output-analysis.json',{'rows':rows,'analysis_scope':'saved raw arrays only; mostly-zero sparse fixture, not a rich numerical distribution','new_model_or_SDK_calls':0})
    print(json.dumps(rows,indent=2))


if __name__=='__main__':main()

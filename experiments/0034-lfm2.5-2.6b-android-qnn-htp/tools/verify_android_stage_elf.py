#!/usr/bin/env python3
"""Fail locally when a staged Android ELF dependency is neither staged nor system-provided."""
import argparse,re,subprocess
from pathlib import Path
SYSTEM={'libc.so','libm.so','libdl.so','liblog.so','libandroid.so','libcdsprpc.so','libGLESv2.so','libEGL.so'}
DSP_SYSTEM={'libc++.so.1','libc++abi.so.1'}
p=argparse.ArgumentParser();p.add_argument('stage',type=Path);a=p.parse_args()
provided={x.name for x in a.stage.iterdir() if x.is_file()}
elfs=[]
for path in a.stage.iterdir():
    if not path.is_file():continue
    probe=subprocess.run(['readelf','-h',str(path)],capture_output=True,text=True)
    if probe.returncode==0 and 'ELF' in probe.stdout:elfs.append(path)
missing={}
for path in elfs:
    text=subprocess.check_output(['readelf','-d',str(path)],text=True)
    needed=re.findall(r'Shared library: \[([^]]+)\]',text)
    header=subprocess.check_output(['readelf','-h',str(path)],text=True)
    allowed=SYSTEM | (DSP_SYSTEM if ('Hexagon' in header or 'DSP6' in header) else set())
    absent=sorted(x for x in needed if x not in provided and x not in allowed)
    if absent:missing[path.name]=absent
if missing:raise SystemExit(f'unresolved staged DT_NEEDED dependencies: {missing}')
print(f'ELF preflight OK: {len(elfs)} ELF files, {len(provided)} root files')

#!/usr/bin/env python3
import argparse,hashlib,json,secrets,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--cpu',type=Path,required=True);p.add_argument('--htp',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--mapping',type=Path,required=True);a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True);order=['cpu','htp'];secrets.SystemRandom().shuffle(order);src={'cpu':a.cpu,'htp':a.htp};mapping={}
for i,route in enumerate(order):
 label=chr(ord('A')+i);dest=a.output_dir/f'sample-{label.lower()}.wav';shutil.copyfile(src[route],dest);mapping[label]={'route':route,'source':str(src[route].resolve()),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
a.mapping.parent.mkdir(parents=True,exist_ok=True);a.mapping.write_text(json.dumps({'schema_version':1,'mapping':mapping},indent=2,sort_keys=True)+'\n')
html='''<!doctype html><meta charset="utf-8"><title>Blind MOSS comparison</title><style>body{font:18px system-ui;max-width:720px;margin:3rem auto;padding:0 1rem;background:#111;color:#eee}.card{background:#222;padding:1.3rem;margin:1rem 0;border-radius:12px}audio{width:100%}small{color:#aaa}</style><h1>Blind MOSS-TTS-Nano comparison</h1><p>Same frozen text and Junhao voice. Please judge each sample independently for pleasantness, naturalness, intelligibility, accent, and artifacts. The labels do not identify the runtime.</p><div class="card"><h2>Sample A</h2><audio controls preload="metadata" src="sample-a.wav"></audio></div><div class="card"><h2>Sample B</h2><audio controls preload="metadata" src="sample-b.wav"></audio></div><small>Do not inspect filenames or hashes before recording the verdict.</small>'''
(a.output_dir/'index.html').write_text(html)

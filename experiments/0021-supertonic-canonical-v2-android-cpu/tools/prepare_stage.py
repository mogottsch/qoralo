#!/usr/bin/env python3
"""Prepare exact canonical-v2 Supertonic app-internal stage and frontend evidence."""
from __future__ import annotations
import argparse, hashlib, json, shutil, struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
EXP=Path(__file__).resolve().parents[1]
CANON_SHA='424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67'
ARCHIVE_SHA='82fa96f91c4ef8abaae3a14a3f4153facf88bed821d1f7331cec2700f432c427'

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--model-root',type=Path,required=True);ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
 if args.output.exists():raise SystemExit('output exists')
 if digest(args.archive)!=ARCHIVE_SHA:raise SystemExit('archive hash mismatch')
 transcript=EXP/'protocol/transcript.txt';raw=transcript.read_bytes()
 if len(raw)!=226 or raw.endswith(b'\n') or digest(transcript)!=CANON_SHA:raise SystemExit('canonical transcript drift')
 model_out=args.output/'models/supertonic-3';model_out.mkdir(parents=True);(args.output/'protocol').mkdir()
 for p in args.model_root.iterdir():
  if p.is_file():shutil.copy2(p,model_out/p.name)
 shutil.copy2(ROOT/'experiments/0008-sherpa-onnx-android-tts-benchmark/models/supertonic-3/sherpa-config.json',model_out/'sherpa-config.json')
 shutil.copy2(ROOT/'experiments/0008-sherpa-onnx-android-tts-benchmark/models/supertonic-3/m1-proof.json',model_out/'m1-proof.json')
 shutil.copy2(transcript,args.output/'protocol/transcript.txt')
 descriptor=json.loads((ROOT/'experiments/0008-sherpa-onnx-android-tts-benchmark/models/supertonic-3/android-descriptor.json').read_text())
 descriptor['transcript_sha256']=CANON_SHA;descriptor['warm_runs']=5;descriptor['files']['protocol/transcript.txt']=CANON_SHA
 (model_out/'descriptor.json').write_text(json.dumps(descriptor,indent=2)+'\n')
 files=[]
 for p in sorted(x for x in args.output.rglob('*') if x.is_file()):files.append({'path':p.relative_to(args.output).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)})
 inventory=args.output.parent/'stage-inventory.json';inventory.write_text(json.dumps({'schema_version':1,'files':files},indent=2)+'\n')
 table=(model_out/'unicode_indexer.bin').read_bytes();values=struct.unpack('<'+str(len(table)//4)+'i',table);text=raw.decode('utf-8');codepoints=[ord(c) for c in text]
 if max(codepoints)>=len(values):raise SystemExit('unicode index table too small')
 ids=[values[c] for c in codepoints]
 packed=b''.join(struct.pack('<i',v) for v in ids)
 frontend={'schema_version':1,'input':{'path':'protocol/transcript.txt','bytes':len(raw),'sha256':CANON_SHA,'trailing_newline':False,'utf8_text':text},'frontend':{'kind':'official Supertonic unicode_indexer.bin direct codepoint mapping before model frontend','unicode_indexer_sha256':digest(model_out/'unicode_indexer.bin'),'unicode_codepoint_count':len(codepoints),'unicode_codepoints':codepoints,'mapped_id_count':len(ids),'mapped_ids':ids,'mapped_ids_int32le_sha256':hashlib.sha256(packed).hexdigest()},'descriptor':{'path':'models/supertonic-3/descriptor.json','sha256':digest(model_out/'descriptor.json'),'warm_runs':5,'threads':1,'provider':'cpu','voice':'M1','speaker_id':5}}
 results=EXP/'results';results.mkdir(exist_ok=True);(results/'frontend-provenance.json').write_text(json.dumps(frontend,indent=2)+'\n')
 print(json.dumps({'stage_files':len(files),'stage_bytes':sum(x['bytes'] for x in files),'inventory':str(inventory),'descriptor_sha256':frontend['descriptor']['sha256'],'frontend_ids_sha256':frontend['frontend']['mapped_ids_int32le_sha256']},indent=2))
if __name__=='__main__':main()

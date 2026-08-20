#!/usr/bin/env python3
"""Copy frozen 0008 Android app and apply only the proven internal-input adapter."""
from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'experiments/0008-sherpa-onnx-android-tts-benchmark/android'
ORIGINAL_SHA='c087a1c212cbef0b12805458a1f2f8ba8b685697a2272cf87a11df16e6572148'
EXPECTED_ADAPTED_SHA='396a24b95d960ea4c5a17f2afc0308c2be4410877f188d0fb4b39653331601fc'

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--aar',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
 if args.output.exists(): raise SystemExit('output exists')
 if digest(args.aar)!='6419cd8bc983e0c4fab06067f0fe0313fdc0f7103818ac1e7a08d50787b7a82b': raise SystemExit('AAR hash mismatch')
 shutil.copytree(SOURCE,args.output,ignore=shutil.ignore_patterns('build','.gradle','local.properties','libs'))
 (args.output/'libs').mkdir();shutil.copy2(args.aar,args.output/'libs/sherpa-onnx-1.13.5.aar')
 java=args.output/'app/src/main/java/dev/moket/ttsbench/BenchmarkActivity.java'
 if digest(java)!=ORIGINAL_SHA: raise SystemExit('frozen Activity hash drift')
 s=java.read_text();s=s.replace('File external=getExternalFilesDir(null);String descriptorName=','File external=getExternalFilesDir(null);File inputRoot=getFilesDir();String descriptorName=');s=s.replace('SecureFiles.verify(external,Map.of(descriptorName','SecureFiles.verify(inputRoot,Map.of(descriptorName');s=s.replace('Map<String,File> verified=SecureFiles.verify(external,d.files());','Map<String,File> verified=SecureFiles.verify(inputRoot,d.files());');java.write_text(s)
 if digest(java)!=EXPECTED_ADAPTED_SHA: raise SystemExit('adapted Activity hash mismatch')
 print(json.dumps({'source_tree':'experiments/0008-sherpa-onnx-android-tts-benchmark/android','original_activity_sha256':ORIGINAL_SHA,'adapted_activity_sha256':EXPECTED_ADAPTED_SHA,'semantic_change':'verified input root only; external output unchanged'},indent=2))
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Assemble ignored direct-QNN Android stage for 37-context fused-graph route."""
from __future__ import annotations
import argparse,hashlib,json,os,shutil
from pathlib import Path
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def link(src,dst):dst.parent.mkdir(parents=True,exist_ok=True);os.link(src,dst)
def main():
 p=argparse.ArgumentParser();p.add_argument('--aot-dir',type=Path,required=True);p.add_argument('--prior-stage',type=Path,required=True);p.add_argument('--android-deps',type=Path,required=True);p.add_argument('--runner',type=Path,required=True);p.add_argument('--libcxx',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir
 if out.exists():shutil.rmtree(out)
 out.mkdir(parents=True);summary=json.loads((a.aot_dir/'summary.json').read_text());lines=[]
 for part in summary['parts']:
  name=part['name'];rel=Path('contexts')/(name+'.bin');link(a.aot_dir/name/part['context_binary']['path'],out/rel);lines.append(f'{rel}\t{name}')
 (out/'consolidated-contexts.tsv').write_text('\n'.join(lines)+'\n')
 for n in ('embedding-quant.u8','embedding-scales.f32le','embedding-zp.u8','short.int32le'):link(a.prior_stage/n,out/n)
 link(a.runner,out/'direct_lfm2_qnn_runner');libs={a.android_deps/'qnnruntime/jni/arm64-v8a/libQnnHtp.so':'libQnnHtp.so',a.android_deps/'qnnruntime/jni/arm64-v8a/libQnnSystem.so':'libQnnSystem.so',a.android_deps/'qnnruntime/jni/arm64-v8a/libQnnHtpV73Stub.so':'libQnnHtpV73Stub.so',a.android_deps/'qnnruntime/jni/arm64-v8a/libQnnHtpV73Skel.so':'libQnnHtpV73Skel.so',a.libcxx:'libc++_shared.so'}
 for src,n in libs.items():link(src,out/n)
 files=sorted(x for x in out.rglob('*') if x.is_file());entries=[]
 with (out/'SHA256SUMS').open('w') as f:
  for x in files:
   rel=x.relative_to(out).as_posix();d=sha(x);f.write(f'{d}  {rel}\n');entries.append({'path':rel,'bytes':x.stat().st_size,'sha256':d})
 meta={'schema_version':1,'classification':'ignored_license_controlled_consolidated_direct_qnn_android_stage','route':'37 QNN contexts loaded once: 30 fused layer graphs, final norm, 6 grouped LM-head graphs; no ORT/EPContext/reload','context_count':37,'graph_count':37,'source_part_count':263,'explicit_state':'22 convolution plus 8 attention K/V pairs','cpu_boundary':['selected-row Q4 embedding dequantization','request/token orchestration','global greedy argmax'],'files':entries,'total_bytes_excluding_manifests':sum(x['bytes'] for x in entries),'retained_outside_git':True};(out/'stage.json').write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n');
 with (out/'SHA256SUMS').open('a') as f:f.write(f"{sha(out/'stage.json')}  stage.json\n")
 print(json.dumps({'stage':str(out),'payload_files':len(entries),'payload_bytes':meta['total_bytes_excluding_manifests'],'contexts':37},indent=2))
if __name__=='__main__':main()

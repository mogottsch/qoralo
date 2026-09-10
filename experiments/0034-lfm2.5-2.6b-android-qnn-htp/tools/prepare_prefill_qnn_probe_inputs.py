#!/usr/bin/env python3
"""Write exact named raw inputs for a position-zero fixed-width QNN prefill probe."""
import argparse,hashlib,json,struct
from pathlib import Path
import numpy as np
ATTN={2,5,9,13,17,21,24,27};H=2048;CAP=4096;VOCAB=128000;EMBED='/model/embed_tokens/GatherBlockQuantized/output_0'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def emb(ids,q,s,z):
 o=np.empty((1,len(ids),H),np.float32)
 for r,t in enumerate(ids):
  u=np.empty(H,np.float32);u[::2]=q[t]&15;u[1::2]=q[t]>>4;zp=np.empty(64,np.float32);zp[::2]=z[t]&15;zp[1::2]=z[t]>>4;o[0,r]=(u-np.repeat(zp,32))*np.repeat(s[t],32)
 return o
ap=argparse.ArgumentParser();ap.add_argument('--sequence-length',type=int,required=True);ap.add_argument('--token-file',type=Path,required=True);ap.add_argument('--embedding-dir',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args();N=a.sequence_length;past=CAP-N;raw=a.token_file.read_bytes();ids=np.asarray(struct.unpack('<%di'%(len(raw)//4),raw)[:N],np.int32);q=np.memmap(a.embedding_dir/'embedding-quant.u8',np.uint8,'r',shape=(VOCAB,1024));s=np.memmap(a.embedding_dir/'embedding-scales.f32le',np.float32,'r',shape=(VOCAB,64));z=np.memmap(a.embedding_dir/'embedding-zp.u8',np.uint8,'r',shape=(VOCAB,32));o=a.output_dir;o.mkdir(parents=True,exist_ok=True);items=[]
def put(name,data):
 p=o/(f'{len(items):02d}.raw');np.asarray(data).tofile(p);items.append({'name':name,'path':str(p.resolve()),'bytes':p.stat().st_size,'sha256':sha(p)})
# qnn-net-run defaults to FLOAT32 file ingestion and casts numeric float values
# to this graph's INT64 position tensor. Do not write integer bit patterns here.
put(EMBED,emb(ids,q,s,z));put('position_ids',np.arange(N,dtype=np.float32)[None,:]);mask=np.full((1,1,N,CAP),-65504,np.float32)
for r in range(N):mask[0,0,r,past:past+r+1]=0
put('attention_mask',mask)
for i in range(30):
 if i in ATTN:put(f'past_key_values.{i}.key',np.zeros((1,8,64,past),np.float32));put(f'past_key_values.{i}.value',np.zeros((1,8,past,64),np.float32))
 else:put(f'past_conv.{i}',np.zeros((1,H,3),np.float32))
(o/'input-list.txt').write_text(' '.join(f"{x['name']}:={x['path']}" for x in items)+'\n');res={'schema_version':1,'classification':'position0_chunk_prefill_qnn_raw_inputs','sequence_length':N,'past_cache_length':past,'token_file_sha256':sha(a.token_file),'tokens':ids.tolist(),'position_file_mode':'default-float32','position_graph_data_type':'QNN_DATATYPE_INT_64','position_values':{'start':0,'count':N},'required_qnn_net_run_native_flags':[],'inputs':items,'total_input_bytes':sum(x['bytes'] for x in items),'input_list_sha256':sha(o/'input-list.txt')};(o/'result.json').write_text(json.dumps(res,indent=2,sort_keys=True)+'\n');print(json.dumps({'inputs':len(items),'bytes':res['total_input_bytes'],'input_list':str(o/'input-list.txt')},indent=2))

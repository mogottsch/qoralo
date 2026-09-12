#!/usr/bin/env python3
"""Prepare exact-history input/cache ledger; no neural graph evaluation."""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np

TRACK=Path(__file__).resolve().parents[1]
ROOT=TRACK/'.local/matched-prefill-reference'
STAGE=TRACK/'.local/frozen-stages/selected-id-long-20260911T143756Z-01'
LOG=TRACK/'.local/selected-id-phone-long-runs/trace-long-20260911T150027Z-01/raw/device/genie-verbose.log'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def chunks(count=1929,ar=128):
    return [{'index':i,'start':start,'real_rows':min(ar,count-start),'padded_rows':ar-min(ar,count-start),'final_valid_row':min(ar,count-start)-1} for i,start in enumerate(range(0,count,ar))]


def cache_positions(past,width):
    slots=np.full(width,-1,dtype=np.int32)
    for token in range(max(0,past-width),past):slots[token%width]=token
    return slots


def masks(past,real,ar=128,ctx=4096,window=512):
    global_mask=np.zeros((1,1,ar,ctx),dtype=np.uint16)
    swa_mask=np.zeros((1,1,ar,window+ar),dtype=np.uint16)
    slots=cache_positions(past,window)
    for row in range(real):
        global_mask[0,0,row,:past]=65535;global_mask[0,0,row,ctx-ar:ctx-ar+row+1]=65535
        keep=(slots>=0)&(slots>=past+row-window+1)
        swa_mask[0,0,row,:window][keep]=65535;swa_mask[0,0,row,window:window+row+1]=65535
    return global_mask,swa_mask


def requant_lut(codes,lut,grid):
    scale=lut['scale']/grid['scale'][0];offset=int(scale*lut['offset']-grid['offset'][0])
    value=np.asarray(codes,dtype=np.float64)*scale+offset
    if value.min()<0 or value.max()>65535:raise ValueError('unexpected out-of-range input requantization')
    return value.astype(np.uint16)  # C++ integer casts truncate; no nearest QDQ substitution


def rope_tables(positions,width,theta,real_frequencies,cos_grid):
    # The bound Genie uses double pow/sin/cos and COS grid parameters for BOTH
    # tables, then clamps/truncates. Preserve that SWA-sine zero-point quirk.
    scale=cos_grid['scale'][0];offset=cos_grid['offset'][0]
    inv=[1.0/math.pow(theta,j/width) if j<real_frequencies else 0.0 for j in range(width)]
    c=np.empty((1,1,len(positions),width),dtype=np.uint16);s=np.empty_like(c)
    for i,pos in enumerate(positions):
        for j,freq in enumerate(inv):
            angle=int(pos)*freq
            c[0,0,i,j]=int(min(65535,max(0,math.cos(angle)/scale-offset)))
            s[0,0,i,j]=int(min(65535,max(0,math.sin(angle)/scale-offset)))
    return c,s


def advance_cache(caches,outputs,step):
    """Copy actual prior graph outputs; never synthesize zero cache after chunk0."""
    start=step['start'];n=step['real_rows']
    for name,buf in caches.items():
        out=name.removesuffix('_in')+'_out';value=outputs[out]
        is_key='_key_' in name;axis=-1 if is_key else -2;width=buf.shape[axis]
        if value.dtype!=buf.dtype:raise ValueError('cache dtype changed '+name)
        for row in range(n):
            dst=[slice(None)]*buf.ndim;src=[slice(None)]*value.ndim;dst[axis]=(start+row)%width;src[axis]=row
            buf[tuple(dst)]=value[tuple(src)]


def saved_schedule():
    steps=[];gathers=[]
    pattern=re.compile(r'Step (\d+): AR-128 CL-4096 n_past=(\d+) n_kv=(\d+) n_process=(\d+) @ past_idx=(\d+) new_idx=(\d+)')
    with LOG.open() as f:
        for line in f:
            match=pattern.search(line)
            if match and len(steps)<16:steps.append([int(v) for v in match.groups()])
            if 'SWA Gather index = ' in line and len(gathers)<16:gathers.append(ast.literal_eval(line.split('SWA Gather index = ',1)[1]))
            if len(steps)==len(gathers)==16:break
    return steps,gathers


def prepare(out):
    out.mkdir(parents=True,exist_ok=False);policy=json.loads((ROOT/'policy-01/policy.json').read_text());ts=policy['tensors']
    manifest=json.loads((STAGE/'frozen-manifest.json').read_text());cfg=json.loads((STAGE/'gemma4-e2b-htp-cl4096-greedy.json').read_text())['dialog'];bindings=[]
    for name in ['embedding_int8_lut.bin','embed_tokens_per_layer_int8_lut.bin','token-ids/long.int32le','gemma4-e2b-htp-cl4096-greedy.json']:
        path=STAGE/name;h=sha(path)
        if h!=manifest['files'][name]['sha256']:raise ValueError('frozen input artifact changed '+name)
        bindings.append({'path':str(path),'sha256':h,'bytes':path.stat().st_size})
    ids=np.fromfile(STAGE/'token-ids/long.int32le',dtype='<i4')
    if len(ids)!=1929 or ids[0]!=2:raise ValueError('exact1929 single-BOS input required')
    token_lut=np.memmap(STAGE/'embedding_int8_lut.bin',dtype='u1',mode='r',shape=(262144,1536))
    ple_lut=np.memmap(STAGE/'embed_tokens_per_layer_int8_lut.bin',dtype='u1',mode='r',shape=(262144,8960))
    schedule=chunks();recorded,gathers=saved_schedule();cache_names=[n for n in policy['input_names'] if '_key_' in n or '_value_' in n]
    if len(recorded)!=16 or len(gathers)!=16:raise ValueError('complete saved16-step/gather correlation required')
    if len(cache_names)!=30:raise ValueError('30 cache inputs required')
    initial={};cache_contracts=[]
    for name in cache_names:
        spec=ts[name];other=ts[name.removesuffix('_in')+'_out']
        if spec['datatype']!=other['datatype'] or spec.get('grid')!=other.get('grid'):raise ValueError('cache policy not preserved '+name)
        # Bound CacheGroup uses key-derived quantized clear word0x8000 for the
        # group. For FP16 values this is negative zero, not an invented +0 cast.
        value=np.full(spec['dimensions'],32768,dtype=np.uint16)
        if spec['datatype']=='Float_16':value=value.view(np.float16)
        file=out/(name+'.npy');np.save(file,value,allow_pickle=False);initial[name]={'file':file.name,'sha256':sha(file)}
        cache_contracts.append({'input':name,'output':other['name'],'input_dimensions':spec['dimensions'],'output_dimensions':other['dimensions'],'datatype':spec['datatype'],'initial_raw_uint16_word':32768,'update_axis':-1 if '_key_' in name else -2,'update_rule':'copy previous output real rows to absolute_position modulo cache width, no requantization'})
    for step,actual,gather in zip(schedule,recorded,gathers):
        i=step['index'];past=step['start'];n=step['real_rows']
        if actual!=[i,past,past,n,0,3968]:raise ValueError('saved physical schedule mismatch')
        positions=list(range(past,past+n))+[0]*(128-n);tokens=np.concatenate([ids[past:past+n],np.full(128-n,cfg['context']['eos-token'][0],dtype=np.int32)])
        gm,sm=masks(past,n)
        expanded=[]
        for start,count in gather:expanded.extend(range(start,start+count) if start>=0 else [-1]*count)
        if len(expanded)>640:raise ValueError('oversized SWA gather')
        expanded.extend([-1]*(640-len(expanded)))
        gathered=np.zeros_like(sm)
        for j,column in enumerate(expanded):
            if column>=0:gathered[0,0,:,j]=gm[0,0,:,column]
        for row in range(n):
            for j,column in enumerate(expanded[:512]):
                if column>=0 and column<past+row-511:gathered[0,0,row,j]=0
        if not np.array_equal(gathered,sm):raise ValueError('SWA mask differs from saved physical gather')
        values={'inputs_embeds':requant_lut(token_lut[tokens],cfg['embedding']['quant-param'],ts['inputs_embeds']['grid'])[None],
          'per_layer_inputs':requant_lut(ple_lut[tokens],cfg['perlayer-embedding']['quant-param'],ts['per_layer_inputs']['grid']).reshape(1,128,35,256),
          'attention_mask':gm,'swa_attention_mask':sm}
        for prefix,width,theta,real in [('',256,1e6,64),('swa_',128,1e4,128)]:
            c,s=rope_tables(positions,width,theta,real,ts[prefix+'position_ids_cos']['grid']);values[prefix+'position_ids_cos']=c;values[prefix+'position_ids_sin']=s
        folder=out/f'chunk-{i:02d}';folder.mkdir();files={}
        for name,value in values.items():
            file=folder/(name+'.npy');np.save(file,value,allow_pickle=False);files[name]={'file':str(file.relative_to(out)),'sha256':sha(file),'dimensions':list(value.shape),'dtype':str(value.dtype)}
        step.update(saved_genie_step=actual,saved_SWA_gather=gather,position_ids=positions,padding_token_id=1,input_files=files,swa_slot_absolute_positions=cache_positions(past,512).tolist(),global_cache_valid_range=[0,past],new_graph_columns={'global':3968,'SWA':512},cache_updates={'global_destination_range':[past,past+n],'SWA_destination_slots':[(past+j)%512 for j in range(n)]})
    result={'classification':'exact_history_declared_final_policy_input_ledger','neural_forward_calls':0,'policy_sha256':sha(ROOT/'policy-01/policy.json'),'context_sha256':manifest['context_sha256'],'input_bindings':bindings,'input_count':1929,'AR128_chunks':16,'final_real_rows':9,'final_valid_logit_row':8,'initial_caches':initial,'cache_contracts':cache_contracts,'chunks':schedule,
      'mask_raw_policy':{'allowed':65535,'blocked':0,'declared_blocked_value':-50,'SWA_span_including_self':512,'padding_rows_all_blocked':True},
      'RoPE_policy':{'calculation':'double pow/sin/cos, clamp/truncate to UINT16 using each family COS scale/offset for BOTH sin and cos','global_width':256,'global_real_frequencies':64,'SWA_width':128,'padded_positions':0,'SWA_sin_declared_offset':ts['swa_position_ids_sin']['grid']['offset'][0],'SWA_sin_host_quantization_offset':ts['swa_position_ids_cos']['grid']['offset'][0],'host_libm_vs_Android_bit_equality_verified':False},
      'input_byte_boundary':'Frozen source-derived arrays and hash-bound formula; no physical tensor dump. All logical IDs/chunks/padding/masks/cache-slot updates match bound source and saved physical step/gather records. Host versus Android libm may differ at quantization boundaries.',
      'cache_evolution':'Future runner must carry actual returned cache tensors through advance_cache after each chunk. No cache values beyond initial state have been computed or fabricated.'}
    (out/'ledger.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'chunks':16,'final_valid_row':8,'cache_contracts':30,'SWA_gather_matches_saved':True,'RoPE_policy':result['RoPE_policy'],'neural_forward_calls':0},indent=2))


def bind_captured_noncache(capture_dir,source_ledger_path,output_dir):
    """Bind ACTUAL device non-cache buffers; never import an HTP-produced cache."""
    import copy
    capture_dir=Path(capture_dir).resolve();source_ledger_path=Path(source_ledger_path);output_dir=Path(output_dir)
    source=json.loads(source_ledger_path.read_text());policy_path=ROOT/'policy-01/policy.json';policy=json.loads(policy_path.read_text());specs=policy['tensors']
    if sha(policy_path)!=source['policy_sha256'] or len(source['chunks'])!=16 or source['input_count']!=1929:raise ValueError('bound full-history ledger required')
    noncache={'inputs_embeds','per_layer_inputs','attention_mask','swa_attention_mask','position_ids_cos','position_ids_sin','swa_position_ids_cos','swa_position_ids_sin'}
    if any(set(step['input_files'])!=noncache for step in source['chunks']):raise ValueError('exact8 non-cache inputs required; HTP caches forbidden')
    events=[json.loads(line) for line in (capture_dir/'capture.jsonl').read_text().splitlines()]
    complete={};begun=set()
    for row in events:
        key=(row['phase'],row['step'],row['name'])
        if row['event']=='begin':
            if key in begun:raise ValueError('duplicate capture begin')
            begun.add(key)
        elif row['event']=='complete':
            if key not in begun or key in complete:raise ValueError('unbound/duplicate capture complete')
            complete[key]=row
        else:raise ValueError('unknown capture event')
    expected={('input',step['index'],name) for step in source['chunks'] for name in step['input_files']}|{('output',15,'logits')}
    if set(complete)!=expected or begun!=expected:raise ValueError('complete128 non-cache inputs plus final logits required')
    if any(row.get('cache_tensor') is not False for row in complete.values()):raise ValueError('cache tensors forbidden in capture binding')
    result=copy.deepcopy(source);output_dir.mkdir(parents=True,exist_ok=False);differences=[]
    for name,record in source['initial_caches'].items():
        path=source_ledger_path.parent/record['file']
        if sha(path)!=record['sha256']:raise ValueError('host initial cache changed')
        (output_dir/record['file']).write_bytes(path.read_bytes())
    for step in result['chunks']:
        folder=output_dir/f"chunk-{step['index']:02d}";folder.mkdir()
        for name,old in list(step['input_files'].items()):
            row=complete[('input',step['index'],name)];spec=specs[name]
            if row['variant']!=128 or row['context']!=4096 or row['n_past']!=step['start'] or row['n_process']!=step['real_rows'] or row['n_valid_kv']!=step['start'] or row['past_idx']!=0 or row['new_idx']!=3968 or row['shape']!=spec['dimensions'] or row['datatype']!='QNN_DATATYPE_UFIXED_POINT_16':raise ValueError('captured input contract mismatch '+name)
            if np.float32(row['scale'])!=np.float32(spec['grid']['scale'][0]) or row['offset']!=spec['grid']['offset'][0]:raise ValueError('captured input grid mismatch '+name)
            filename=f"{step['index']:02d}-input-{name}.raw"
            path=capture_dir/filename
            if row['file']!=filename or path.is_symlink() or path.resolve().parent!=capture_dir:raise ValueError('unsafe capture path')
            data=path.read_bytes()
            if len(data)!=row['bytes'] or len(data)!=2*np.prod(spec['dimensions']):raise ValueError('captured input length')
            value=np.frombuffer(data,dtype='<u2').reshape(spec['dimensions'])
            planned=np.load(source_ledger_path.parent/old['file'],allow_pickle=False)
            differences.append({'chunk':step['index'],'name':name,'different_elements_from_host_formula':int(np.count_nonzero(value!=planned))})
            saved=folder/(name+'.npy');np.save(saved,value,allow_pickle=False)
            step['input_files'][name]={'file':str(saved.relative_to(output_dir)),'sha256':sha(saved),'raw_capture_sha256':hashlib.sha256(data).hexdigest(),'dimensions':spec['dimensions'],'dtype':'uint16'}
    logit=complete[('output',15,'logits')];raw=capture_dir/'15-output-logits.raw'
    if raw.is_symlink() or logit['file']!=raw.name or logit['final_valid_row']!=8 or logit['shape']!=[1,1,262144] or logit['bytes']!=524288 or raw.stat().st_size!=524288 or not logit['before_sampler_access'] or logit['variant']!=128 or logit['context']!=4096 or logit['n_past']!=1920 or logit['n_process']!=9 or logit['datatype']!='QNN_DATATYPE_UFIXED_POINT_16':raise ValueError('final logit capture contract')
    lg=specs['logits']['grid']
    if np.float32(logit['scale'])!=np.float32(lg['scale'][0]) or logit['offset']!=lg['offset'][0]:raise ValueError('captured final-logit grid mismatch')
    result.update(actual_noncache_capture_bound=True,cache_origin='Host initial state plus ONLY reference-returned caches; no HTP cache input accepted',capture_journal_sha256=sha(capture_dir/'capture.jsonl'),HTP_logit_capture={'path':str(raw),'sha256':sha(raw),'metadata':logit},host_formula_comparison=differences,input_byte_boundary='All128 external non-cache input arrays are exact copies of the actual frozen-Genie captures. Source-generated host-libm arrays are only comparison metadata, not reference inputs.')
    (output_dir/'ledger.json').write_text(json.dumps(result,indent=2)+'\n');return result


def run_reference_prefill(policy_path,ledger_path,output_dir,*,authorization_id=None,wall_seconds=1800):
    """Future explicitly authorized execution entry point; NOT called in preparation."""
    if not authorization_id:raise PermissionError('A new full-model execution grant is required')
    import time
    from declared_dlc_reference import DeclaredDlcReference,decode
    policy_path=Path(policy_path);ledger_path=Path(ledger_path);output_dir=Path(output_dir)
    ledger=json.loads(ledger_path.read_text())
    if not ledger.get('actual_noncache_capture_bound'):raise ValueError('Paired execution requires actual non-cache captures, not host-libm formula inputs')
    if sha(policy_path)!=ledger['policy_sha256']:raise ValueError('policy binding mismatch')
    output_dir.mkdir(parents=True,exist_ok=False);ref=DeclaredDlcReference(policy_path);base=ledger_path.parent;start=time.monotonic()
    caches={}
    for n,v in ledger['initial_caches'].items():
        if sha(base/v['file'])!=v['sha256']:raise ValueError('initial cache binding changed '+n)
        caches[n]=np.load(base/v['file'],allow_pickle=False)
    trace={'events':0,'bytes':0,'error':None};stream=(output_dir/'operations.jsonl').open('x')
    for step in ledger['chunks']:
        values={}
        for name,record in step['input_files'].items():
            path=base/record['file']
            if sha(path)!=record['sha256']:raise ValueError('prepared input changed '+name)
            values[name]=np.load(path,allow_pickle=False)
        values.update(caches)
        def event(row):
            if trace['error'] is not None:return
            try:
                line=json.dumps({**row,'chunk':step['index']})+'\n'
                if trace['events']>=300000 or trace['bytes']+len(line)>64*1024*1024:
                    trace['error']='bounded trace cap';return
                stream.write(line);stream.flush();trace['events']+=1;trace['bytes']+=len(line)
            except OSError as exc:trace['error']=repr(exc)
        if step['index']==0:(output_dir/'prefill-started.json').write_text(json.dumps({'authorization_id':authorization_id,'logical_prefill_attempts':1,'input_tokens':1929,'AR128_chunks':16,'monotonic_ns':time.monotonic_ns()})+'\n')
        outputs=ref.run_encoded(values,allow_full_model=True,authorization_id=authorization_id,wall_seconds=wall_seconds-(time.monotonic()-start),on_event=event)
        # Actual returned encoded values flow to the next chunk; never reset.
        advance_cache(caches,outputs,step)
        (output_dir/'progress.json').write_text(json.dumps({'completed_chunks':step['index']+1,'seconds':time.monotonic()-start})+'\n')
    raw=outputs['logits'][0,ledger['final_valid_logit_row']].copy();spec=dict(ref.policy['tensors']['logits']);spec['dimensions']=[262144]
    raw.astype('<u2',copy=False).tofile(output_dir/'last-logits.uint16le');decode(raw,spec).astype('<f4').tofile(output_dir/'last-logits.float32le')
    try:stream.close()
    except OSError as exc:trace['error']=repr(exc)
    receipt={'complete':True,'trace':trace,'logical_prefills':1,'AR128_executions':16,'input_tokens':1929,'generation_calls':0,'raw_saved_before_analysis':True,'raw_sha256':sha(output_dir/'last-logits.uint16le'),'float32_sha256':sha(output_dir/'last-logits.float32le'),'seconds':time.monotonic()-start,'DSP_kernel_equivalence':False}
    (output_dir/'capture.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir.resolve()
    if not out.is_relative_to(ROOT):p.error('owned fresh private output required')
    prepare(out)


if __name__=='__main__':main()

#!/usr/bin/env python3
"""Analyze retained cost metadata only. Never loads or executes a model."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import statistics

TRACK=Path(__file__).resolve().parents[1]
ROOT=TRACK/'.local/native-qat-reference'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def category(begin):
    op=begin['operation']
    if op=='native.apply_srq':return 'SRQ'
    if op=='torch.functional.linear':return 'linear'
    if op=='torch.matmul':
        args=begin.get('args',[])
        if len(args)>=2 and isinstance(args[0],dict) and isinstance(args[1],dict):
            a,b=args[0].get('shape'),args[1].get('shape')
            if a==[1,8,1929,1929] and b in ([1,8,1929,256],[1,8,1929,512]):return 'AV_D'+str(b[-1])
            if a in ([1,8,1929,256],[1,8,1929,512]) and b==[1,8,a[-1],1929]:return 'QK_D'+str(a[-1])
        return 'other_matmul'
    if op.endswith('.embedding_dequant'):
        args=begin.get('args',[])
        if len(args)>1 and isinstance(args[1],dict) and args[1].get('shape')==[262144,384]:return 'full_token_embedding_dequant'
        return 'selected_embedding_dequant'
    if op.endswith('.linear_dequant'):return 'linear_dequant'
    return 'wrapper_or_other_exclusive'


def summarize(records,end_ns=None):
    begins={};ends={};issues=[]
    for x in records:
        i=x['call']
        if x['event']=='begin':
            if i in begins:issues.append('duplicate begin '+str(i))
            parent=x.get('parent')
            if parent is not None:
                if parent not in begins:issues.append('missing parent '+str(parent))
                elif x.get('depth')!=begins[parent].get('depth',0)+1 or x.get('thread')!=begins[parent].get('thread'):issues.append('invalid parent nesting '+str(i))
            begins[i]=x
        else:
            if i not in begins or i in ends:issues.append('unmatched/duplicate end '+str(i))
            elif x['operation']!=begins[i]['operation'] or x.get('parent')!=begins[i].get('parent'):issues.append('end binding mismatch '+str(i))
            ends[i]=x
    direct_children=defaultdict(list)
    for i,x in ends.items():
        if x.get('parent') is not None:direct_children[x['parent']].append(x)
    for i,x in ends.items():
        for key,exclusive in [('wall_ns','exclusive_wall_ns'),('process_cpu_ns','exclusive_process_cpu_ns')]:
            expected=x[key]-sum(c[key] for c in direct_children[i])
            if x.get(exclusive)!=expected:issues.append('exclusive accounting mismatch '+str(i)+' '+key)
    groups=defaultdict(list);exclusive=Counter();cpu=Counter();completed=[]
    for i,x in ends.items():
        if i not in begins:continue
        b=begins[i];kind=category(b)
        exclusive[kind]+=x['exclusive_wall_ns']/1e9;cpu[kind]+=x['exclusive_process_cpu_ns']/1e9
        row={'call':i,'operation':x['operation'],'category':kind,'args':b.get('args'),'wall_seconds':x['wall_ns']/1e9,'CPU_seconds':x['process_cpu_ns']/1e9,'exclusive_wall_seconds':x['exclusive_wall_ns']/1e9,'event':x['event']}
        completed.append(row);groups[kind].append(row)
    stats={}
    for kind,values in groups.items():
        times=[x['wall_seconds'] for x in values]
        stats[kind]={'completed_calls':len(values),'inclusive_wall_median_seconds':statistics.median(times),'inclusive_wall_min_seconds':min(times),'inclusive_wall_max_seconds':max(times),'exclusive_wall_total_seconds':exclusive[kind],'exclusive_CPU_total_seconds':cpu[kind]}
    pending=[]
    for i,b in begins.items():
        if i not in ends:
            pending.append({'call':i,'operation':b['operation'],'parent':b.get('parent'),'depth':b.get('depth'),'category':category(b),'args':b.get('args'),'open_interval_at_stop_seconds':(end_ns-b['monotonic_ns'])/1e9 if end_ns is not None else None})
    projected=None
    if 'AV_D256' in stats and 'AV_D512' in stats:projected=28*stats['AV_D256']['inclusive_wall_median_seconds']+7*stats['AV_D512']['inclusive_wall_median_seconds']
    return {'correlation_issues':issues,'begin_count':len(begins),'completed_count':len(ends),'thread_ids':sorted({x.get('thread') for x in begins.values()}),'groups':stats,'completed_exclusive_wall_seconds':dict(exclusive),'open_at_trace_end':sorted(pending,key=lambda x:x.get('depth',0)),
      'AV_only_full35_layer_projection_seconds':projected,'projection_boundary':'28 sliding D256 plus7 global D512 calls at observed per-shape medians; not a guaranteed bound or full model completion prediction.',
      'timing_boundary':'Only exclusive intervals are totaled. Inclusive durations contain nested work and must not be summed with children. Open ancestor intervals overlap; do not sum them. Process CPU includes native workers; cross-thread overlaps are not independent CPU cost.'},completed


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir.resolve()
    if out.parent!=TRACK/'results' or not out.name.startswith('native-qat-cost-checkpoint-'):p.error('fresh owning result directory required')
    out.mkdir(parents=True,exist_ok=False);run=ROOT/'cost-prefill-01';guard_dir=ROOT/'cost-01-launch';private=[]
    for label,root in [('native',run),('guard',guard_dir)]:
        dest=out/'receipts'/label;dest.mkdir(parents=True)
        for f in root.iterdir():
            if not f.is_file():continue
            if f.suffix=='.bin' or f.name=='analysis.json':private.append({'path':str(f),'bytes':f.stat().st_size,'sha256':sha(f),'reason':'Private requested logits or their numerical analysis'});continue
            shutil.copyfile(f,dest/f.name)
    guard=json.loads((guard_dir/'guard-result.json').read_text());trace=run/'native-operations.jsonl';records=[];malformed=[]
    for i,line in enumerate(trace.read_text().splitlines(),1):
        try:records.append(json.loads(line))
        except json.JSONDecodeError:malformed.append(i)
    summary,completed=summarize(records,guard.get('stop_monotonic_ns',guard['end_monotonic_ns']))
    summary['malformed_line_numbers']=malformed
    summary['trace_may_be_capped']=len(records)>=10000 or trace.stat().st_size>=8*1024*1024-65536
    resource=[json.loads(x) for x in (guard_dir/'resources.jsonl').read_text().splitlines()]
    forward_ns=int(json.loads((run/'forward-started.json').read_text())['monotonic']*1e9)
    samples=[x for x in resource if x['monotonic_ns']>=forward_ns and 'io' in x.get('child',{})]
    io=None
    if len(samples)>1:
        first,last=samples[0]['child'],samples[-1]['child']
        if first['starttime']==last['starttime']:io={k:last['io'][k]-first['io'][k] for k in first['io']}
    kernel={}
    for name in ['stdout','stderr']:
        text=(guard_dir/(name+'.log')).read_text(errors='replace');lines=text.splitlines()
        kernel[name]={'MKL_verbose_lines':sum('MKL_VERBOSE' in x for x in lines),'oneDNN_verbose_lines':sum('onednn_verbose' in x or 'dnnl_verbose' in x for x in lines),'matched_metadata_lines':[x for x in lines if 'MKL_VERBOSE' in x or 'onednn_verbose' in x or 'dnnl_verbose' in x]}
    native=json.loads((run/'result.json').read_text()) if (run/'result.json').exists() else None
    report={'classification':'one_native_QAT_observation_cost_checkpoint','guard':guard,'native_result':native,'forward_attempts':1,'completed_forward':bool(native and native.get('passed')),'exact_input_ids_sha256':sha(run/'input-ids.int32le'),'strict_loaded_validation_passed':json.loads((run/'load-validation.json').read_text())['passed'],
      'trace':summary,'forward_sampled_IO_delta':io,'IO_boundary':'Owned-process kernel counters between first/last samples after forward marker, not all memory traffic or exact whole-forward counters.','kernel_verbose':kernel,'kernel_identity_boundary':'Verbose metadata only. Missing records do not identify or rule out a kernel. Tensor-level QK/AV timings do not prove the lower-level kernel.',
      'instrumentation_gap':'Per-decoder-layer wrapper selector used Gemma4DecoderLayer, but pinned class is Gemma4TextDecoderLayer. Operator and quant-forward nesting remains captured; no per-layer-forward duration is claimed.',
      'private_outputs':private,'same_computation':True,'changed_dtype_weights_scales_input_or_deadline':False,'memory_lock_admission':False,'phone_calls':0,'automatic_replay':False,'QNN_root_cause_or_quality_result':False}
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');(out/'completed-operations.json').write_text(json.dumps(completed,indent=2)+'\n')
    sums=out/'SHA256SUMS';sums.write_text(''.join(f'{sha(f)}  {f.relative_to(out)}\n' for f in sorted(out.rglob('*')) if f.is_file() and f!=sums))
    print(json.dumps({'result':str(out),'guard_exit':guard.get('actual_child_exit'),'completed_forward':report['completed_forward'],'trace_issues':summary['correlation_issues'],'completed_exclusive_seconds':summary['completed_exclusive_wall_seconds'],'open_frames':summary['open_at_trace_end'],'AV_projection':summary['AV_only_full35_layer_projection_seconds']},indent=2))


if __name__=='__main__':main()

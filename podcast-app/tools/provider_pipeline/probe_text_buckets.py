#!/usr/bin/env python3
"""Bounded HOST-CPU source comparison, never phone/HTP execution or speech synthesis."""
import argparse,hashlib,json,os,resource,time
from contextlib import nullcontext
from pathlib import Path
from text_buckets import ROOT,derive,runtime_edges


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--bucket',type=int,default=320);a=p.parse_args()
    os.umask(0o077)
    if '.local' not in a.output.resolve().parts:raise ValueError('Private output only')
    a.output.mkdir(parents=True,exist_ok=False)
    spec={'scope':'host CPU DP/text source comparison only','bucket':a.bucket,'thresholdMaxAbsolute':1e-4,'thresholdRmse':1e-5,
        'sourceCases':'15 frozen real provider segments plus synthetic nativeT1,2,3,8,9,16,17,31,32,127,319,320 within bucket',
        'threads':2,'addressSpaceGiB':8,'deadlineSeconds':300,'phoneCalls':0,'speechRenders':0}
    (a.output/'protocol.json').write_text(json.dumps(spec,indent=2)+'\n')
    available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))
    if available < 2*1024*1024:raise RuntimeError('Insufficient live headroom for bounded source comparison')
    with nullcontext():  # Moritz removed memory-lock admission; actual process/resource bounds remain.
        import signal
        def deadline(*_):raise TimeoutError('bounded source comparison deadline')
        signal.signal(signal.SIGALRM,deadline)
        os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='2'
        signal.alarm(300);resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
        os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:2]))
        import numpy as np,onnx,onnxruntime as ort
        start=time.monotonic();freeze=json.loads((ROOT/'experiments/0037-supertonic-provider-pipeline/protocol/freeze.json').read_text())
        bundle=ROOT/'experiments/0037-supertonic-provider-pipeline/.local/common/bundle'
        manifest=json.loads((bundle/'manifest.json').read_text())
        if hashlib.sha256((bundle/'manifest.json').read_bytes()).hexdigest()!=freeze['bundle_manifest_sha256']:raise ValueError('Bundle drift')
        cases=[]
        for c in manifest['chunks']:
            folder=bundle/f'{c["index"]:03d}';path=folder/'text_ids.i64'
            if hashlib.sha256(path.read_bytes()).hexdigest()!=c['ids_sha256']:raise ValueError('Input drift')
            cases.append((f'real-{c["index"]:03d}',np.fromfile(path,dtype='<i8').reshape(1,-1)))
        for n in sorted({1,2,3,8,9,16,17,31,32,127,a.bucket-1,a.bucket}):
            cases.append((f'synthetic-{n}',np.full((1,n),int(cases[0][1][0,4]),dtype=np.int64)))
        report={'protocol':spec,'onnxruntime':ort.__version__,'numpy':np.__version__,'components':{},'status':'started'}
        try:
            for component in ['duration','text']:
                binding=freeze['cpu_original_model_bindings'][component];source=Path(binding['source'])
                if hashlib.sha256(source.read_bytes()).hexdigest()!=binding['sha256']:raise ValueError('Source drift')
                model,delta=derive(onnx.load(source),component,a.bucket);path=a.output/(component+'.onnx');onnx.save(model,path)
                (a.output/(component+'-delta.json')).write_text(json.dumps(delta,indent=2)+'\n')
                opts=ort.SessionOptions();opts.intra_op_num_threads=2;opts.inter_op_num_threads=1;opts.enable_mem_pattern=False
                native=ort.InferenceSession(str(source),opts,providers=['CPUExecutionProvider'])
                padded=ort.InferenceSession(str(path),opts,providers=['CPUExecutionProvider'])
                style_name='style_dp' if component=='duration' else 'style_ttl'
                shape=(1,8,16) if component=='duration' else (1,50,256)
                style_path=bundle/(style_name+'.f32')
                if hashlib.sha256(style_path.read_bytes()).hexdigest()!=manifest['tensors'][style_name+'.f32']['sha256']:raise ValueError('Style drift')
                style=np.fromfile(style_path,dtype='<f4').reshape(shape)
                records=[]
                for label,ids in cases:
                    n=ids.shape[1]
                    if n>a.bucket:raise ValueError('Case does not fit bucket')
                    direct={'text_ids':ids,style_name:style,'text_mask':np.ones((1,1,n),dtype=np.float32)}
                    actual_ids=np.zeros((1,a.bucket),dtype=np.int64);actual_ids[:,:n]=ids
                    mask=np.zeros((1,1,a.bucket),dtype=np.float32);mask[:,:,:n]=1
                    bucket={'text_ids':actual_ids,style_name:style,'text_mask':mask,**runtime_edges(n,a.bucket,component)}
                    ref=native.run(None,direct)[0];full=padded.run(None,bucket)[0];got=full if component=='duration' else full[:,:,:n]
                    if not np.isfinite(ref).all() or not np.isfinite(got).all():raise ValueError('Nonfinite output')
                    diff=got.astype(np.float64)-ref.astype(np.float64)
                    mx=float(np.max(np.abs(diff)));rms=float(np.sqrt(np.mean(diff**2)))
                    ref.astype('<f4').tofile(a.output/(component+'-'+label+'-native.f32'));full.astype('<f4').tofile(a.output/(component+'-'+label+'-bucket.f32'))
                    records.append({'case':label,'nativeT':n,'maxAbsolute':mx,'rmse':rms,'passed':mx<=1e-4 and rms<=1e-5,
                        'inactiveExactlyZero':bool(np.all(full[:,:,n:]==0)) if component=='text' else None})
                report['components'][component]={'cases':records,'sourceSha256':binding['sha256'],
                    'derivativeSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'allCasesPass':all(r['passed'] for r in records)}
                del native,padded,model
            report['status']='passed' if all(x['allCasesPass'] for x in report['components'].values()) else 'numerical_gate_failed'
        except BaseException as error:
            report['status']='error';report['errorType']=type(error).__name__
            raise
        finally:
            report['seconds']=time.monotonic()-start;report['maxRssKiB']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            (a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
            signal.alarm(0)
        print(json.dumps({'status':report['status'],'seconds':report['seconds'],'maxRssKiB':report['maxRssKiB'],
            'components':{k:{'cases':len(v['cases']),'maxAbsolute':max(x['maxAbsolute'] for x in v['cases']),'allPass':v['allCasesPass']} for k,v in report['components'].items()}}))

if __name__=='__main__':main()

"""ONE separately authorized cost checkpoint; no host memory-lock admission."""
import hashlib,json,os,signal,subprocess,threading,time
from pathlib import Path
import shutil
TRACK=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality')
ROOT=TRACK/'.local/native-qat-reference';HERE=ROOT/'cost-01-launch';G=1024**3
started=time.monotonic();reason=None;child=None;streams={};threads=[]
def save(name,x):(HERE/name).write_text(json.dumps(x,indent=2)+'\n')
def stop(sig,frame):
 global reason
 reason='guard_signal_'+str(sig)
for s in (signal.SIGTERM,signal.SIGINT):signal.signal(s,stop)
def capacity():
 m={s.split(':')[0]:int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines()}
 return {'mem_available':m['MemAvailable'],'swap_free':m['SwapFree'],'disk_free':shutil.disk_usage(ROOT).free}
def stat(pid):
 b=Path(f'/proc/{pid}/stat').read_text();f=b[b.rfind(') ')+2:].split()
 return {'starttime':f[19],'state':f[0],'utime_ticks':int(f[11]),'stime_ticks':int(f[12])}
def child_usage(pid,born):
 try:
  x=stat(pid)
  if x['starttime']!=born:return {'unavailable':'identity mismatch; no other PID inspected'}
  io={line.split(':')[0]:int(line.split()[1]) for line in Path(f'/proc/{pid}/io').read_text().splitlines()}
  mem={}
  for line in Path(f'/proc/{pid}/status').read_text().splitlines():
   if line.startswith(('VmRSS:','VmHWM:','VmSwap:')):mem[line.split(':')[0]]=int(line.split()[1])*1024
  return {**x,'clock_ticks_per_second':os.sysconf('SC_CLK_TCK'),'io':io,'memory_bytes':mem}
 except (OSError,IndexError,ValueError) as e:return {'unavailable':type(e).__name__}
def cgroup_usage():
 try:
  rel=next(x.split('::',1)[1] for x in Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::'))
  cg=Path('/sys/fs/cgroup')/rel.lstrip('/');result={}
  for name in ('memory.current','memory.peak','memory.swap.current','memory.swap.peak','memory.events','cpu.stat','io.stat'):
   f=cg/name;result[name]=f.read_text().strip() if f.exists() else None
  return result
 except (OSError,StopIteration) as e:return {'unavailable':type(e).__name__}
def drain(label,pipe):
 limit=16*1024*1024;h=hashlib.sha256();total=kept=0;error=None
 try:
  with (HERE/(label+'.log')).open('xb') as f:
   while True:
    b=os.read(pipe.fileno(),65536)
    if not b:break
    h.update(b);total+=len(b);piece=b[:max(0,limit-kept)]
    if piece:f.write(piece);f.flush();kept+=len(piece)
 except Exception as e:error=repr(e)
 finally:
  pipe.close();streams[label]={'total_bytes':total,'retained_prefix_bytes':kept,'discarded_bytes':total-kept,'full_stream_sha256':h.hexdigest(),'error':error,'cap_bytes':limit}
result={'authorization':'Pi separately authorized ONE native-QAT observation-only cost checkpoint','model_forward_limit':1,'generation_calls':0,'adb_calls':0,'host_memory_lock_admission':False}
try:
 before=capacity();save('capacity-before.json',before)
 if before['mem_available']<16*G or before['swap_free']<10*G or before['disk_free']<64*G:raise RuntimeError('fresh host headroom insufficient')
 if not json.loads((ROOT/'meta-validation-02/validation.json').read_text())['passed']:raise RuntimeError('strict schema not ready')
 with (ROOT/'cost-checkpoint-01-consumed.json').open('x') as f:json.dump({'separate_authorization':True,'prior_b376a318_not_replayed_under_old_grant':True,'output':str(ROOT/'cost-prefill-01'),'guard_pid':os.getpid()},f)
 env={'PATH':'/usr/bin:/bin','HOME':str(HERE/'home'),'TMPDIR':str(HERE/'tmp'),'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','DO_NOT_TRACK':'1','CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','TOKENIZERS_PARALLELISM':'false','PYTHONDONTWRITEBYTECODE':'1','DNNL_VERBOSE':'1','ONEDNN_VERBOSE':'1','MKL_VERBOSE':'1'}
 cmd=[str(TRACK.parents[1]/'.local/qairt-2.49.40-venv/bin/python'),'-B',str(TRACK/'tools/native_qat_checkpoint.py'),'--execute','--observe-cost','--output-dir',str(ROOT/'cost-prefill-01')]
 save('child-command.json',{'argv':cmd,'environment':env,'close_fds':True,'source_sha256':hashlib.sha256((TRACK/'tools/native_qat_checkpoint.py').read_bytes()).hexdigest(),'trace_source_sha256':hashlib.sha256((TRACK/'tools/native_qat_cost_trace.py').read_bytes()).hexdigest()})
 child=subprocess.Popen(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,stdin=subprocess.DEVNULL,close_fds=True,start_new_session=True)
 born=stat(child.pid)['starttime'];save('child-pid.json',{'pid':child.pid,'starttime':born,'process_group':child.pid})
 for label,pipe in [('stdout',child.stdout),('stderr',child.stderr)]:
  t=threading.Thread(target=drain,args=(label,pipe),daemon=True);t.start();threads.append(t)
 while child.poll() is None:
  now=time.monotonic();c=capacity()
  with (HERE/'resources.jsonl').open('a') as f:f.write(json.dumps({'monotonic_ns':time.monotonic_ns(),'seconds':now-started,**c,'child':child_usage(child.pid,born),'cgroup':cgroup_usage()})+'\n')
  if c['mem_available']<4*G or c['swap_free']<8*G or c['disk_free']<64*G:reason='headroom_floor'
  if now-started>580:reason='wall_budget_with_cleanup_margin'
  if (HERE/'STOP').exists():reason='owned_stop_file'
  if reason:
   result['stop_monotonic_ns']=time.monotonic_ns();result['last_child_usage']=child_usage(child.pid,born)
   os.killpg(child.pid,signal.SIGTERM)
   try:child.wait(timeout=12)
   except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
   break
  time.sleep(2)
 result['actual_child_exit']=child.wait()
except BaseException as e:result['guard_error']=repr(e)
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=12)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 for t in threads:t.join(timeout=5)
 result.update(child_reaped=child is None or child.poll() is not None,stop_reason=reason,seconds=time.monotonic()-started,streams=streams,final_cgroup=cgroup_usage(),end_monotonic_ns=time.monotonic_ns())
 save('guard-result.json',result);print(json.dumps(result,indent=2))
raise SystemExit(0 if result.get('actual_child_exit')==0 and not reason and 'guard_error' not in result else 1)

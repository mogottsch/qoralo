import fcntl,hashlib,json,os,signal,subprocess,time
from pathlib import Path
import shutil
TRACK=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality')
ROOT=TRACK/'.local/native-qat-reference';HERE=ROOT/'forward-01-launch';G=1024**3
reason=None;child=None;fd=None;held=False;started=time.monotonic()
def stop(sig,frame):
 global reason
 reason='guard_signal_'+str(sig)
for s in (signal.SIGTERM,signal.SIGINT):signal.signal(s,stop)
def capacity():
 m={s.split(':')[0]:int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines()}
 return {'mem_available':m['MemAvailable'],'swap_free':m['SwapFree'],'disk_free':shutil.disk_usage(ROOT).free}
def save(name,x):(HERE/name).write_text(json.dumps(x,indent=2)+'\n')
result={'model_forward_limit':1,'generation_calls':0,'adb_calls':0,'heavy_lock_requested_by_pi':True}
try:
 before=capacity();save('capacity-before.json',before)
 if before['mem_available']<16*G or before['swap_free']<10*G or before['disk_free']<64*G:raise RuntimeError('fresh host headroom insufficient')
 validation=json.loads((ROOT/'meta-validation-02/validation.json').read_text())
 if not validation['passed']:raise RuntimeError('metadata validation not ready; no lock')
 lock=TRACK.parents[3]/'artifacts/locks/heavy-ram.lock'
 fd=os.open(lock,os.O_RDWR|os.O_CREAT|os.O_CLOEXEC,0o600);os.set_inheritable(fd,False)
 try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise RuntimeError('actual heavy-ram.lock holder/conflict; no waiting reservation')
 held=True;result['heavy_lock_acquired']=True
 after=capacity()
 if after['mem_available']<16*G or after['swap_free']<10*G:raise RuntimeError('headroom changed after lock')
 with (ROOT/'one-prefill-consumed.json').open('x') as f:json.dump({'authorization':'Pi native-QAT ONE CPU prefill,2026-09-12','guard_pid':os.getpid(),'forward_output':str(ROOT/'prefill-01'),'validation_sha256':hashlib.sha256((ROOT/'meta-validation-02/validation.json').read_bytes()).hexdigest()},f)
 env={'PATH':'/usr/bin:/bin','HOME':str(HERE/'home'),'TMPDIR':str(HERE/'tmp'),'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','DO_NOT_TRACK':'1','CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','TOKENIZERS_PARALLELISM':'false','PYTHONDONTWRITEBYTECODE':'1'}
 cmd=[str(TRACK.parents[1]/'.local/qairt-2.49.40-venv/bin/python'),'-B',str(TRACK/'tools/native_qat_checkpoint.py'),'--execute','--output-dir',str(ROOT/'prefill-01')]
 save('child-command.json',{'argv':cmd,'environment':env,'close_fds':True,'lock_fd_inheritable':False,'source_sha256':hashlib.sha256((TRACK/'tools/native_qat_checkpoint.py').read_bytes()).hexdigest()})
 with (HERE/'child.stdout').open('xb') as out,(HERE/'child.stderr').open('xb') as err:
  child=subprocess.Popen(cmd,env=env,stdout=out,stderr=err,stdin=subprocess.DEVNULL,close_fds=True,start_new_session=True)
  save('child-pid.json',{'pid':child.pid,'process_group':child.pid})
  while child.poll() is None:
   c=capacity()
   with (HERE/'resources.jsonl').open('a') as f:f.write(json.dumps({'seconds':time.monotonic()-started,**c})+'\n')
   if c['mem_available']<4*G or c['swap_free']<8*G or c['disk_free']<64*G:reason='headroom_floor'
   if time.monotonic()-started>580:reason='wall_budget_with_cleanup_margin'
   if (HERE/'STOP').exists():reason='owned_stop_file'
   if reason:
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
 if fd is not None:
  if held:fcntl.flock(fd,fcntl.LOCK_UN)
  os.close(fd)
 result.update(heavy_lock_released=True,child_reaped=child is None or child.poll() is not None,stop_reason=reason,seconds=time.monotonic()-started)
 save('guard-result.json',result)
 print(json.dumps(result,indent=2))
raise SystemExit(0 if result.get('actual_child_exit')==0 and not reason and 'guard_error' not in result else 1)

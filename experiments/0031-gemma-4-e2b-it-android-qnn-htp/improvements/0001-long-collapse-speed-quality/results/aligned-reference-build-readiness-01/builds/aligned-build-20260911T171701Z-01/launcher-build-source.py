#!/usr/bin/env python3
"""Bounded Android frontend build using copied, hash-bound cached core objects.

No Bazel daemon, dependency resolution, SDK mutation, model loading or ADB.
Historical cached objects are explicitly reused, not claimed newly rebuilt or
proven identical to every object of the historical GPU executable.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import time

TRACK=Path(__file__).resolve().parents[1]
EXP=TRACK.parents[1]
REF=EXP.parent/'0025-gemma-4-e2b-it-android'
CORE=REF/'.local/LiteRT-LM'
REV='924e79c91542761242244e4f1651851f822e4cbb'
CACHE=Path('/home/moritz/.cache/bazel/_bazel_moritz/ab44f4d89db1f18b2686fa7c4849d44d/execroot/litert_lm')
BIN='bazel-out/arm64-v8a-opt/bin'
PARAM=BIN+'/runtime/engine/litert_lm_canonical_runner-2.params'
PARAM_SHA='404526fdc21b0b3cd0e9a5853c54a72cf5b97c7109ac615ad5a95c164f0db3f5'
OLDOBJ=BIN+'/runtime/engine/_objs/litert_lm_canonical_runner/litert_lm_canonical_runner.o'
OLDOUT=BIN+'/runtime/engine/litert_lm_canonical_runner'
NDK=Path('/home/moritz/Android/Sdk/ndk/28.1.13356709')
LLVM=NDK/'toolchains/llvm/prebuilt/linux-x86_64'
SOURCE=TRACK/'results/aligned-reference-source-readiness-01/litert_lm_aligned_reference.cc'
SOURCE_SHA='bd3e22b740fcfca317434f1e31a0f23e01af3bd8784aaeb6874a1a30f1e138d6'
LIB_SHA='3fdbf64355af65b3ca6ed0c633ffed1e4faa1bfa9256f5e7403fec1633ea1b74'
GiB=1024**3


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()


def capacity(root):
    m={s.split(':')[0]:int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines()}
    return {'mem_available':m['MemAvailable'],'swap_free':m['SwapFree'],'disk_free':shutil.disk_usage(root).free}


def link_arguments(lines):
    if lines.count(OLDOBJ)!=1 or lines[-2:]!=['-o',OLDOUT]:raise ValueError('cached link structure changed')
    out=[('aligned-reference.o' if s==OLDOBJ else 'bin/litert_lm_aligned_reference' if s==OLDOUT else s) for s in lines]
    return out+['-Wl,-rpath,$ORIGIN/../lib']


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run-id',required=True);a=ap.parse_args()
    if not re.fullmatch(r'aligned-build-[A-Za-z0-9-]+',a.run_id):ap.error('fresh aligned-build ID required')
    root=TRACK/'.local/aligned-reference-builds'/a.run_id
    root.mkdir(parents=True,exist_ok=False,mode=0o700)
    began=time.monotonic();steps=[];bindings=[]
    def save(name,value):(root/name).write_text(json.dumps(value,indent=2)+'\n')
    def bound_copy(source,dest):
        c=capacity(root)
        if c['mem_available']<4*GiB or c['swap_free']<8*GiB or c['disk_free']<64*GiB:raise RuntimeError('copy headroom floor')
        if sum(r['bytes'] for r in bindings)+Path(source).stat().st_size>16*GiB:raise RuntimeError('owned copy allocation cap')
        before=sha(source);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        if sha(dest)!=before:raise ValueError('copy mismatch '+str(source))
        bindings.append({'source':str(source),'copy':str(dest.relative_to(root)),'bytes':dest.stat().st_size,'sha256':before})
    def run(name,cmd,cwd):
        save(name+'-command.json',{'argv':list(map(str,cmd)),'cwd':str(cwd)})
        start=time.monotonic();reason=None
        env={'PATH':'/usr/bin:/bin','HOME':str(root/'home'),'TMPDIR':str(root/'tmp'),'LANG':'C.UTF-8'}
        with (root/(name+'.stdout')).open('wb') as o,(root/(name+'.stderr')).open('wb') as e:
            child=subprocess.Popen(list(map(str,cmd)),cwd=cwd,env=env,stdout=o,stderr=e,start_new_session=True,close_fds=True)
            while child.poll() is None:
                c=capacity(root)
                with (root/'resources.jsonl').open('a') as f:f.write(json.dumps({'t':time.monotonic()-began,'step':name,**c})+'\n')
                if c['mem_available']<4*GiB or c['swap_free']<8*GiB or c['disk_free']<64*GiB:reason='headroom_floor'
                if time.monotonic()-began>1700:reason='wall_budget'
                if (root/'STOP').exists():reason='owned_stop_file'
                if reason:
                    os.killpg(child.pid,signal.SIGTERM)
                    try:child.wait(timeout=20)
                    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                    break
                time.sleep(1)
            code=child.wait()
        receipt={'name':name,'actual_exit_code':code,'seconds':time.monotonic()-start,'stop_reason':reason}
        steps.append(receipt);save(name+'-exit.json',receipt)
        if code or reason:raise RuntimeError('native step failed: '+name)
    try:
        c=capacity(root);save('capacity-before.json',c)
        if c['mem_available']<12*GiB or c['swap_free']<12*GiB or c['disk_free']<100*GiB:raise RuntimeError('launch headroom insufficient')
        if subprocess.check_output(['git','rev-parse','HEAD'],cwd=CORE,text=True).strip()!=REV:raise ValueError('wrong core revision')
        dirty=subprocess.check_output(['git','--no-optional-locks','status','--short'],cwd=CORE,text=True).splitlines()
        if set(dirty)-{' M runtime/engine/BUILD','?? runtime/engine/litert_lm_canonical_runner.cc'}:raise ValueError('unexpected core changes')
        save('core-binding.json',{'revision':REV,'dirty':dirty,'mode':'fresh git archive plus unchanged copied cached objects; no original GPU binary equivalence claim'})
        if sha(SOURCE)!=SOURCE_SHA or sha(CACHE/PARAM)!=PARAM_SHA:raise ValueError('source/link receipt hash changed')
        for n in ['home','tmp','work/bin','work/lib']:(root/n).mkdir(parents=True)
        work=root/'work'
        with (root/'core.tar').open('wb') as out:
            subprocess.run(['git','archive',REV],cwd=CORE,stdout=out,check=True)
        subprocess.run(['tar','-xf',str(root/'core.tar'),'-C',str(work)],check=True)
        bound_copy(SOURCE,work/'aligned-reference.cc')
        bound_copy(CACHE/PARAM,root/'original-link.params')
        lines=(CACHE/PARAM).read_text().splitlines()
        # Independent private copies: no hardlinks/symlinks back to cached objects.
        for s in lines:
            if s.startswith('-') or s in {OLDOBJ,OLDOUT}:continue
            if not s.endswith(('.o','.a')):raise ValueError('unrecognized link file '+s)
            bound_copy(CACHE/s,work/s)
        # Preserve frontend header dependencies except NDK system headers; the
        # immutable installed NDK is used directly and actual compiler .d saved.
        dep=CACHE/(OLDOBJ[:-2]+'.d')
        bound_copy(dep,root/'original-frontend.d')
        for s in shlex.split(dep.read_text().replace('\\\n',' '))[1:]:
            if s.startswith('external/androidndk/') or s.endswith('.cc'):continue
            if s.startswith(('external/','bazel-out/')) and (CACHE/s).is_file():bound_copy(CACHE/s,work/s)
        # Pin the actual built runtime, not its different prebuilt namesake.
        lib=CACHE/(BIN+'/external/litert/litert/c/libLiteRt.so')
        if sha(lib)!=LIB_SHA:raise ValueError('accepted libLiteRt bytes unavailable')
        bound_copy(lib,work/'lib/libLiteRt.so')
        for s in lines:
            if s.startswith('-L'):
                d=work/s[2:];d.mkdir(parents=True,exist_ok=True)
                bound_copy(lib,d/'libLiteRt.so')
        save('copied-inputs.json',bindings)
        save('toolchain.json',{'ndk':'28.1.13356709','compiler':str(LLVM/'bin/clang++'),'compiler_sha256':sha(LLVM/'bin/clang++'),'linker_sha256':sha(LLVM/'bin/ld.lld'),'frontend_flags':'new explicit Android31/C++20/O3 frontend flags; cached core not recompiled'})
        run('compiler-version',[LLVM/'bin/clang++','--version'],work)
        cmd=[LLVM/'bin/clang++','--target=aarch64-linux-android31','-std=c++20','-O3','-DNDEBUG','-fPIC','-DABSL_FLAGS_STRIP_NAMES=0','-I.','-I'+BIN,'-Iexternal/com_google_absl','-Iexternal/litert','-Iexternal/nlohmann_json/include','-MMD','-MF','aligned-reference.d','-c','aligned-reference.cc','-o','aligned-reference.o']
        run('compile',cmd,work)
        (work/'link.params').write_text('\n'.join(link_arguments(lines))+'\n')
        run('link',[LLVM/'bin/clang','@link.params'],work)
        run('elf',[LLVM/'bin/llvm-readelf','-h','-d','-n',work/'bin/litert_lm_aligned_reference'],work)
        run('undefined-symbols',[LLVM/'bin/llvm-nm','-D','--undefined-only',work/'bin/litert_lm_aligned_reference'],work)
        for row in bindings:
            if sha(root/row['copy'])!=row['sha256']:raise ValueError('copied input changed '+row['copy'])
        save('build-result.json',{'classification':'frontend_compiled_and_linked_core_objects_reused','actual_success':True,'steps':steps,'seconds':time.monotonic()-began,'binary_sha256':sha(work/'bin/litert_lm_aligned_reference'),'binary_bytes':(work/'bin/litert_lm_aligned_reference').stat().st_size,'source_sha256':SOURCE_SHA,'libLiteRt_sha256':LIB_SHA,'copied_input_count':len(bindings),'model_load_or_inference':False,'adb_calls':0,'historical_gpu_executable_equivalence_proven':False})
    except BaseException as e:
        save('build-result.json',{'actual_success':False,'steps':steps,'error':repr(e),'seconds':time.monotonic()-began,'model_load_or_inference':False,'adb_calls':0})
        save('copied-inputs.json',bindings)
        raise


if __name__=='__main__':main()

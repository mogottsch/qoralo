#!/usr/bin/env python3
"""Reuse the retained host supervisor; fresh disk scratch, serial command, no retry.

This wrapper itself grants no execution permission. Preparation used only synthetic
tests and ONNX metadata inspection. The existing supervisor handles STOP, pressure,
wall deadline, TERM/KILL/reap. An8GiB address-space ceiling bounds parser accidents.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import types

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]
GUARD = REPO/'experiments/0032-qwen-3.5-2b-android-qnn-htp/tools/qwen_host_guard.py'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--seconds',type=int,default=120)
    p.add_argument('command',nargs=argparse.REMAINDER)
    a=p.parse_args()
    if not 1<=a.seconds<=1800 or not a.command or a.directory.exists():p.error('fresh directory,1..1800seconds and command required')
    directory=a.directory.resolve()
    if not directory.is_relative_to(ROOT.resolve()):p.error('guard directory must be in owned track')
    directory.mkdir(parents=True);(directory/'guard').mkdir();(directory/'scratch').mkdir()
    # Linux prlimit execs the command in the same supervised process group.
    command=['nice','-n','15','ionice','-c','2','-n','7','prlimit','--as=8589934592','--',*a.command]
    environment=dict(os.environ,TMPDIR=str(directory/'scratch'),OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4')
    module=types.ModuleType('retained_host_guard');module.__file__=str(GUARD)
    source=GUARD.read_bytes();exec(compile(source,str(GUARD),'exec'),module.__dict__)
    (directory/'command.json').write_text(json.dumps({'argv':command,'guard_source':str(GUARD),'guard_source_sha256':hashlib.sha256(source).hexdigest(),'math_threads':4,'tmpdir':environment['TMPDIR'],'address_space_limit_bytes':8589934592},indent=2)+'\n')
    report=module.supervise(command,directory/'guard',a.seconds,env=environment)
    print(json.dumps(report,indent=2));print((directory/'guard/stderr.log').read_text());print((directory/'guard/stdout.log').read_text()[:4000])
    raise SystemExit(0 if report['exit_code']==0 else 1)


if __name__=='__main__':main()

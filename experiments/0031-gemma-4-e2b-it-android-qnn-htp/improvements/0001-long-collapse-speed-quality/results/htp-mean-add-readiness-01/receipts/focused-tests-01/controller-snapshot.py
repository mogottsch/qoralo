#!/usr/bin/env python3
"""Plan-only adaptation of the validated continuous-lease two-case controller."""
import argparse
import hashlib
from pathlib import Path
import sys
import types

TOOLS=Path(__file__).resolve().parent
BASE_SHA='e92a637841cf69515eaa30ebdbc3217838b2ec0a7757091655e223f002d7a383'
CHAIN_SHA='efd83b1ff26f25dcdeef63c8837b2f7e2ee3bbb887f5f8bb0cd1549f06ed521e'
STAGE_NAME='htp-mean-add-stage-01'
DIGEST='f860ed18df22270801551be16499ecb9c2a3f10351f4b84d2da3c5bba7bc60b2'
CASES=('mean_edge','epsilon_add')
_BASE=None
_CHAIN=None
_RECEIPT=None


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def substitute(source,changes):
    original=source
    for before,after,count in changes:
        if source.count(before)!=count:raise ValueError('mean/add adapter anchor changed '+before)
        source=source.replace(before,after)
    inverse=source
    for before,after,count in reversed(changes):
        if inverse.count(after)!=count:raise ValueError('mean/add inverse anchor changed '+after)
        inverse=inverse.replace(after,before)
    if inverse!=original:raise ValueError('unbounded mean/add adapter change')
    return source


def components():
    global _BASE,_CHAIN,_RECEIPT
    if _BASE is not None:return _BASE,_CHAIN,_RECEIPT
    base_path=TOOLS/'phone_htp_power_discriminator.py';chain_path=TOOLS/'phone_htp_chain_discriminator.py'
    if sha(base_path)!=BASE_SHA or sha(chain_path)!=CHAIN_SHA:raise ValueError('validated base controllers changed')
    base_changes=[('htp-power-edge-stage-01',STAGE_NAME,1),('51053482d9d0d198b43343830503d8c1c3d2ee3337c4ccb598e792248dffb993',DIGEST,1),("('power_edge','normalization_chain','normalization_exposed')","('mean_edge','epsilon_add')",2),('power-edge-context.bin','mean-add-context.bin',1),('1180672','512',2),('graph_count=3','graph_count=2',1),('one tiny three-graph HTP edge/fusion checkpoint; not device permission','two standalone Mean/Add controls; not device permission',1),('three authored HTP scalar/normalization graphs only; no LLM/reference','two authored HTP Mean/Add controls only; no LLM/reference',1),('three tiny HTP graphs; native raw codes; no model/reference/CPU fallback','two tiny Mean/Add graphs; native raw codes; no model/reference/CPU fallback',1),('from phone_htp_power_discriminator import common, scripts','from phone_htp_mean_add_discriminator import base_common as common, base_scripts as scripts',1)]
    bs=substitute(base_path.read_text(),base_changes);bm=types.ModuleType('mean_add_base_adapter');bm.__file__=str(Path(__file__).resolve());sys.modules[bm.__name__]=bm;exec(compile(bs,bm.__file__,'exec'),bm.__dict__);_BASE=bm
    chain_changes=[("CASES=('normalization_chain','normalization_exposed')","CASES=('mean_edge','epsilon_add')",1),("lists=['__','__','__']","lists=['__','__']",1),('.local/htp-chain-phone-runs','.local/htp-mean-add-phone-runs',1),('/data/local/tmp/vibevoice-0031-htp-chain-','/data/local/tmp/vibevoice-0031-htp-mean-add-',1),('1180416','512',2),('loaded_context_graphs=3','loaded_context_graphs=2',1),('ONLY two remaining normalization graphs; separate named one-execution invocations, one continuous phone lease','ONLY standalone Mean and epsilon-Add; separate named one-execution invocations, one continuous lease',1)]
    cs=substitute(chain_path.read_text(),chain_changes);cm=types.ModuleType('mean_add_chain_adapter');cm.__file__=str(Path(__file__).resolve());sys.modules[cm.__name__]=cm;exec(compile(cs,cm.__file__,'exec'),cm.__dict__);cm.base_module=lambda:bm;_CHAIN=cm
    _RECEIPT={'base_controller_sha256':BASE_SHA,'two_case_controller_sha256':CHAIN_SHA,'base_changes':base_changes,'case_changes':chain_changes,'materialized_base_sha256':hashlib.sha256(bs.encode()).hexdigest(),'materialized_case_controller_sha256':hashlib.sha256(cs.encode()).hexdigest(),'same_lease_ownership_cleanup_limits':True,'Power_or_normalization_chain_execution_requested':False,'physical_execution_authorized_by_preparation':False}
    return _BASE,_CHAIN,_RECEIPT


def base_common(remote):return components()[0].common(remote)
def base_scripts(remote):return components()[0].scripts(remote)
def case_argv(remote,case):return components()[1].case_argv(remote,case)
def all_scripts(remote):return components()[1].all_scripts(remote)


def load_lifecycle(expected,quiet):
    base,chain,binding=components();module,receipt=chain.load_lifecycle(expected,quiet);receipt['mean_add_adapter']=binding;receipt['mean_add_adapter_sha256']=sha(Path(__file__));receipt['single_output_controls_only']=True
    parent_plan=module.plan
    def plan():
        p=parent_plan();p.update(stage=str(base.STAGE),reviewed_stage_digest=DIGEST,selected_cases=list(CASES),graph_count=2,loaded_context_graphs=2,Power_execution_requested=False,normalization_chain_execution_requested=False,single_output_each=True,expected_raw_output_bytes=512);return p
    module.plan=plan
    return module,receipt


def main():
    p=argparse.ArgumentParser(add_help=False);p.add_argument('--expected-app-sha256');p.add_argument('--expected-test-sha256');p.add_argument('--pi-user-job-quiescent',action='store_true');a,rest=p.parse_known_args();expected={k:v for k,v in {'dev.vibevoice.podcast.internal':a.expected_app_sha256,'dev.vibevoice.podcast.internal.test':a.expected_test_sha256}.items() if v}
    if '--execute' in rest and (len(expected)!=2 or not a.pi_user_job_quiescent):p.error('fresh scoped grant/APKs/quiescence required')
    module,_=load_lifecycle(expected,a.pi_user_job_quiescent);sys.argv=[sys.argv[0],*rest];return module.main()


if __name__=='__main__':raise SystemExit(main())

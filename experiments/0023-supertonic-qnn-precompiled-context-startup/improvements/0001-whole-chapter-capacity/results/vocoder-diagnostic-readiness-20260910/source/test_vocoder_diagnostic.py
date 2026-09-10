import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import diagnose_vocoder_context as diagnostic
from test_compile_component_context import FakeOrt as BaseFake, request as base_request


class FakeOrt(BaseFake):
    def __init__(self,fail=None):super().__init__('vocoder',fail);self.logging=[]
    def set_default_logger_severity(self,value):self.logging.append(('severity',value))
    def set_default_logger_verbosity(self,value):self.logging.append(('verbosity',value))
    def InferenceSession(self,*args,**kwargs):
        assert self.logging==[('severity',0),('verbosity',1)]
        assert kwargs['sess_options'].log_severity_level==0 and kwargs['sess_options'].log_verbosity_level==1
        return super().InferenceSession(*args,**kwargs)


def request(out):
    value=base_request('vocoder',out);value.update(worker_sha256=diagnostic.sha(diagnostic.__file__),diagnostics=diagnostic.DIAGNOSTICS)
    return value


def fixture(root,membership='/',mount_root='/system.slice/docker-test.scope'):
    proc=root/'proc';(proc/'self').mkdir(parents=True);mount=root/'cg';mount.mkdir()
    (proc/'self/cgroup').write_text('0::'+membership+'\n')
    (proc/'self/mountinfo').write_text(f'1 0 0:1 {mount_root} {mount} ro - cgroup2 cgroup rw\n')
    return proc,mount


class VocoderDiagnosticTests(unittest.TestCase):
    def test_namespace_root_own_scope_metrics_and_missing_peak(self):
        with tempfile.TemporaryDirectory() as temp:
            proc,mount=fixture(Path(temp))
            for name,value in [('memory.current','123\n'),('memory.max','8589934592\n'),('memory.events','oom 0\noom_kill 0\n')]: (mount/name).write_text(value)
            value=diagnostic.cgroup_snapshot(proc)
            self.assertEqual(str(mount),value['directory']);self.assertIsNone(value['scope_error'])
            self.assertEqual('0::/\n',value['proc_self_cgroup']);self.assertEqual('8589934592\n',value['files']['memory.max']['raw'])
            self.assertIsNone(value['files']['memory.peak']['raw']);self.assertIn('FileNotFoundError',value['files']['memory.peak']['error'])

    def test_host_namespace_membership_resolves_own_child_not_host_root(self):
        with tempfile.TemporaryDirectory() as temp:
            proc,mount=fixture(Path(temp),'/system.slice/docker-test.scope','/')
            own=mount/'system.slice/docker-test.scope';own.mkdir(parents=True)
            (mount/'memory.current').write_text('HOST_WRONG_SCOPE');(own/'memory.current').write_text('456\n')
            value=diagnostic.cgroup_snapshot(proc);self.assertEqual(str(own),value['directory']);self.assertEqual('456\n',value['files']['memory.current']['raw'])

    def test_unresolved_or_ambiguous_scope_stays_null(self):
        for kind in ('v1','ambiguous','wrong-root'):
            with tempfile.TemporaryDirectory() as temp:
                proc,mount=fixture(Path(temp),'/other.scope' if kind=='wrong-root' else '/')
                if kind=='v1':(proc/'self/cgroup').write_text('5:memory:/legacy\n')
                if kind=='ambiguous':
                    f=proc/'self/mountinfo';f.write_text(f.read_text()*2)
                value=diagnostic.cgroup_snapshot(proc);self.assertIsNotNone(value['scope_error'])
                self.assertTrue(all(v['raw'] is None for v in value['files'].values()))

    def test_verbose_global_and_session_before_single_constructor_after_even_failure(self):
        for failure in (None,'constructor'):
            with tempfile.TemporaryDirectory() as temp:
                out=Path(temp)/'out';fake=FakeOrt(failure)
                with patch.object(diagnostic,'cgroup_snapshot',side_effect=[{'phase':'before','memory.current':None},{'phase':'after','memory.current':None}]) as capture:
                    if failure:
                        with self.assertRaises(RuntimeError):diagnostic.construct_only(request(out),fake,out)
                    else:diagnostic.construct_only(request(out),fake,out)
                self.assertEqual(2,capture.call_count);self.assertEqual(1,fake.calls)
                self.assertEqual('before',json.loads((out/'cgroup-before.json').read_text())['phase']);self.assertEqual('after',json.loads((out/'cgroup-after.json').read_text())['phase'])
                result=json.loads((out/'result.json').read_text());self.assertEqual(0,result['Session_Run_calls']);self.assertEqual(diagnostic.DIAGNOSTICS,result['diagnostics'])

    def test_fresh_diagnostic_scope_and_logging_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);req=p/'request.json';rel=p/'release.json'
            def bind(value):
                req.write_text(json.dumps(value));rel.write_text(json.dumps({'approved':True,'permission':'one_vocoder_verbose_cgroup_constructor_no_Run','request_sha256':diagnostic.sha(req),'worker_sha256':diagnostic.sha(diagnostic.__file__),'output_dir':value['output_dir']}))
            value=request(p/'out');bind(value);self.assertEqual('vocoder',diagnostic.authorize(req,rel)['component'])
            for change in ('component','diagnostics'):
                changed=copy.deepcopy(value)
                if change=='component':changed['component']='text'
                else:changed['diagnostics']['global_log_severity']=2
                bind(changed)
                with self.assertRaises(ValueError):diagnostic.authorize(req,rel)
        self.assertNotIn('onnxruntime',sys.modules)


if __name__=='__main__':unittest.main()

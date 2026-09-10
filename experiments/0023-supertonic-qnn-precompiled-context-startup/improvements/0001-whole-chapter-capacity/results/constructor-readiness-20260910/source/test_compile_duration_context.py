import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import compile_duration_context as worker


class Options:
    def __init__(self):self.config={}
    def add_session_config_entry(self,key,value):self.config[key]=value


class FakeOrt:
    __version__='1.27.1'
    SessionOptions=Options
    ExecutionMode=types.SimpleNamespace(ORT_SEQUENTIAL='sequential')
    GraphOptimizationLevel=types.SimpleNamespace(ORT_ENABLE_ALL='all')
    def __init__(self,fail=None):self.calls=0;self.fail=fail
    def InferenceSession(self,source,sess_options,providers):
        self.calls+=1;self.options=sess_options;self.providers=providers
        if self.fail=='constructor':raise RuntimeError('synthetic constructor failure')
        from onnx import helper,TensorProto as TP,save_model
        path=Path(sess_options.config['ep.context_file_path']);binary=path.with_name('duration-context_qnn.bin')
        if self.fail!='missing':
            binary.write_bytes(b'SYNTHETIC CONTEXT NOT QNN')
            node=helper.make_node('EPContext',[v['name'] for v in worker.INPUTS],['duration'],domain='com.microsoft',embed_mode=1 if self.fail=='embedded' else 0,ep_cache_context=binary.name)
            ins=[helper.make_tensor_value_info(v['name'],TP.INT64 if v['type']=='tensor(int64)' else TP.FLOAT,v['shape']) for v in worker.INPUTS]
            outs=[helper.make_tensor_value_info('duration',TP.FLOAT,[1])]
            model=helper.make_model(helper.make_graph([node],'synthetic',ins,outs))
            save_model(model,str(path))
        def rows(values):return [types.SimpleNamespace(**v) for v in values]
        inputs=list(worker.INPUTS)
        if self.fail=='io':inputs=[{**inputs[0],'shape':[1,239]},*inputs[1:]]
        class Session:
            def get_inputs(self):return rows(inputs)
            def get_outputs(self):return rows(worker.OUTPUTS)
            def get_providers(s):return ['CPUExecutionProvider'] if self.fail=='provider' else ['QNNExecutionProvider','CPUExecutionProvider']
            def run(self,*args,**kwargs):raise AssertionError('FORWARD IS FORBIDDEN')
        return Session()


def request(output):
    return {'component':'duration','source':{'path':'synthetic-only'},'output_dir':str(output),'backend_path':'fake-no-native.so','ort_version':'1.27.1','qairt_version':'2.49.0.260730','expected_inputs':worker.INPUTS,'expected_outputs':worker.OUTPUTS,'provider_options':worker.PROVIDER,'session_run_calls_allowed':0,'constructor_calls_allowed':1,'mock':True,'worker_sha256':worker.sha(worker.__file__)}


class ConstructorTests(unittest.TestCase):
    def test_mock_constructor_options_artifacts_io_and_no_run(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'out';fake=FakeOrt();result=worker.construct_only(request(out),fake,out)
            self.assertEqual(1,fake.calls);self.assertEqual(0,result['Session_Run_calls']);self.assertTrue(result['mock'])
            self.assertEqual('1',fake.options.config['session.disable_cpu_ep_fallback']);self.assertEqual('0',fake.options.config['ep.context_embed_mode'])
            self.assertEqual('43',fake.providers[0][1]['soc_model']);self.assertEqual('0',fake.providers[0][1]['offload_graph_io_quantization'])
            self.assertEqual(worker.INPUTS,result['actual_inputs']);self.assertEqual('EPContext',result['external_context']['node_op'])
            self.assertTrue((out/'constructor-receipt.json').exists())

    def test_failures_retained_without_retry(self):
        for failure in ('constructor','missing','embedded','io','provider'):
            with tempfile.TemporaryDirectory() as temp:
                out=Path(temp)/'out';fake=FakeOrt(failure)
                with self.assertRaises(Exception):worker.construct_only(request(out),fake,out)
                self.assertEqual(1,fake.calls)
                result=json.loads((out/'result.json').read_text());self.assertEqual('error',result['status']);self.assertEqual(0,result['Session_Run_calls'])
                if failure not in ('constructor','missing'):self.assertTrue((out/'duration-context_qnn.bin').exists())

    def test_no_overwrite_or_second_constructor(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'out';fake=FakeOrt();worker.construct_only(request(out),fake,out)
            with self.assertRaises(FileExistsError):worker.construct_only(request(out),fake,out)
            self.assertEqual(1,fake.calls)

    def test_exact_release_bound_to_request_worker_and_output(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);req=p/'request.json';release=p/'release.json';req.write_text(json.dumps(request(p/'out')))
            data={'approved':True,'permission':'one_duration_EPContext_constructor_no_Run','request_sha256':worker.sha(req),'worker_sha256':worker.sha(worker.__file__),'output_dir':str(p/'out')}
            release.write_text(json.dumps(data));self.assertEqual('duration',worker.authorize(req,release)['component'])
            for key in data:
                changed=dict(data);changed[key]=None;release.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):worker.authorize(req,release)

    def test_plan_and_unapproved_execute_never_import_ort(self):
        with tempfile.TemporaryDirectory() as temp:
            req=Path(temp)/'request.json';req.write_text(json.dumps(request(Path(temp)/'out')))
            run=subprocess.run([sys.executable,str(ROOT/'tools/compile_duration_context.py'),'--request',str(req)],capture_output=True,text=True)
            self.assertEqual(0,run.returncode);self.assertIn('PLAN_ONLY_NO_NATIVE_IMPORT',run.stdout)
            run=subprocess.run([sys.executable,str(ROOT/'tools/compile_duration_context.py'),'--request',str(req),'--execute'],capture_output=True,text=True)
            self.assertNotEqual(0,run.returncode);self.assertIn('requires separate exact release',run.stderr)
            self.assertNotIn('onnxruntime',sys.modules)

    def test_host_launcher_plan_and_rejection_never_call_docker(self):
        import run_duration_constructor as launcher
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);req=p/'request.json';release=p/'release.json'
            value=request(p/'phase/data');value.update(phase_dir=str(p/'phase'),approval_path=str(release),container_name='synthetic',sdk_root='/sdk',environment={'OMP_NUM_THREADS':'4'},docker_image_id='sha256:synthetic')
            req.write_text(json.dumps(value));release.write_text('{}')
            command=launcher.command(value,req,release)
            self.assertIn('--network=none',command);self.assertIn('--cpus=4',command);self.assertIn('--pull=never',command)
            self.assertEqual('docker',command[0]);self.assertIn('--execute',command)
            with patch.object(launcher.subprocess,'run',side_effect=AssertionError('Docker execution forbidden')):
                with patch.object(sys,'argv',['launcher','--request',str(req),'--release',str(release),'--execute']):
                    with self.assertRaises(ValueError):launcher.main()
            self.assertFalse((p/'phase').exists())

    def test_wrong_version_has_zero_constructor_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'out';fake=FakeOrt();fake.__version__='1.17.1'
            with self.assertRaises(ValueError):worker.construct_only(request(out),fake,out)
            self.assertEqual(0,fake.calls)


if __name__=='__main__':unittest.main()

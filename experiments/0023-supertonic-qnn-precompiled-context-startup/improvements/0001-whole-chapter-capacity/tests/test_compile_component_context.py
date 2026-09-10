import copy
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
import compile_component_context as worker
import run_component_constructor as launcher


class Options:
    def __init__(self):self.config={}
    def add_session_config_entry(self,key,value):self.config[key]=value


class FakeOrt:
    __version__='1.27.1'
    SessionOptions=Options
    ExecutionMode=types.SimpleNamespace(ORT_SEQUENTIAL='sequential')
    GraphOptimizationLevel=types.SimpleNamespace(ORT_ENABLE_ALL='all')
    def __init__(self,component,fail=None):self.component=component;self.fail=fail;self.calls=0
    def InferenceSession(self,source,sess_options,providers):
        self.calls+=1;self.options=sess_options;self.providers=providers
        if self.fail=='constructor':raise RuntimeError('synthetic constructor failure')
        from onnx import helper,TensorProto as TP,save_model
        inputs,outputs=copy.deepcopy(worker.SPECS[self.component])
        path=Path(sess_options.config['ep.context_file_path']);binary=path.with_name(self.component+'-context_qnn.bin')
        if self.fail!='missing':
            binary.write_bytes(b'SYNTHETIC ONLY; NOT A QNN CONTEXT')
            cache='other.bin' if self.fail=='reference' else binary.name
            node=helper.make_node('EPContext',[v['name'] for v in inputs],[v['name'] for v in outputs],domain='com.microsoft',embed_mode=1 if self.fail=='embedded' else 0,ep_cache_context=cache)
            def infos(values):return [helper.make_tensor_value_info(v['name'],TP.INT64 if v['type']=='tensor(int64)' else TP.FLOAT,v['shape']) for v in values]
            descriptor_inputs=copy.deepcopy(inputs)
            if self.fail=='descriptor_io':descriptor_inputs[0]['shape'][-1]=17
            save_model(helper.make_model(helper.make_graph([node],'synthetic',infos(descriptor_inputs),infos(outputs))),str(path))
        if self.fail=='session_io':inputs[0]['shape'][-1]=17
        def rows(values):return [types.SimpleNamespace(**v) for v in values]
        class Session:
            def get_inputs(self):return rows(inputs)
            def get_outputs(self):return rows(outputs)
            def get_providers(s):return ['CPUExecutionProvider'] if self.fail=='provider' else ['QNNExecutionProvider','CPUExecutionProvider']
            def run(self,*a,**k):raise AssertionError('FORWARD FORBIDDEN')
        return Session()


def request(component,output):
    inputs,outputs=worker.SPECS[component]
    return {'component':component,'source':{'path':'synthetic-only'},'output_dir':str(output),'backend_path':'fake-no-native.so','ort_version':'1.27.1','qairt_version':'2.49.0.260730','expected_inputs':inputs,'expected_outputs':outputs,'io_sha256':worker.io_sha256(component),'provider_options':worker.PROVIDER,'session_run_calls_allowed':0,'constructor_calls_allowed':1,'mock':True,'worker_sha256':worker.sha(worker.__file__)}


def release(req_path,value):
    return {'approved':True,'permission':f"one_{value['component']}_EPContext_constructor_no_Run",'request_sha256':worker.sha(req_path),'worker_sha256':worker.sha(worker.__file__),'output_dir':value['output_dir']}


class RemainingConstructorTests(unittest.TestCase):
    def test_three_mock_constructor_artifact_io_provider_gates_no_run(self):
        for component in worker.SPECS:
            with self.subTest(component=component),tempfile.TemporaryDirectory() as temp:
                out=Path(temp)/'out';fake=FakeOrt(component);result=worker.construct_only(request(component,out),fake,out)
                self.assertEqual(1,fake.calls);self.assertEqual(0,result['Session_Run_calls']);self.assertTrue(result['mock'])
                self.assertEqual(worker.SPECS[component][0],result['actual_inputs']);self.assertEqual(worker.SPECS[component][1],result['actual_outputs'])
                self.assertEqual('1',fake.options.config['session.disable_cpu_ep_fallback']);self.assertEqual('0',fake.options.config['ep.context_embed_mode'])
                self.assertEqual('43',fake.providers[0][1]['soc_model']);self.assertEqual(worker.io_sha256(component),result['io_sha256'])
                self.assertTrue((out/'constructor-receipt.json').exists())

    def test_all_components_retain_failures_without_retry(self):
        for component in worker.SPECS:
            for failure in ('constructor','missing','embedded','reference','descriptor_io','session_io','provider'):
                with self.subTest(component=component,failure=failure),tempfile.TemporaryDirectory() as temp:
                    out=Path(temp)/'out';fake=FakeOrt(component,failure)
                    with self.assertRaises(Exception):worker.construct_only(request(component,out),fake,out)
                    self.assertEqual(1,fake.calls);result=json.loads((out/'result.json').read_text())
                    self.assertEqual('error',result['status']);self.assertEqual(0,result['Session_Run_calls'])
                    if failure!='constructor':self.assertTrue((out/'constructor-receipt.json').exists())
                    if failure not in ('constructor','missing'):self.assertTrue((out/f'{component}-context_qnn.bin').exists())

    def test_no_overwrite_or_second_constructor_each(self):
        for component in worker.SPECS:
            with tempfile.TemporaryDirectory() as temp:
                out=Path(temp)/'out';fake=FakeOrt(component);worker.construct_only(request(component,out),fake,out)
                with self.assertRaises(FileExistsError):worker.construct_only(request(component,out),fake,out)
                self.assertEqual(1,fake.calls)

    def test_exact_component_request_worker_output_and_io_release(self):
        for component in worker.SPECS:
            with tempfile.TemporaryDirectory() as temp:
                p=Path(temp);req=p/'request.json';rel=p/'release.json';value=request(component,p/'out');req.write_text(json.dumps(value));binding=release(req,value)
                rel.write_text(json.dumps(binding));self.assertEqual(component,worker.authorize(req,rel)['component'])
                for key in binding:
                    changed=dict(binding);changed[key]=None;rel.write_text(json.dumps(changed))
                    with self.assertRaises(ValueError):worker.authorize(req,rel)
                value['io_sha256']='bad';req.write_text(json.dumps(value));rel.write_text(json.dumps(release(req,value)))
                with self.assertRaises(ValueError):worker.authorize(req,rel)

    def test_duration_not_eligible(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);req=p/'request.json';rel=p/'release.json';value=request('text',p/'out');value['component']='duration';req.write_text(json.dumps(value));rel.write_text(json.dumps(release(req,value)))
            with self.assertRaisesRegex(ValueError,'no duration retry'):worker.authorize(req,rel)

    def test_plan_and_unapproved_execute_do_not_import_runtime(self):
        for component in worker.SPECS:
            with tempfile.TemporaryDirectory() as temp:
                req=Path(temp)/'request.json';req.write_text(json.dumps(request(component,Path(temp)/'out')))
                command=[sys.executable,str(ROOT/'tools/compile_component_context.py'),'--request',str(req)]
                run=subprocess.run(command,capture_output=True,text=True);self.assertEqual(0,run.returncode);self.assertIn('PLAN_ONLY_NO_NATIVE_IMPORT',run.stdout)
                run=subprocess.run(command+['--execute'],capture_output=True,text=True);self.assertNotEqual(0,run.returncode);self.assertIn('requires separate exact release',run.stderr)
        self.assertNotIn('onnxruntime',sys.modules)

    def test_launcher_plan_and_rejection_have_no_docker_calls(self):
        for component in worker.SPECS:
            with tempfile.TemporaryDirectory() as temp:
                p=Path(temp);req=p/'request.json';rel=p/'release.json';value=request(component,p/'phase/data')
                value.update(phase_dir=str(p/'phase'),approval_path=str(rel),container_name='synthetic-'+component,sdk_root='/sdk',environment={k:str(p/'phase/scratch') for k in ('TMPDIR','QAIRT_TMP_DIR','TMP','TEMP')},docker_image_id='sha256:synthetic')
                req.write_text(json.dumps(value));rel.write_text('{}');argv=launcher.command(value,req,rel)
                for argument in ('--network=none','--cpus=4','--pull=never','--memory=8g','--memory-swap=8g'):self.assertIn(argument,argv)
                for key,val in value['environment'].items():self.assertIn(key+'='+val,argv)
                with patch.object(launcher.subprocess,'run',side_effect=AssertionError('Docker forbidden')):
                    with patch.object(sys,'argv',['launcher','--request',str(req),'--release',str(rel),'--execute']):
                        with self.assertRaises(ValueError):launcher.main()
                self.assertFalse((p/'phase').exists())

    def test_wrong_ort_version_has_zero_constructor_calls(self):
        for component in worker.SPECS:
            with tempfile.TemporaryDirectory() as temp:
                out=Path(temp)/'out';fake=FakeOrt(component);fake.__version__='1.17.1'
                with self.assertRaises(ValueError):worker.construct_only(request(component,out),fake,out)
                self.assertEqual(0,fake.calls)

    def test_saved_requests_only_component_scope_diff_same_runtime_and_bounds(self):
        base=json.loads((ROOT/'protocol/next-constructor-request-disk-scratch.json').read_text())
        batch=json.loads((ROOT/'protocol/remaining-constructors/batch.NOT_APPROVED.json').read_text())
        allowed={'component','source','expected_inputs','expected_outputs','io_sha256','phase_dir','output_dir','approval_path','container_name','worker_sha256','launcher_sha256','environment'}
        phases=[];approvals=[];containers=[]
        for entry in batch['requests']:
            path=ROOT/entry['path'];value=json.loads(path.read_text());self.assertEqual(entry['sha256'],worker.sha(path))
            self.assertEqual(worker.io_sha256(value['component']),value['io_sha256'])
            self.assertEqual({k:v for k,v in base.items() if k not in allowed},{k:v for k,v in value.items() if k not in allowed})
            for key,val in base['environment'].items():
                self.assertEqual(str(Path(value['phase_dir'])/'scratch') if key in ('TMPDIR','QAIRT_TMP_DIR','TMP','TEMP') else val,value['environment'][key])
            self.assertFalse(json.loads((ROOT/entry['release_template']).read_text())['approved'])
            phases.append(value['phase_dir']);approvals.append(value['approval_path']);containers.append(value['container_name'])
        for values in (phases,approvals,containers):self.assertEqual(3,len(set(values)))
        self.assertNotIn(base['phase_dir'],phases);self.assertNotIn(base['approval_path'],approvals);self.assertNotIn(base['container_name'],containers)
        self.assertTrue(batch['serial']);self.assertTrue(batch['stop_on_first_failure']);self.assertEqual(0,batch['Session_Run_calls_allowed'])


if __name__=='__main__':unittest.main()

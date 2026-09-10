import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import compare_duration_padding_cpu as worker


def arrays():
    ids=np.zeros((1,2048),dtype=np.int64);ids[:,:1333]=np.arange(1333)
    mask=np.zeros((1,1,2048),dtype=np.float32);mask[:,:,:1333]=1
    return {'text_ids':ids,'text_mask':mask,'style_dp':np.arange(128,dtype=np.float32).reshape(1,8,16)}


def fake(providers=None,nonfinite=False):
    calls=[];sessions=[]
    class Session:
        def __init__(self,path,sess_options,providers,enable_fallback):
            assert providers==['CPUExecutionProvider'] and enable_fallback is False;sessions.append(path)
        def get_providers(self):return providers or ['CPUExecutionProvider']
        def get_inputs(self):return [SimpleNamespace(name='text_ids',type='tensor(int64)',shape=['batch_size','text_length'])]
        def get_outputs(self):return [SimpleNamespace(name='duration',type='tensor(float)',shape=[1])]
        def run(self,names,feed):
            calls.append({k:v.copy() for k,v in feed.items()});assert names==['duration']
            return [np.array([np.nan if nonfinite else 100.0 if feed['text_ids'].shape[-1]==1333 else 30.0],dtype=np.float32)]
    return SimpleNamespace(SessionOptions=SimpleNamespace,ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL=0),GraphOptimizationLevel=SimpleNamespace(ORT_ENABLE_ALL=99),InferenceSession=Session),sessions,calls


class DurationPairTests(unittest.TestCase):
    def test_one_session_two_exact_cases_and_raw_outputs(self):
        ort,sessions,calls=fake();data=arrays();result={'Run_calls_attempted':0,'cases':[]}
        with tempfile.TemporaryDirectory() as temp:
            worker.run_pair(ort,np,{'model':{'path':'FAKE_ONLY'},'case_order':[1333,2048]},data,Path(temp),result)
            self.assertEqual(['FAKE_ONLY'],sessions);self.assertEqual([1333,2048],[v['text_ids'].shape[-1] for v in calls]);self.assertEqual(2,result['Run_calls_attempted'])
            np.testing.assert_array_equal(calls[0]['text_ids'],calls[1]['text_ids'][:,:1333]);np.testing.assert_array_equal(calls[0]['style_dp'],calls[1]['style_dp'])
            self.assertEqual(2,len(list(Path(temp).glob('*.npy'))));self.assertEqual(-70,result['comparison']['padded_minus_active_seconds']);self.assertIsNone(result['comparison']['native_DP_scalar'])

    def test_nonCPU_provider_is_rejected_before_forward(self):
        ort,_,calls=fake(['CPUExecutionProvider','AzureExecutionProvider'])
        with tempfile.TemporaryDirectory() as temp,self.assertRaises(ValueError):worker.run_pair(ort,np,{'model':{'path':'FAKE'},'case_order':[1333,2048]},arrays(),Path(temp),{'Run_calls_attempted':0,'cases':[]})
        self.assertEqual([],calls)

    def test_invalid_padding_or_style_fails_before_session(self):
        for kind in ['ids','mask','style']:
            data=arrays()
            if kind=='ids':data['text_ids'][0,2047]=1
            elif kind=='mask':data['text_mask'][0,0,1333]=1
            else:data['style_dp'][0,0,0]=np.nan
            with self.assertRaises(ValueError):worker.validate_arrays(np,data)

    def test_both_nonfinite_outputs_preserved_before_classification(self):
        ort,_,calls=fake(nonfinite=True);result={'Run_calls_attempted':0,'cases':[]}
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):worker.run_pair(ort,np,{'model':{'path':'FAKE'},'case_order':[1333,2048]},arrays(),Path(temp),result)
            self.assertEqual(2,len(calls));self.assertEqual(2,len(list(Path(temp).glob('*.npy'))));self.assertTrue(all(v['duration_seconds'] is None for v in result['cases']))

    def test_missing_or_mismatched_release_denied_without_runtime_import(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'request.json').write_text(json.dumps({'output_dir':str(root/'out')}));(root/'release.json').write_text('{}')
            with self.assertRaises(ValueError):worker.authorize(root/'request.json',root/'release.json')
        self.assertNotIn('onnxruntime',sys.modules)


if __name__=='__main__':unittest.main()

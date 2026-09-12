import importlib
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
r=importlib.import_module('declared_dlc_reference')
i=importlib.import_module('matched_prefill_inputs')
w=importlib.import_module('audit_active_export_weights')


def tensor(shape,dtype='uFxp_16',scale=1.,offset=0,bits=16,axis=None):
    t={'dimensions':shape,'datatype':dtype}
    if 'Fxp_' in dtype:t['grid']={'axis':axis,'scale':[scale],'offset':[offset],'bitwidths':[bits]}
    return t


def op(typ,attrs):return {'type':typ,'attrs':attrs}


class ArithmeticTests(unittest.TestCase):
    def test_effective_signed4_width_not_int8_container_sign(self):
        t=tensor([4],'sFxp_8',.5,0,4)
        np.testing.assert_array_equal(r.decode(np.array([0,7,8,15],dtype=np.int8),t),[0,3.5,-4,-.5])
        np.testing.assert_array_equal(r.decode(r.encode(np.array([0,3.5,-4,-.5]),t),t),[0,3.5,-4,-.5])

    def test_tiled_dequant_is_equal_without_retaining_a_float_model(self):
        raw=np.arange(12,dtype=np.int8).reshape(3,4)
        t={'dimensions':[3,4],'datatype':'sFxp_8','grid':{'axis':0,'scale':[.5,.25,.125],'offset':[0,0,0],'bitwidths':[4,4,4]}}
        np.testing.assert_array_equal(r.decode(raw,t,max_temporary_elements=4),r.decode(raw,t,max_temporary_elements=100))

    def test_declared_rounding_and_float16_boundaries(self):
        np.testing.assert_array_equal(r.encode(np.array([-.5,.5,1.5,65536]),tensor([4])),[0,0,2,65535])
        t=tensor([1],'Float_16');self.assertEqual(r.encode([1.0001],t).dtype,np.float16)
        self.assertEqual(r.encode([1.0001],t)[0],1.)

    def test_all_arithmetic_families_on_tiny_inputs(self):
        x=np.array([[1.,2.],[3.,4.]],dtype=np.float32)
        for code,fn in [(0,np.add),(2,np.divide),(13,np.multiply),(16,np.power),(18,np.subtract)]:
            np.testing.assert_allclose(r.logical_op(op('Eltwise_Binary',{'operation':code}),[x,x],[2,2]),fn(x,x))
        np.testing.assert_array_equal(r.logical_op(op('MatMul',{'transpose_in0':False,'transpose_in1':False}),[x,x],[2,2]),x@x)
        np.testing.assert_array_equal(r.logical_op(op('FullyConnected',{}),[x,x],[2,2]),x@x.T)
        conv={'stride':[1,1],'dilation':[1,1],'group':1,'pad_amount':[[0,0],[0,0]]}
        np.testing.assert_array_equal(r.logical_op(op('Conv2d',conv),[x.reshape(1,1,2,2),x.reshape(1,1,2,2),np.zeros(2,dtype=np.float32)],[1,1,2,2]),(x@x).reshape(1,1,2,2))
        np.testing.assert_allclose(r.logical_op(op('RmsNorm',{'axes':[1],'epsilon':0.}),[x,np.ones(2),np.zeros(2)],[2,2]),x/np.sqrt(np.mean(x*x,axis=1,keepdims=True)))
        soft=r.logical_op(op('Softmax',{'axis':1,'beta':1.}),[x],[2,2]);np.testing.assert_allclose(soft.sum(1),[1,1])
        from math import erf,sqrt
        z=np.array([-1,0,1],dtype=np.float32)
        np.testing.assert_allclose(r.logical_op(op('ElementWiseNeuron',{'operation':1}),[z],[3]),[v*.5*(1+erf(v/sqrt(2))) for v in z],rtol=1e-6)
        np.testing.assert_array_equal(r.logical_op(op('ElementWiseNeuron',{'operation':8}),[z],[3]),np.tanh(z))
        np.testing.assert_array_equal(r.logical_op(op('Reduce',{'reduce_type':'ReduceMean','axes':[1],'keep_dims':True}),[x],[2,1]),[[1.5],[3.5]])

    def test_memory_operations_and_explicit_gaps(self):
        x=np.arange(4).reshape(2,2)
        np.testing.assert_array_equal(r.logical_op(op('Reshape',{}),[x],[4]),x.reshape(4))
        np.testing.assert_array_equal(r.logical_op(op('Transpose',{'perm':[1,0]}),[x],[2,2]),x.T)
        np.testing.assert_array_equal(r.logical_op(op('Concat',{'axis':0}),[x,x],[4,2]),np.concatenate([x,x]))
        np.testing.assert_array_equal(r.logical_op(op('Gather',{'axis':0}),[x,np.array([1])],[1,2]),x[[1]])
        attrs={'ranges':[[0,1,1],[0,2,1]],'begin_mask':0,'end_mask':0,'new_axes_mask':0,'shrink_axes':0}
        np.testing.assert_array_equal(r.logical_op(op('StridedSlice',attrs),[x],[1,2]),x[:1])
        self.assertIs(r.logical_op(op('Cast',{}),[x],[2,2]),x)
        self.assertIs(r.logical_op(op('Convert',{}),[x],[2,2]),x)
        with self.assertRaises(ValueError):r.logical_op(op('Unknown',{}),[x],[2,2])

    def test_small_streamed_policy_and_default_full_graph_block(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);np.save(p/'w.npy',np.array([[1,15],[2,0]],dtype=np.int8))
            tx=tensor([1,2],offset=-10);tw=tensor([2,2],'sFxp_8',bits=4);tw['static']={'file':'w.npy'};tq=tensor([1,2],offset=-10);tf=tensor([1,2],'Float_16')
            policy={'tensors':{'x':tx,'w':tw,'q':tq,'f':tf},'input_names':['x'],'output_names':['f'],'operators':[{'index':0,'name':'matmul','type':'MatMul','inputs':['x','w'],'outputs':['q'],'attrs':{'transpose_in0':False,'transpose_in1':False}},{'index':1,'name':'convert','type':'Convert','inputs':['q'],'outputs':['f'],'attrs':{}}]}
            file=p/'policy.json';file.write_text(json.dumps(policy));ref=r.DeclaredDlcReference(file)
            np.testing.assert_array_equal(ref.run_encoded({'x':np.array([[11,12]],dtype=np.uint16)})['f'],[[5,-1]])
            ref.policy['operators']*=17
            with self.assertRaises(PermissionError):ref.run_encoded({})
            with self.assertRaises(PermissionError):i.run_reference_prefill('missing','missing','missing')


class InputLedgerTests(unittest.TestCase):
    def test_full_history_and_mask_counts(self):
        c=i.chunks();self.assertEqual(len(c),16);self.assertEqual(c[-1]['real_rows'],9);self.assertEqual(c[-1]['final_valid_row'],8)
        self.assertEqual(sum(x['real_rows'] for x in c),1929)
        gm,sm=i.masks(1920,9);self.assertEqual(np.count_nonzero(gm[0,0,8]),1929);self.assertEqual(np.count_nonzero(sm[0,0,8]),512)
        self.assertFalse(gm[0,0,9:].any());self.assertFalse(sm[0,0,9:].any())
        np.testing.assert_array_equal(i.cache_positions(640,512)[:128],np.arange(512,640))

    def test_actual_cache_outputs_carried_across_ring_wrap(self):
        caches={'swa_key_0_h0_in':np.zeros((1,1,1,4),dtype=np.uint16)}
        i.advance_cache(caches,{'swa_key_0_h0_out':np.array([[[[1,2,3]]]],dtype=np.uint16)},{'start':0,'real_rows':3})
        i.advance_cache(caches,{'swa_key_0_h0_out':np.array([[[[4,5,6]]]],dtype=np.uint16)},{'start':3,'real_rows':3})
        np.testing.assert_array_equal(caches['swa_key_0_h0_in'].ravel(),[5,6,3,4])

    def test_bound_rope_quantizer_uses_cos_grid_for_sine(self):
        g={'scale':[3.051804378628731e-05],'offset':[-32768]};c,s=i.rope_tables([0],256,1e6,64,g)
        self.assertTrue(np.all(s==32768));self.assertTrue(np.all(c==65535))
        self.assertEqual(i.requant_lut(np.array([0,255],dtype=np.uint8),{'scale':1.,'offset':0},{'scale':[1.],'offset':[0]}).tolist(),[0,255])

    def test_export_mapping_per_head_and_projection(self):
        x=w.source_mapping('model.model.layers.4.self_attn.q_proj_sha.3.weight',[512,1536,1,1])
        self.assertEqual(x['start_row'],1536);self.assertIn('layers.4.self_attn.q_proj.weight',x['source'])
        self.assertTrue(w.source_mapping('val_42',[1536,8960])['transpose'])


class CaptureReadinessTests(unittest.TestCase):
    def test_source_transform_only_adds_observation(self):
        c=importlib.import_module('prepare_paired_prefill_capture')
        source='header\n  return true;\n}\n\nbool QnnNspModel::setupInput(const InferenceStep& step,\n                             uint32_t start,\n                             std::vector<int32_t>& tokens,\n                             std::vector<size_t>& tokenNumPerBatch,\nbody\n  const size_t size = m_vocab_size * static_cast<size_t>(count);\n  __TRACE("qnn-htp: getLogits Returning {}*{} from [{}]", count, m_vocab_size, step.str());\ntail\n'
        patched=c.patch(source)
        restored=patched.removeprefix('#include "qualla/prefill_capture.hpp"\n').replace(c.INPUT_HOOK,'').replace(c.OUTPUT_HOOK,'')
        self.assertEqual(restored,source)
        self.assertNotIn('sampler.process',c.INPUT_HOOK+c.OUTPUT_HOOK)
        self.assertIn('getBuffer(tensor, true, buffer_idx)',c.INPUT_HOOK)
        self.assertIn('step.n_process == 9 && count == 1',c.OUTPUT_HOOK)
        self.assertNotIn('past_key',c.INPUT_HOOK)

    def test_phone_plan_is_no_permission_and_never_restores_old_APKs(self):
        c=importlib.import_module('phone_paired_prefill_capture');m,receipt=c.load_lifecycle({},False)
        p=m.plan();self.assertEqual(p['adb_calls'],0);self.assertFalse(p['phone_permission_granted_by_plan'])
        self.assertEqual(p['process_deadline_seconds'],300);self.assertTrue(p['host_reference_uses_own_caches'])
        source,shell,_,_=c.materialize_sources();self.assertIn('GEMMA_PREFILL_CAPTURE_DIR',shell);self.assertIn('ulimit -v 8388608',shell)
        expected={'dev.vibevoice.podcast.internal':'a'*64,'dev.vibevoice.podcast.internal.test':'b'*64}
        data=('APK\tdev.vibevoice.podcast.internal\t'+'a'*64+'\nAPK\tdev.vibevoice.podcast.internal.test\t'+'b'*64+'\nPID\tdev.vibevoice.podcast.internal:generation\t\nPID\tdev.vibevoice.podcast.internal.test\t\n').encode()
        self.assertTrue(c.validate_app(data,expected)['idle_main_process_not_a_generation_claim'])
        with self.assertRaises(ValueError):c.validate_app(data,{'wrong':'c'*64})
        with self.assertRaises(ValueError):c.validate_app(data.replace(b':generation\t\n',b':generation\t123\n'),expected)

    def test_actual_captured_inputs_replace_formula_but_not_host_cache(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);policy_dir=root/'policy-01';policy_dir.mkdir();src=root/'source';src.mkdir();cap=root/'capture';cap.mkdir()
            names=['inputs_embeds','per_layer_inputs','attention_mask','swa_attention_mask','position_ids_cos','position_ids_sin','swa_position_ids_cos','swa_position_ids_sin']
            policy={'tensors':{name:tensor([1]) for name in names}};policy['tensors']['logits']=tensor([1,1,262144])
            pf=policy_dir/'policy.json';pf.write_text(json.dumps(policy));np.save(src/'planned.npy',np.array([0],dtype=np.uint16));np.save(src/'initial.npy',np.array([123],dtype=np.uint16))
            ledger={'input_count':1929,'policy_sha256':i.sha(pf),'chunks':i.chunks(),'initial_caches':{'host_cache':{'file':'initial.npy','sha256':i.sha(src/'initial.npy')}}};events=[]
            for step in ledger['chunks']:
                step['input_files']={name:{'file':'planned.npy'} for name in names}
                for name in names:
                    file=f"{step['index']:02d}-input-{name}.raw";(cap/file).write_bytes(b'\x01\x00')
                    row={'phase':'input','step':step['index'],'name':name,'variant':128,'context':4096,'n_past':step['start'],'n_process':step['real_rows'],'n_valid_kv':step['start'],'past_idx':0,'new_idx':3968,'shape':[1],'datatype':'QNN_DATATYPE_UFIXED_POINT_16','scale':1.,'offset':0,'file':file,'bytes':2,'cache_tensor':False}
                    events.extend([{**row,'event':'begin'},{**row,'event':'complete'}])
            file='15-output-logits.raw';(cap/file).write_bytes(bytes(524288));row={'phase':'output','step':15,'name':'logits','file':file,'bytes':524288,'shape':[1,1,262144],'final_valid_row':8,'before_sampler_access':True,'cache_tensor':False,'variant':128,'context':4096,'n_past':1920,'n_process':9,'datatype':'QNN_DATATYPE_UFIXED_POINT_16','scale':1.,'offset':0};events.extend([{**row,'event':'begin'},{**row,'event':'complete'}]);(cap/'capture.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events));lp=src/'ledger.json';lp.write_text(json.dumps(ledger))
            with mock.patch.object(i,'ROOT',root):bound=i.bind_captured_noncache(cap,lp,root/'bound')
            self.assertTrue(bound['actual_noncache_capture_bound'])
            self.assertEqual(np.load(root/'bound/initial.npy').tolist(),[123])
            self.assertEqual(np.load(root/'bound/chunk-00/inputs_embeds.npy').tolist(),[1])
            self.assertEqual(sum(v['different_elements_from_host_formula'] for v in bound['host_formula_comparison']),128)
            bad={**row,'phase':'input','step':0,'name':'past_key_4_h0_in','event':'complete'}
            with (cap/'capture.jsonl').open('a') as f:f.write(json.dumps(bad)+'\n')
            with mock.patch.object(i,'ROOT',root),self.assertRaises(ValueError):i.bind_captured_noncache(cap,lp,root/'rejected')


if __name__=='__main__':unittest.main()

import importlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
n=importlib.import_module('native_qat_checkpoint')


class NativeQatValidationTests(unittest.TestCase):
    def test_known_block_shape_is_strict_not_blanket_quant_shape_bypass(self):
        key='model.language_model.embed_tokens_per_layer.embedding_scale'
        expected={key:{'shape':[262144,35],'dtype':'F32'}}
        self.assertTrue(n.compare_schema(expected,expected,[])['passed'])
        for shape in ([262144,1],[262144,34],[262143,35]):
            self.assertFalse(n.compare_schema(expected,{key:{'shape':shape,'dtype':'F32'}},[])['passed'])

    def test_missing_and_integer_dtype_changes_block(self):
        key='lm_head.weight';expected={key:{'shape':[262144,384],'dtype':'U8'}}
        self.assertFalse(n.compare_schema(expected,{},[])['passed'])
        self.assertFalse(n.compare_schema(expected,{key:{'shape':[262144,384],'dtype':'I8'}},[])['passed'])
        self.assertTrue(n.in_scope('lm_head'))

    def test_only_declared_native_unused_keys_are_accounted(self):
        key='model.language_model.layers.0.self_attn.k_cache_scale'
        source={key:{'shape':[],'dtype':'F32'}}
        self.assertFalse(n.compare_schema({},source,[])['passed'])
        self.assertTrue(n.compare_schema({},source,[r'.*\.k_cache_scale$'])['passed'])

    def test_saved_native_meta_validation_no_weights_or_forward(self):
        root=TRACK/'.local/native-qat-reference'
        old=json.loads((root/'meta-validation-01/validation.json').read_text())
        self.assertFalse(old['passed'])
        fixed=json.loads((root/'meta-validation-02/validation.json').read_text())
        self.assertTrue(fixed['passed'])
        self.assertEqual(fixed['missing'],[])
        self.assertEqual(fixed['unaccounted_source_keys'],[])
        self.assertEqual(fixed['shape_or_integer_dtype_mismatches'],[])
        self.assertFalse(fixed['native_variable_shape_binding']['model_modified'])
        self.assertEqual(fixed['quant_modules']['lm_head']['num_bits'],2)
        self.assertEqual(fixed['input_ids_sha256'],n.INPUT_SHA)
        self.assertEqual(fixed['input_ids_count'],1929)
        self.assertEqual(json.loads((root/'meta-validation-02/result.json').read_text())['model_forward_calls'],0)


class NativeQatTimeoutTests(unittest.TestCase):
    def test_consumed_one_forward_no_logits_and_owned_cleanup(self):
        r=json.loads((TRACK/'results/native-qat-prefill-checkpoint-01/result.json').read_text())
        self.assertTrue(r['strict_loaded_text_head_validation_passed'])
        self.assertEqual(r['validated_text_head_tensor_count'],1371)
        self.assertEqual(r['scope']['forward_attempts'],1)
        self.assertEqual(r['scope']['completed_forwards'],0)
        self.assertEqual(r['scope']['generate_calls'],0)
        self.assertEqual(r['guard']['actual_child_exit'],-15)
        self.assertEqual(r['guard']['stop_reason'],'wall_budget_with_cleanup_margin')
        self.assertTrue(r['guard']['child_reaped'])
        self.assertTrue(r['guard']['heavy_lock_released'])
        self.assertIsNone(r['logits']['native'])
        self.assertIsNone(r['logits']['float32'])
        self.assertIsNone(r['native_module_SRQ_execution_counts'])
        self.assertFalse(r['host_lock_policy']['future_admission_requirement'])

    def test_cost_descriptors_not_measured_throughput(self):
        r=json.loads((TRACK/'results/native-qat-prefill-checkpoint-01/offline-cost-assessment.json').read_text())
        self.assertEqual(r['quantized_linear_count'],276)
        self.assertEqual(r['combined_nominal_flops'],8521852993536)
        self.assertTrue(r['pad_embedding_property']['native_property_materializes_complete_table'])
        self.assertIsNone(r['saved_runtime']['process_IO_counters'])
        self.assertIsNone(r['host_cpu']['selected_BF16_gemm_kernel'])


class ObservationOnlyTraceTests(unittest.TestCase):
    def test_same_object_return_and_begin_is_flushed_before_call(self):
        from native_qat_cost_trace import CostTrace
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'trace.jsonl';t=CostTrace(p,tensor_type=bytes);value=object()
            def original():
                self.assertEqual(json.loads(p.read_text().splitlines()[0])['event'],'begin')
                return value
            self.assertIs(t.wrap('original',original)(),value)
            t.close();self.assertEqual([json.loads(s)['event'] for s in p.read_text().splitlines()],['begin','end'])

    def test_nested_timings_have_parent_and_non_double_counted_fields(self):
        from native_qat_cost_trace import CostTrace
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'trace.jsonl';t=CostTrace(p,tensor_type=bytes)
            inner=t.wrap('inner',lambda:object());outer=t.wrap('outer',lambda:inner())
            outer();t.close();rows=[json.loads(s) for s in p.read_text().splitlines()]
            begins={x['operation']:x for x in rows if x['event']=='begin'}
            ends={x['operation']:x for x in rows if x['event']=='end'}
            self.assertEqual(begins['inner']['parent'],begins['outer']['call'])
            self.assertEqual(ends['outer']['wall_ns'],ends['outer']['exclusive_wall_ns']+ends['inner']['wall_ns'])

    def test_property_dequant_and_forward_each_run_once_and_restore(self):
        from native_qat_cost_trace import CostTrace
        calls={};value=object()
        class Embedding:
            @property
            def weight(self):
                calls['property']=calls.get('property',0)+1
                return self._dequantize_weights('packed','scales')
            def _dequantize_weights(self,*args):
                calls['embedding_dequant']=calls.get('embedding_dequant',0)+1;return value
            def forward(self):
                calls['embedding_forward']=calls.get('embedding_forward',0)+1;return self.weight
        class Linear:
            def _dequantize_weights(self,*args):
                calls['linear_dequant']=calls.get('linear_dequant',0)+1;return value
            def forward(self):
                calls['linear_forward']=calls.get('linear_forward',0)+1;return self._dequantize_weights()
        class Model:
            def __init__(self):self.emb=Embedding();self.head=Linear()
            def named_modules(self):return [('',self),('emb',self.emb),('lm_head',self.head)]
            def forward(self):self.emb.forward();return self.head.forward()
        quant=SimpleNamespace(QuantizedEmbedding=Embedding,QuantizedLinear=Linear,apply_srq=lambda x:x)
        torch=SimpleNamespace(nn=SimpleNamespace(Linear=Linear,functional=SimpleNamespace(linear=lambda x:x)),matmul=lambda x:x)
        model=Model();prop=Embedding.weight;original_srq=quant.apply_srq
        with tempfile.TemporaryDirectory() as d:
            trace=CostTrace(Path(d)/'trace.jsonl',tensor_type=bytes)
            with trace.instrument(model,quant,torch):
                self.assertEqual(calls,{})  # installation did not evaluate .weight
                self.assertIs(model.forward(),value)
            self.assertEqual(set(calls.values()),{1})
            self.assertIs(Embedding.weight,prop);self.assertIs(quant.apply_srq,original_srq)
            self.assertNotIn('forward',model.__dict__);trace.close()

    def test_original_exception_and_trace_failure_do_not_change_function(self):
        from native_qat_cost_trace import CostTrace
        with tempfile.TemporaryDirectory() as d:
            t=CostTrace(Path(d)/'trace.jsonl',tensor_type=bytes);error=RuntimeError('same error')
            def original():raise error
            with self.assertRaises(RuntimeError) as caught:t.wrap('fails',original)()
            self.assertIs(caught.exception,error)
            t.file.close()
            value=object();self.assertIs(t.wrap('still runs',lambda:value)(),value)
            self.assertIsNotNone(t.logging_error)


if __name__=='__main__':unittest.main()

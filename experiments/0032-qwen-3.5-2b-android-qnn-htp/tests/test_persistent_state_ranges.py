from __future__ import annotations
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

TOOLS=Path(__file__).resolve().parents[1]/'tools'
sys.path.insert(0,str(TOOLS))
import audit_persistent_state_ranges as audit
from audit_conv_history_metadata import scalar_qdq


def node(name,target,source,scale=.01,zero=12):
    args=[{'name':'input','arg':{'as_tensor':{'name':source}}}]
    if target in (audit.Q,audit.DQ):
        args += [{'name':'scale','arg':{'as_float':scale}},{'name':'zero_point','arg':{'as_int':zero}},
                 {'name':'quant_min','arg':{'as_int':0}},{'name':'quant_max','arg':{'as_int':65535}},
                 {'name':'dtype','arg':{'as_scalar_type':4}}]
    return {'name':name,'target':target,'inputs':args,'outputs':[{'as_tensor':{'name':name}}]}


class PersistentRangeTests(unittest.TestCase):
    def test_explicit_range_and_carrier_are_separate(self):
        d=audit.encoding(node('q',audit.Q,'state'))['domain']
        self.assertEqual(4,d['dtype']);self.assertEqual(0,d['quant_min']);self.assertEqual(65535,d['quant_max'])
        self.assertEqual(audit.f32(-12*.01),d['decoded_min_fp32'])
        self.assertEqual(struct.pack('<f',.01).hex(),d['scale_f32le_hex'])

    def test_missing_dynamic_and_unrecognized_domains_explicit(self):
        n=node('q',audit.Q,'state');n['inputs'][1]['arg']={'as_tensor':{'name':'dynamic_scale'}}
        self.assertEqual('ambiguous',audit.encoding(n)['status'])
        self.assertIsNone(audit.encoding(n)['domain'])
        self.assertEqual('absent',audit.encoding(node('add','torch.ops.aten.add.Tensor','state'))['status'])

    def test_shape_only_use_not_a_numeric_branch(self):
        q=node('q',audit.Q,'state');dq=node('dq',audit.DQ,'q');use=node('use','aten.mul','dq')
        shape=node('shape','torch.ops.aten.expand_as.default','other')
        shape['inputs']=[{'name':'self','arg':{'as_tensor':{'name':'other'}}},{'name':'other','arg':{'as_tensor':{'name':'state'}}}]
        owners,users=audit.indexes({'nodes':[q,dq,use,shape]})
        result=audit.input_boundary('state',owners,users)
        self.assertEqual('unique',result['status']);self.assertEqual(1,len(result['quantizers']))
        self.assertEqual(1,len(result['shape_only_uses']));self.assertFalse(result['other_value_uses'])
        self.assertEqual('use',result['quantizers'][0]['branches'][0]['value_consumers'][0]['node'])

    def test_input_per_consumer_and_unequal_qdq_remain_explicit(self):
        ns=[node('q1',audit.Q,'state'),node('d1',audit.DQ,'q1'),node('q2',audit.Q,'state',.02),node('d2',audit.DQ,'q2',.02)]
        owners,users=audit.indexes({'nodes':ns});result=audit.input_boundary('state',owners,users)
        self.assertEqual('per_consumer',result['status']);self.assertIsNone(result['unique_domain'])
        ns[-1]=node('d2',audit.DQ,'q2',.03)
        owners,users=audit.indexes({'nodes':ns});self.assertEqual('ambiguous',audit.input_boundary('state',owners,users)['status'])

    def test_absent_or_unquantized_value_use_not_invented(self):
        self.assertEqual('absent',audit.input_boundary('state',{}, {})['status'])
        owners,users=audit.indexes({'nodes':[node('add','aten.add','state')]})
        result=audit.input_boundary('state',owners,users)
        self.assertEqual('ambiguous',result['status']);self.assertIsNone(result['unique_domain'])

    def test_output_per_consumer_domains_do_not_erase_selected_boundary(self):
        ns=[node('q1',audit.Q,'producer'),node('dq',audit.DQ,'q1'),node('q2',audit.Q,'producer',.02)]
        owners,users=audit.indexes({'nodes':ns});result=audit.output_boundary('dq',owners,users)
        self.assertEqual('explicit_paired',result['status']);self.assertTrue(result['producer_has_multiple_explicit_domains'])
        self.assertEqual(.01,result['domain']['scale']);self.assertEqual(2,len(result['producer_consumer_domains']))
        self.assertEqual('absent',audit.output_boundary('missing',owners,users)['status'])

    def test_decoded_compatibility_distinguished_from_code_clipping(self):
        d=audit.encoding(node('q',audit.Q,'state',.0007933978922665119,37640))['domain']
        result=audit.compatibility(d,d);self.assertTrue(result['same_encoding']);self.assertTrue(result['decoded_output_interval_contained_in_input'])
        self.assertEqual('unknown',audit.compatibility(None,d)['status'])
        import numpy as np
        high=d['decoded_max_fp32'];above=np.nextafter(np.float32(high),np.float32('inf'))
        coverage=audit.coverage([above],d)
        self.assertEqual(1,coverage['above_decoded_maximum']);self.assertEqual(0,coverage['code_clipped_total'])

    def test_vector_fp32_arithmetic_matches_scalar_stages(self):
        import numpy as np
        stages=json.loads((TOOLS.parent/'results/conv-history-sweep-readiness-20260910/pack/scalar-stages.json').read_text())
        d=audit.encoding(node('q',audit.Q,'state',.0007933978922665119,37640))['domain']
        array=np.array([r['value'] for r in stages],dtype=np.float32)
        code,decoded=audit.roundtrip(array,d)
        for value,c,out in zip(array,code,decoded):
            scalar=scalar_qdq(float(value),d)
            self.assertEqual(scalar['unclamped_code'],float(c))
            self.assertEqual(struct.pack('<f',scalar['output_fp32']),struct.pack('<f',out))

    def test_coverage_retains_nonfinite_scope_and_clipped_examples(self):
        d=audit.encoding(node('q',audit.Q,'state',.01,12))['domain']
        result=audit.coverage([float('nan'),-100,0,float('inf'),1000],d)
        self.assertEqual(3,result['finite_values']);self.assertEqual(2,result['code_clipped_total'])
        self.assertEqual([1,4],[e['flat_index'] for e in result['first_clipped_examples']])
        self.assertEqual('no_finite_values',audit.coverage([float('nan')],d)['status'])

    def test_only_five_bounded_saved_bundle_specs(self):
        specs=audit.bundle_specs();self.assertEqual(5,len(specs))
        self.assertEqual(['qdq_p0','qnn_p0','qdq_p1_same_inputs','qnn_p1_same_inputs','qnn_p1_own_state'],[s['id'] for s in specs])
        self.assertTrue(all(s['raw_bytes']<24*1024*1024 for s in specs))
        self.assertTrue(all('.pte' not in s['path'] and '.pt2' not in s['path'] for s in specs))

    def test_wrong_bundle_hash_rejected_before_deserialization(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'synthetic.pt';path.write_bytes(b'not a tensor')
            with self.assertRaisesRegex(ValueError,'Raw bundle identity'):
                audit.read_bundle_bytes({'path':str(path),'raw_bytes':12,'raw_sha256':'0'*64,'compressed':False})


if __name__=='__main__':unittest.main()

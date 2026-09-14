import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
m=importlib.import_module('analyze_paired_declared_prefill')


class PairedVectorAnalysisTests(unittest.TestCase):
    def test_identity_and_code_error_units(self):
        q=np.array([10,20,30],dtype=np.uint16);x=m.compare_codes(q,q,scale=.5,offset=-10)
        self.assertEqual(x['equal_codes'],3);self.assertTrue(x['bit_exact_codes']);self.assertAlmostEqual(x['cosine_common_grid'],1)
        r=np.array([12,18,31],dtype=np.uint16);x=m.compare_codes(q,r,scale=.5,offset=-10)
        self.assertEqual(x['different_codes'],3);self.assertAlmostEqual(x['mean_absolute_error_codes'],5/3)
        self.assertEqual(x['maximum_absolute_error_common_grid'],1);self.assertEqual(x['QNN_argmax']['lowest_ID'],2)

    def test_invalid_dtype_shape_grid_rejected(self):
        good=np.array([1,2],dtype=np.uint16)
        for bad in [np.array([1,2],dtype=np.int16),np.array([],dtype=np.uint16),good.reshape(1,2)]:
            with self.assertRaises(ValueError):m.compare_codes(bad,good)
        with self.assertRaises(ValueError):m.compare_codes(good,good,scale=0)

    def test_constant_vectors_keep_undefined_metrics_nullable_and_IDs_bounded(self):
        q=np.zeros(128,dtype=np.uint16);x=m.compare_codes(q,q,scale=1,offset=0)
        self.assertIsNone(x['cosine_common_grid']);self.assertIsNone(x['Pearson_common_grid'])
        self.assertEqual(x['QNN_argmax']['tie_count'],128);self.assertEqual(len(x['QNN_argmax']['IDs_bounded']),16)
        self.assertTrue(x['QNN_argmax']['IDs_truncated'])

    def test_full_length_hash_and_F32_expansion_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);q=root/'q';r=root/'r';f=root/'f';raw=(np.arange(m.VOCAB)%65536).astype('<u2');raw.tofile(q);raw.tofile(r)
            expanded=(raw.astype(np.float32)+np.float32(m.OFFSET))*np.float32(m.SCALE);expanded.astype('<f4').tofile(f)
            x=m.inspect_vectors(q,r,f,m.sha(q),m.sha(r),m.sha(f));self.assertEqual(x['values_compared'],262144)
            self.assertTrue(x['reference_raw_to_F32_serialization_verified'])
            expanded[0]+=1;expanded.tofile(f)
            with self.assertRaises(ValueError):m.inspect_vectors(q,r,f,m.sha(q),m.sha(r),m.sha(f))
            q.write_bytes(b'partial')
            with self.assertRaises(ValueError):m.inspect_vectors(q,r,f,m.sha(q),m.sha(r),m.sha(f))

    def test_corrected_partial_run_has_no_final_comparison(self):
        path=TRACK/'.local/paired-prefill-comparison/corrected-01/analysis.json'
        if not path.exists():self.skipTest('private corrected analysis unavailable')
        x=json.loads(path.read_text());self.assertEqual(x['reference_version'],'storage_corrected')
        self.assertIsNone(x['comparison']);self.assertIsNone(x['reference_capture'])
        self.assertEqual(x['first_unexpected_nonfinite']['operator_index'],6294)
        self.assertEqual(x['first_unexpected_nonfinite']['chunk'],5)
        self.assertEqual(x['trace']['open_operation_count'],1)

    def test_partial_trace_preserved_without_inventing_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'trace';p.write_text('\n'.join([json.dumps({'event':'begin','chunk':0,'index':0,'name':'a'}),json.dumps({'event':'end','chunk':0,'index':0}),json.dumps({'event':'begin','chunk':0,'index':1,'name':'b'}),'incomplete'])+'\n')
            r=m.trace_summary(p);self.assertEqual(r['begin'],2);self.assertEqual(r['end'],1)
            self.assertEqual(r['open_operation_count'],1);self.assertEqual(r['malformed_lines'],1)


if __name__=='__main__':unittest.main()

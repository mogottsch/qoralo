import importlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
a=importlib.import_module('analyze_htp_chain_codes')


class HTPChainCodeTests(unittest.TestCase):
    def test_all_row_pattern_values_are_checked(self):
        raw=np.broadcast_to(np.resize(np.array([1,2,3,4],dtype=np.uint16),128).reshape(1,128,1),(1,128,3)).copy()
        r=a.patterns(raw,[1,128,3]);self.assertEqual([x['codes_bounded'] for x in r],[[1],[2],[3],[4]])
        raw[0,124,2]=99;r=a.patterns(raw,[1,128,3]);self.assertEqual(r[0]['codes_bounded'],[1,99])
        self.assertEqual(r[0]['values_checked'],96)

    def test_native_dtype_shape_and_bounded_summary(self):
        with self.assertRaises(ValueError):a.patterns(np.zeros(128,dtype=np.int16),[1,128,1])
        with self.assertRaises(ValueError):a.patterns(np.zeros(127,dtype=np.uint16),[1,128,1])
        r=a.patterns(np.arange(128,dtype=np.uint16),[1,128,1]);self.assertEqual(r[0]['distinct_code_count'],32);self.assertEqual(len(r[0]['codes_bounded']),16)

    def test_saved_bindings_and_equality_do_not_prove_buffer_independence(self):
        path=TRACK/'.local/htp-chain-offline/analysis-01/analysis.json'
        if not path.exists():self.skipTest('private saved analysis unavailable')
        r=json.loads(path.read_text());self.assertEqual(r['total_raw_bytes'],1180416)
        self.assertTrue(r['compiled_to_execution_name_ID_shape_dtype_bindings_verified'])
        self.assertTrue(r['normalized_final_bytes_identical']);self.assertTrue(r['exposed_mean_denom_bytes_identical'])
        self.assertFalse(r['native_output_buffer_addresses_fds_or_alias_independence_captured'])
        self.assertFalse(r['optimizer_fusion_or_materialization_mechanism_identified'])
        self.assertFalse(r['epsilon_mean_floor_or_NaN_repair_adopted'])
        values={x['tensor']:x for x in r['outputs'] if x['case']=='normalization_exposed'}
        self.assertNotEqual(values['mean']['tensor_id'],values['denom']['tensor_id'])
        self.assertEqual(values['mean']['sha256'],values['denom']['sha256'])
        self.assertEqual(values['mean']['patterns'][0]['codes_bounded'],[1])
        self.assertEqual(values['squared']['patterns'][0]['codes_bounded'],[0])


if __name__=='__main__':unittest.main()

import importlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
a=importlib.import_module('analyze_htp_mean_add_codes')


class MeanAddCodeTests(unittest.TestCase):
    def test_all_words_not_only_first_pattern_are_checked(self):
        words=np.resize(np.array([1,1,22,434],dtype=np.uint16),128);before=words.copy();r=a.compare_patterns(words,[0,0,22,434])
        self.assertEqual(r['different_codes'],64);self.assertEqual(r['maximum_absolute_code_error'],1)
        self.assertFalse(r['generalized_rounding_floor_or_policy_inferred']);np.testing.assert_array_equal(words,before)
        words[-1]=65535;r=a.compare_patterns(words,[0,0,22,434]);self.assertEqual(r['different_codes'],65)
        self.assertEqual(r['observed_codes_per_pattern'][3],[434,65535]);self.assertEqual(r['maximum_absolute_code_error'],65101)

    def test_wrong_dtype_shape_and_pattern_count_rejected(self):
        for values,patterns in [(np.zeros(128,dtype=np.float32),[0]*4),(np.zeros(127,dtype=np.uint16),[0]*4),(np.zeros((1,128),dtype=np.uint16),[0]*4),(np.zeros(128,dtype=np.uint16),[0]*3)]:
            with self.assertRaises(ValueError):a.compare_patterns(values,patterns)

    def test_exact_binary_grid_rescale_keeps_mean_zero_comparator(self):
        if not a.STAGE.exists():self.skipTest('private frozen controls unavailable')
        stage=json.loads((a.STAGE/'frozen-manifest.json').read_text());g=stage['graphs'][0]
        x=np.fromfile(a.STAGE/'inputs/mean_edge.uint16le',dtype='<u2').reshape(128,-1);y=np.resize(np.array([1,1,22,434],dtype=np.uint16),128);r=a.exact_rescale_errors(x,y,g)
        self.assertEqual([v['nearest_even_code'] for v in r['patterns']],[0,0,22,434])
        self.assertEqual([v['code_error_vs_nearest'] for v in r['patterns']],[[1],[1],[0],[0]])
        self.assertEqual(r['patterns'][0]['ideal_output_code_coordinate_exact'],'0')
        self.assertEqual(r['patterns'][0]['decoded_error_vs_ideal'],[0.023287702351808548])
        self.assertLess(r['patterns'][1]['ideal_output_code_coordinate'],0.5)

    def test_epsilon_add_real_rescale_does_not_invent_positive_code(self):
        if not a.STAGE.exists():self.skipTest('private frozen controls unavailable')
        stage=json.loads((a.STAGE/'frozen-manifest.json').read_text());g=stage['graphs'][1]
        x=np.fromfile(a.STAGE/'inputs/epsilon_add.uint16le',dtype='<u2').reshape(128,-1);y=x[:,0].copy();r=a.exact_rescale_errors(x,y,g)
        self.assertEqual([v['nearest_even_code'] for v in r['patterns']],[0,1,22,434])
        self.assertTrue(all(v['code_error_vs_nearest']==[0] for v in r['patterns']))
        self.assertEqual(len(set(v['decoded_error_vs_ideal_exact'][0] for v in r['patterns'])),1)
        self.assertAlmostEqual(r['patterns'][0]['ideal_output_code_coordinate'],4.2918185502555006e-5)


if __name__=='__main__':unittest.main()

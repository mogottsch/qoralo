"""Numerical/reporting helpers only; tiny tensors, no model or saved model load."""
import sys
import unittest
from pathlib import Path

import torch

torch.set_num_threads(1)
EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP/'tools'))
from analyze_position1_pair import compare_saved, output_identity
from controlled_position1 import difference_vectors


class SavedAnalysisTest(unittest.TestCase):
    def test_identical_nonzero_vectors(self):
        x=torch.tensor([1.,2.,-4.])
        r=compare_saved(x,x)
        self.assertAlmostEqual(1.,r['cosine'],places=12)
        self.assertEqual(0,r['max_abs']);self.assertEqual(0,r['l2_difference'])

    def test_zero_angle_is_nullable_not_invented(self):
        r=compare_saved(torch.zeros(3),torch.ones(3))
        self.assertIsNone(r['cosine']);self.assertEqual('zero norm',r['cosine_null_reason'])
        self.assertTrue(r['finite'])

    def test_nonfinite_values_are_explicit(self):
        r=compare_saved(torch.tensor([float('nan')]),torch.tensor([1.]))
        self.assertFalse(r['finite']);self.assertIsNone(r['cosine'])

    def test_geometry_or_dtype_mismatch_rejected(self):
        with self.assertRaises(ValueError):compare_saved(torch.ones(3),torch.ones(4))
        with self.assertRaises(ValueError):compare_saved(torch.ones(3),torch.ones(3,dtype=torch.float64))

    def test_output_labels_keep_48_states_separate_from_24_hidden(self):
        types=(['linear_attention']*3+['full_attention'])*6
        self.assertEqual(('logits',None,None),output_identity(0,types))
        self.assertEqual(('state_a',0,'linear_attention'),output_identity(1,types))
        self.assertEqual(('state_b',0,'linear_attention'),output_identity(25,types))
        self.assertEqual(('hidden_after_layer',0,'linear_attention'),output_identity(49,types))
        self.assertEqual(('hidden_after_layer',23,'full_attention'),output_identity(72,types))

    def test_vector_terms_preserve_reference_shift_and_originals(self):
        x=[torch.tensor([float(v),float(-v),float(v+1)]) for v in (7,3,2,1)]
        originals=[t.clone() for t in x]
        r=difference_vectors(*x)
        torch.testing.assert_close(r['current_call']+r['qnn_state_effect']+r['historical_reference_shift'],r['observed_own_trajectory_difference'],rtol=0,atol=0)
        self.assertEqual(0,int(r['rounding_residual'].count_nonzero()))
        for a,b in zip(x,originals):self.assertTrue(torch.equal(a,b))
        self.assertFalse(any('cosine' in k for k in r))


if __name__=='__main__':unittest.main()

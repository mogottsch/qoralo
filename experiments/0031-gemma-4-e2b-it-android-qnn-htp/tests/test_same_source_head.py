import json
from pathlib import Path
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'


class SameSourceHeadTests(unittest.TestCase):
    def test_full_head_matches_both_equal_source_tables(self):
        x=json.loads((TRACK/'results/same-source-head-fidelity-01/result.json').read_text())
        self.assertEqual(x['values'],262144*1536)
        for name in ('head_f32','embedding_f32'):
            self.assertTrue(x['comparisons'][name]['exact_equal'])
            self.assertEqual(x['comparisons'][name]['mismatching_values'],0)
            self.assertEqual(x['comparisons'][name]['dequantized_f32_bytes_sha256'],x['export_head_region_sha256'])
        self.assertGreater(x['comparisons']['head_bf16_forward']['mismatching_values'],0)

    def test_config_difference_is_not_promoted_to_corrupt_weights(self):
        x=json.loads((TRACK/'results/same-source-head-fidelity-01/result.json').read_text())
        self.assertTrue(x['export_config_tie_word_embeddings'])
        self.assertFalse(x['source_config_tie_word_embeddings'])
        self.assertFalse(x['model_forward_or_inference'])
        self.assertEqual(x['adb_calls'],0)
        self.assertEqual(x['text_and_head_SRQ_scale_count'],632)
        self.assertEqual(x['nonzero_SRQ_scales'],630)


if __name__=='__main__':unittest.main()

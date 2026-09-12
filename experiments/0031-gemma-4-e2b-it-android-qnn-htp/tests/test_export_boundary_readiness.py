import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
spec=importlib.util.spec_from_file_location('boundary',TRACK/'tools/audit_export_boundary_readiness.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)


class BoundaryHelperTests(unittest.TestCase):
    def test_identity_codebook_and_no_unsigned_wrap_invention(self):
        x=b.requant_codebook(1,0,1,0,False)
        self.assertTrue(x['conversion_valid_for_all_codes']);self.assertEqual(x['max_abs_added_error'],0)
        x=b.requant_codebook(1000,-128,1,0,False)
        self.assertFalse(x['conversion_valid_for_all_codes']);self.assertTrue(x['unclamped_out_of_range_codes'])
        self.assertNotIn('output_code_min',x)
        self.assertTrue(b.requant_codebook(1000,-128,1,0,True)['conversion_valid_for_all_codes'])

    def test_debug_spans_not_mistaken_for_full_logits(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'log';p.write_text('input-logits: [1,2] ... [3,4]\n')
            x=b.partial_logits_inventory(p)
            self.assertEqual(x['entries_per_head_tail'],{'(2, 2)':1})
            self.assertFalse(x['complete_vocabulary_vector'])


class SavedBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.x=json.loads((TRACK/'results/export-boundary-source-readiness-01/result.json').read_text())

    def test_actual_export_is_not_native_SRQ(self):
        x=self.x;e=x['archived_export']
        self.assertEqual(e['node_count'],9596);self.assertEqual(e['function_count'],0)
        self.assertEqual(e['node_domains'],{'':9596})
        self.assertEqual(e['encoding_histograms']['param_encodings'],{"(4, 'INT')":522})
        self.assertEqual(e['encoding_histograms']['activation_encodings'],{"(16, 'INT')":6194})
        self.assertEqual(x['SRQ_boundary']['export_explicit_round_clip_QDQ_nodes'],0)
        self.assertFalse(x['SRQ_boundary']['direct_native_to_HTP_numerical_match'])
        self.assertFalse(x['available_exporter_source']['archive_producer_source_revision_proven'])

    def test_all_lut_codes_fit_but_not_called_a_runtime_tensor_capture(self):
        c=self.x['input_boundary']['contracts']
        for v in c.values():
            x=v['all_256_codes'];self.assertEqual(x['unclamped_out_of_range_codes'],[])
            self.assertTrue(x['conversion_valid_for_all_codes'])
            self.assertIn('not execution proof',x['boundary'])
        self.assertEqual(c['inputs_embeds']['all_256_codes']['requant_offset_int32'],16574)
        self.assertEqual(c['per_layer_inputs']['all_256_codes']['requant_offset_int32'],6012)

    def test_no_saved_full_QNN_logits_and_no_new_inference(self):
        x=self.x;i=x['saved_logit_inventory']
        self.assertEqual(i['raw_logit_candidate_files'],[])
        self.assertFalse(i['QNN_complete_prefill_logits_found'])
        self.assertEqual(i['selected_trace_provider']['entries_per_head_tail'],{'(10, 10)':2048})
        self.assertFalse(x['readiness']['matched_causal_comparison_ready'])
        self.assertFalse(x['readiness']['next_inference_authorized'])
        self.assertEqual(x['neural_model_instantiations_or_forward_calls'],0)
        self.assertEqual(x['adb_calls'],0)


if __name__=='__main__':unittest.main()

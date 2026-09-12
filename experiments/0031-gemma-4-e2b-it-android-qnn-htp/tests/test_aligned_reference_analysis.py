import importlib
from pathlib import Path
import struct
import sys
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
a=importlib.import_module('analyze_aligned_litert_reference')


class AlignedAnalysisTests(unittest.TestCase):
    def test_full_input_not_count_only(self):
        record={'actual_effective_token_ids':[2,105,7],'expected_effective_token_ids':[2,105,7],'all_ids_equal':True,'prefill_not_yet_started':True}
        expected=struct.pack('<3i',2,105,7)
        self.assertTrue(a.input_alignment(record,expected)['exact_frozen_ids_equal'])
        record['actual_effective_token_ids']=[2,105,8]
        self.assertFalse(a.input_alignment(record,expected)['exact_frozen_ids_equal'])

    def test_invalid_ids_rejected(self):
        for values in ([True,2],[-1],[262144],['2'],None):
            with self.assertRaises(ValueError):a.packed(values)

    def test_prefix_difference_is_descriptive(self):
        result=a.prefix_comparison([818,42,9],[818,42,10,11])
        self.assertEqual(result['common_prefix_tokens'],2)
        self.assertEqual(result['first_differing_index'],2)
        self.assertEqual(result['reference_id_at_difference'],9)

    def test_filtered_terminal_not_invented(self):
        result=a.prefix_comparison([818,42],[818,42,106])
        self.assertIsNone(result['first_differing_index'])
        self.assertTrue(result['one_stream_ended_after_common_prefix'])
        self.assertIsNone(result['qnn_id_at_difference'])


if __name__=='__main__':unittest.main()

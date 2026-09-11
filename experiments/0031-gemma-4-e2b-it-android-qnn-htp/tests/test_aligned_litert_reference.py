"""Source-only aligned-reference checks; never load an engine or use ADB."""
import importlib
import json
from pathlib import Path
import struct
import sys
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
a=importlib.import_module('prepare_aligned_litert_reference')


class AlignedReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=a.SOURCE.read_text()
        cls.ids=list(struct.unpack('<1929i',(a.STAGE/'token-ids/long.int32le').read_bytes()))
        cls.derived,cls.changes=a.patch(cls.source,cls.ids)

    def test_only_one_long_request_with_full_id_gate_before_prefill(self):
        self.assertEqual(self.derived.count('RunRequest('),2)
        self.assertEqual(self.derived.count('session.RunPrefill(input)'),1)
        self.assertLess(self.derived.index('if (!alignment_matches)'),self.derived.index('session.RunPrefill(input)'))
        self.assertIn('actual_input_ids == kExpectedAlignedInputIds',self.derived)
        self.assertIn('for (const std::string tier : {"long"})',self.derived)
        self.assertNotIn('session.RewindToStep',self.derived)
        self.assertIn('FLAGS_backend) != "gpu"',self.derived)
        self.assertIn('FLAGS_cache_dir) == ":nocache"',self.derived)

    def test_remove_only_renderer_bos_and_keep_reference_sampler(self):
        self.assertIn('return "<|turn>system\\n" + system',self.derived)
        self.assertNotIn('return "<bos><|turn>system\\n" + system',self.derived)
        self.assertNotIn('SetStartTokenId(',self.derived)
        start=self.source.index('  auto& sampler = session_config.GetMutableSamplerParams();')
        end=self.source.index('  const auto initial_session_creation_start',start)
        self.assertIn(self.source[start:end],self.derived)
        self.assertIn('FLAGS_max_num_tokens) != 8192',self.derived)
        self.assertIn('2048, 1800, kExpectedAlignedInputIds.size()',self.derived)
        self.assertEqual(a.sha(a.SOURCE.read_bytes()),a.SOURCE_SHA)

    def test_saved_cpu_gpu_effective_history_and_same_tokenizer_body_algebra(self):
        for backend in ('cpu','gpu'):
            path=a.REFERENCE/f'results/android-{backend}-campaign/raw/runner-stdout.jsonl'
            runner=json.loads([line for line in path.read_text().splitlines() if line.startswith('{')][-1])
            old=runner['prompts']['long']['token_ids']
            self.assertEqual(old,[2]+self.ids)
            # Source flow: metadata BOS chunk + explicit BOS in caller chunk.
            # StringToProcessedInputText strips caller BOS before tokenizing the
            # body, then reinserts it. Without caller BOS, SAME body is encoded
            # without that reinsertion; metadata BOS chunk stays unchanged.
            rendered=(a.STAGE/'prompts/long.txt').read_text()
            self.assertTrue(rendered.startswith('<bos>'))
            body=rendered[len('<bos>'):]
            old_tokenizer_body=rendered[len('<bos>'):]
            self.assertEqual(body,old_tokenizer_body)
            self.assertEqual(old[:1]+old[2:],self.ids)

    def test_stale_private_source_and_wrong_expected_input_are_rejected(self):
        stale=(a.REFERENCE/'.local/LiteRT-LM/runtime/engine/litert_lm_canonical_runner.cc').read_text()
        self.assertNotEqual(a.sha(stale.encode()),a.SOURCE_SHA)
        with self.assertRaises(ValueError):a.patch(stale,self.ids)
        with self.assertRaises(ValueError):a.patch(self.source,[2]+self.ids)
        wrong=self.ids.copy();wrong[-1]+=1
        with self.assertRaises(ValueError):a.patch(self.source,wrong)


if __name__=='__main__':unittest.main()

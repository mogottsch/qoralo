import importlib.util
from pathlib import Path
import struct
import unittest
import json

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('inputs',ROOT/'common/prepare_inputs.py');inputs=importlib.util.module_from_spec(spec);spec.loader.exec_module(inputs)

class CommonTests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(inputs.normalize('  Hi\u00a0there—“friend”\n'), 'Hi there-"friend"')
        self.assertEqual(inputs.normalize('a_b / c'), 'a b c.')
        self.assertEqual(inputs.normalize('Hello 👋\x00\x01 world'), 'Hello world.')
        self.assertEqual(inputs.normalize('Café.'),'Cafe\u0301.')
    def test_empty_rejected(self):
        with self.assertRaises(ValueError):inputs.normalize(' \n ')
    def test_per_character_decomposition(self):
        self.assertEqual(inputs.normalize('a\u0315\u0300.'),'a\u0315\u0300.')
    def test_terminal_set(self):
        expected=set('.!?;:,\'\")]}>…。」』】〉》›»“”‘’')
        self.assertEqual(inputs.TERMINAL,expected)
    def test_noise_is_saved_layout_not_seed_matching(self):
        small=inputs.noise(2);large=inputs.noise(4)
        self.assertEqual(len(small),144*2*4)
        self.assertEqual(small,inputs.noise(2))
        self.assertEqual(small[:8],large[:8])
        self.assertNotEqual(small[8:16],large[16:24])
        self.assertTrue(all(abs(x)<10 for x in struct.unpack('<288f',small)))
    def test_runner_forbids_duration_override_and_cpu_other_ep(self):
        text=(ROOT/'cpu/runner.cc').read_text()
        self.assertIn('natural duration exceeds common L; no crop/override',text)
        self.assertNotIn('.AppendExecutionProvider',text)
        self.assertIn('std::floor(predicted[0]*float(SR))',text)
        self.assertIn('step<5',text)
        self.assertNotIn('kTrimmedSamples',text)

class CoverageTests(unittest.TestCase):
    def test_known_alignment(self):
        spec=importlib.util.spec_from_file_location('asr',ROOT/'common/asr_coverage.py');asr=importlib.util.module_from_spec(spec);spec.loader.exec_module(asr)
        result=asr.alignment('one two three four','one three five')
        self.assertEqual(result['word_error_rate'],0.5)
        self.assertEqual(result['deletions'],1)
        self.assertEqual(result['substitutions'],1)
        self.assertEqual(result['exactly_matched_reference_words'],2)
    def test_complete_alignment(self):
        spec=importlib.util.spec_from_file_location('asr',ROOT/'common/asr_coverage.py');asr=importlib.util.module_from_spec(spec);spec.loader.exec_module(asr)
        result=asr.alignment('Hello, friend!','hello friend')
        self.assertEqual(result['word_error_rate'],0)
        self.assertEqual(result['last_30_reference_words_matched'],2)

class EvidenceTests(unittest.TestCase):
    def test_full_cpu_own_stage_evidence(self):
        x=json.loads((ROOT/'cpu/results/full-render-01.json').read_text())
        self.assertEqual(x['emitted_frames'],1304030)
        self.assertEqual(x['natural_active_latent'],425)
        self.assertEqual(x['latent_extent'],512)
        self.assertEqual(x['wav']['sha256'],'9b1c8587308fb2a98ef1d600549e8f06beec86c3419684789279a143b17c46d2')
        self.assertEqual(set(x['provider_evidence']),{'duration','text','vector','vocoder'})
        for value in x['provider_evidence'].values():self.assertEqual(set(value['kernel_events_by_provider']),{'CPUExecutionProvider'})
        self.assertEqual(x['provider_evidence']['vector']['kernel_events_by_provider']['CPUExecutionProvider'],5*x['provider_evidence']['vector']['distinct_profile_kernel_names'])
    def test_coverage_failure_is_not_hidden_by_valid_wav(self):
        x=json.loads((ROOT/'cpu/results/full-render-01.json').read_text())
        self.assertEqual(x['coverage_status'],'failed_qualified_local_asr')
        self.assertFalse(x['entire_chapter_coverage_demonstrated'])
        self.assertGreater(x['asr_summary']['word_error_rate'],0.8)
        self.assertEqual(x['listening_acceptance'],'not_reviewed')
        self.assertIsNone(x['warm_median_rtf'])
    def test_frozen_stochastic_contract(self):
        c=json.loads((ROOT/'protocol/contract.json').read_text())
        x=json.loads((ROOT/'cpu/results/full-render-01.json').read_text())
        self.assertEqual(c['tensors']['noise.f32']['shape'],[1,144,512])
        self.assertEqual(c['tensors']['noise.f32']['sha256'],x['stochastic_input_evidence']['common_noise_sha256'])
        self.assertEqual(c['tensors']['current_step.f32']['shape'],[5])
        self.assertTrue(x['stochastic_input_evidence']['active_columns_exactly_equal_common_saved_noise'])
        self.assertTrue(x['stochastic_input_evidence']['inactive_columns_exactly_zero'])

if __name__=='__main__':unittest.main()

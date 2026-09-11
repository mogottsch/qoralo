import importlib.util
from pathlib import Path
import struct
import unittest

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

if __name__=='__main__':unittest.main()

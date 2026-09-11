import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]


class TextLoadTests(unittest.TestCase):
    def test_no_forward_api_or_profile_enable(self):
        code=(ROOT/'phone/text_load_diagnostic.cc').read_text()
        self.assertNotRegex(code,r'(?:\.|->)\s*Run\s*\(')
        self.assertNotIn('EnableProfiling(',code)
        self.assertIn('"session.disable_cpu_ep_fallback","1"',code)
        self.assertIn('alarm(180)',code)
        self.assertIn('session.reset()',code)

    def test_private_stage_is_text_only(self):
        stage=ROOT/'.local/text-load-stage-01'
        if not stage.exists():self.skipTest('private local stage absent')
        d=json.loads((stage/'stage-provenance.json').read_text())
        self.assertEqual(d['constructor_calls'],1)
        self.assertEqual(d['Run_calls'],0)
        contexts={name for name in d['files'] if name.startswith('contexts/')}
        self.assertEqual(contexts,{'contexts/text-context.onnx','contexts/text-context_qnn.bin'})
        self.assertFalse(any('bundle/' in name or 'duration' in name for name in d['files']))
        for name,record in d['files'].items():
            self.assertEqual(hashlib.sha256((stage/name).read_bytes()).hexdigest(),record['sha256'])


if __name__=='__main__':unittest.main()

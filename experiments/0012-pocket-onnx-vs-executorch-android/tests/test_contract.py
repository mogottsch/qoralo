import hashlib, json, re, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
class ContractTest(unittest.TestCase):
 def test_protocol_is_exact_and_cpu_only(self):
  p=json.loads((ROOT/'protocol.json').read_text()); c=p['matched_contract']
  self.assertEqual(hashlib.sha256(c['text'].encode()).hexdigest(),c['text_sha256'])
  self.assertEqual(c['device'],'R5CW81PR8SY / SM-S918B / SM8550');self.assertEqual(c['execution'],'CPU only');self.assertEqual(c['threads'],1)
 def test_source_and_graphs_are_pinned_float(self):
  p=json.loads((ROOT/'provenance/source-and-export.json').read_text());self.assertEqual(p['official_source']['weight_revision'],'d29db7978e464fb90cb3359ee0c69a273b9142cc')
  self.assertFalse(p['official_source']['gated']);self.assertEqual(p['controlled_onnx_export']['quantization_ops'],0)
  for f in p['official_source']['files']+p['controlled_onnx_export']['files']:
   self.assertRegex(f['sha256'],r'^[0-9a-f]{64}$')
 def test_route_outcomes_and_scope(self):
  r=json.loads((ROOT/'results/comparison.json').read_text());self.assertEqual(r['onnx']['status'],'android_cpu_success');self.assertEqual(r['executorch']['status'],'blocked_before_android')
  self.assertEqual(r['onnx']['runtime']['provider'],'cpu');self.assertEqual(r['onnx']['runtime']['qnn_events'],0);self.assertEqual(r['scope'],{'quantization':False,'qnn':False,'htp':False})
  self.assertTrue(r['onnx']['output']['finite'] and r['onnx']['output']['non_silent'] and r['onnx']['output']['unclipped'])
 def test_executorch_blocker_is_fail_closed(self):
  e=json.loads((ROOT/'provenance/executorch-screen.json').read_text());self.assertEqual(e['status'],'blocked_before_android')
  for name in ('flow_lm_main','mimi_decoder'):
   self.assertTrue(e['components'][name]['required_for_complete_tts']);self.assertFalse(e['components'][name]['torch_export'])

if __name__=='__main__': unittest.main()

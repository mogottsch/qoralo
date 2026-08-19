import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ResultContract(unittest.TestCase):
 def test_protocol_identity(self):
  p=json.loads((ROOT/'protocol.json').read_text());m=p['matched_contract']
  self.assertEqual(hashlib.sha256(m['text'].encode()).hexdigest(),m['text_sha256'])
  self.assertEqual(m['device'],'R5CW81PR8SY / SM-S918B / SM8550')
 def test_fail_closed_result(self):
  r=json.loads((ROOT/'results/host-gate.json').read_text());self.assertEqual(r['result'],'blocked_before_phone')
  self.assertTrue(r['runtime']['cpu_fallback_disabled']);self.assertFalse(r['phone']['attempted']);self.assertIsNone(r['performance']['htp_rtf']);self.assertIsNone(r['sample_audio']['htp_wav'])
 def test_no_false_full_htp_claim(self):
  r=json.loads((ROOT/'results/host-gate.json').read_text());v={x['variant']:x for x in r['static_optimized_variants']}
  self.assertTrue(v['text_conditioner-text26']['passed']);self.assertTrue(v['flow_lm_flow-flow1']['passed'])
  for name in ('flow_lm_main-voice126','flow_lm_main-text26','flow_lm_main-ar1','mimi_encoder-encoder240000','mimi_decoder-decoder12','mimi_decoder-decoder6'):self.assertFalse(v[name]['passed'])
  self.assertFalse(r['boundaries']['mixed_fallback_run']);self.assertFalse(r['boundaries']['quantization'])
if __name__=='__main__':unittest.main()

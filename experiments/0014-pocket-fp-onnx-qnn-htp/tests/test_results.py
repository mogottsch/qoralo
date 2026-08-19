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
 def test_original_no_false_full_htp_claim(self):
  r=json.loads((ROOT/'results/host-gate.json').read_text());v={x['variant']:x for x in r['static_optimized_variants']}
  self.assertTrue(v['text_conditioner-text26']['passed']);self.assertTrue(v['flow_lm_flow-flow1']['passed'])
  for name in ('flow_lm_main-voice126','flow_lm_main-text26','flow_lm_main-ar1','mimi_encoder-encoder240000','mimi_decoder-decoder12','mimi_decoder-decoder6'):self.assertFalse(v[name]['passed'])
  self.assertFalse(r['boundaries']['mixed_fallback_run']);self.assertFalse(r['boundaries']['quantization'])
 def test_continuation_is_qnn_only_but_quality_failed(self):
  r=json.loads((ROOT/'results/full-qnn-continuation.json').read_text());self.assertEqual(r['result'],'technically_qnn_only_observed_paths_but_perceptually_rejected');self.assertFalse(r['quality']['deployment_recommendation']);self.assertTrue(r['runtime']['cpu_fallback_disabled'])
  for route in r['explicit_temperature_0_7_phone_candidates'].values():
   self.assertEqual(route['provider_events']['CPUExecutionProvider'],0);q=route['provider_events']['QNNExecutionProvider'];self.assertGreater(q,0)
   for key in ('rpc_execute_events','accelerator_execute_events','cycle_events','hvx_events'):self.assertEqual(q,route['physical'][key])
   self.assertEqual(route['physical']['hvx_thread_sum'],4*q);self.assertTrue(route['wav']['finite'] and route['wav']['non_silent'] and route['wav']['unclipped']);self.assertTrue(route['cleanup_verified'])
  self.assertIn('observed',r['technical_boundary']['observed_path']);self.assertIn('neither',r['technical_boundary']['decoder6']);self.assertIn('physically invoked',r['technical_boundary']['decoder6'])
 def test_blind_listening_rejected_cpu_and_qnn(self):
  r=json.loads((ROOT/'results/blind-listening.json').read_text());self.assertTrue(r['method']['blind']);self.assertEqual(r['verdict'],'all_rejected_as_unusable');self.assertEqual(r['samples']['B']['revealed_route'],'experiment-0012 ONNX Runtime CPU oracle');self.assertEqual(set(r['samples']),{'A','B','C'})
 def test_temperature_correction_is_scoped(self):
  r=json.loads((ROOT/'results/temperature-drift.json').read_text());self.assertEqual(r['evidence']['committed_0012_runner']['sha256'],'6f4b1376c4eb90098c6b08a710bcae01192936a01a56067c18903441e3ff45ee');self.assertIn('0.7',r['finding']);self.assertTrue(r['do_not_rewrite_history']);self.assertIn('not modified',r['scope'])
if __name__=='__main__':unittest.main()

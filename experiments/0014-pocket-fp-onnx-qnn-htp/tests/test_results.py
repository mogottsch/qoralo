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
 def test_zero_encoder_root_cause_is_fail_closed(self):
  r=json.loads((ROOT/'results/zero-voice-encoder-root-cause.json').read_text());z=r['zero_encoder_tensors']
  self.assertEqual(z['count'],42);self.assertEqual(z['total_elements'],9224736);self.assertTrue(z['all_zero']);self.assertTrue(all(x['nonzero_elements']==0 for x in z['tensors']))
  fixtures=r['controlled_onnx_encoder']['fixture_results'];self.assertEqual({x['fixture'] for x in fixtures},{'bria_first_10s','zeros','ones','random_seed0_standard_normal'});self.assertTrue(all(x['source_vs_onnx_exact'] and x['source_nonzero_elements']==0 and x['onnx_nonzero_elements']==0 for x in fixtures));self.assertIn('invalid audio-cloning route',r['root_cause'])
 def test_recovered_fixed_alba_qnn_path(self):
  r=json.loads((ROOT/'results/alba-quality-recovery.json').read_text());q=r['physical_qnn_htp'];p=q['profiled_proof'];events=p['provider_events'];physical=p['physical']
  self.assertEqual(events,{'QNNExecutionProvider':122});self.assertEqual(physical['rpc_execute_events'],122)
  for key in ('accelerator_execute_events','cycle_events','hvx_events'):self.assertEqual(physical[key],122)
  self.assertEqual(physical['hvx_thread_sum'],488);self.assertTrue(p['cleanup_verified']);self.assertTrue(q['unprofiled_single_generation']['byte_identical_to_profiled_and_accepted']);self.assertIn('not a warm median',q['unprofiled_single_generation']['timing_boundary'])
  self.assertEqual(r['quality']['canonical_observed_qnn_sample_sha256'],'2c3901ec39a53596759c1d95381a1d67e4f9ca8886cdf39ac03721863c63eb56');self.assertTrue(r['quality']['accepted']);self.assertEqual(q['listening']['verdict'],'accepted');self.assertNotIn('encoder',p['calls'])
 def test_quality_recovery_verdicts_remain_route_scoped(self):
  r=json.loads((ROOT/'results/quality-recovery-listening.json').read_text());self.assertEqual(r['android_cpu_original_graph_alba_gate']['verdict'],'rejected');self.assertEqual(r['android_cpu_fixed_cache_alba_gate']['verdict'],'accepted');self.assertEqual(r['physical_fallback_disabled_qnn_alba_gate']['verdict'],'accepted');self.assertTrue(r['physical_fallback_disabled_qnn_alba_gate']['independent_from_cpu']);self.assertEqual(r['controlled_fp_onnx_alba_host_gate']['verdict'],'accepted_both')
 def test_quality_recovery_protocol_preserves_full_cache_context(self):
  r=json.loads((ROOT/'quality-recovery-protocol.json').read_text());b=r['qnn_static_boundary'];self.assertEqual(b['initial_voice_positions']+b['text_positions']+b['maximum_generated_positions'],252);self.assertLessEqual(252,b['cache_capacity']);self.assertFalse(r['preservation']['edit_0012']);self.assertIn('fixed-voice',r['contract']['voice'])
if __name__=='__main__':unittest.main()

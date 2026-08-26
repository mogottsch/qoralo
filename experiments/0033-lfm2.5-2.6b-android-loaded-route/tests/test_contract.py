import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; EXP=ROOT/'experiments/0033-lfm2.5-2.6b-android-loaded-route'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
class TestContract(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.c=json.loads((EXP/'protocol/experiment-contract.json').read_text())
 def test_shared_protocol_and_workloads(self):
  self.assertEqual('2bb2de193745bc9b74c98639ee077f07615702655b2fc6118185148e2a0c0b46',sha(ROOT/'protocols/android-llm-benchmark/contract.json'))
  for t,h in self.c['canonical_protocol']['workloads'].items(): self.assertEqual(h,sha(ROOT/f'protocols/android-llm-benchmark/workloads/inference-v1/{t}.json'))
  self.assertEqual('proven_full_in_session_conversation_and_kv_reset',self.c['canonical_protocol']['request_isolation_strategy'])
 def test_lfm_identity(self):
  a=self.c['deployment_artifact']; self.assertTrue(a['official_liquidai_artifact']); self.assertEqual(1674455040,a['bytes']); self.assertEqual('02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed',a['sha256'])
  p=self.c['tokenizer_and_template']['prompt_inventory']; self.assertEqual({'short':171,'medium':600,'long':1922},{k:v['input_tokens'] for k,v in p.items()})
 def test_two_separate_artifacts(self):
  a=self.c['runtime']['artifacts']; self.assertEqual('8ce2767eba7480326682d69963eeb483204ee1541c3b5b0c0ef409068ea2b217',a['cpu']['sha256']); self.assertEqual('64409e6e96a7d003ed6c68ec12363f3e6d7c34d46af40bc439cb84f060cd4ced',a['opencl']['sha256']); self.assertEqual(['libc.so','libdl.so','libm.so'],a['cpu']['dynamic_dependencies']); self.assertIn('libOpenCL.so',a['opencl']['dynamic_dependencies']); self.assertFalse(a['opencl']['binary_kernels']); self.assertEqual(a['opencl']['kernel_manifest_sha256'],sha(EXP/a['opencl']['kernel_manifest']))
 def test_runner_is_persistent_isolated_and_separate(self):
  s=(EXP/'tools/run_phone.sh').read_text(); c=(EXP/'tools/run_client.py').read_text()
  for x in ('android-stage-cpu','android-stage-opencl','--device none --gpu-layers 0','--device GPUOpenCL --gpu-layers 31','POST /slots/0?action=erase','range(1, 6)','cache_n'): self.assertIn(x,s+c)
  self.assertIn('tokenizer.ggml.add_bos_token=bool:false',s); self.assertIn('<|im_start|>assistant\\n<think>',c)
  self.assertIn('vibevoice-0033-lfm2.5-2.6b-android-loaded-route-$ARM',s); self.assertIn('flock -n 9',s); self.assertNotIn('/sdcard',s)
 def test_complete_cpu_campaign_is_separate_and_valid(self):
  base=EXP/'results/android-cpu-campaign'; d=json.loads((base/'result.json').read_text()); c=self.c['completed_cpu_campaign']; self.assertEqual(c['result_sha256'],sha(base/'result.json')); self.assertEqual(c['checksum_manifest_sha256'],sha(base/'SHA256SUMS')); self.assertEqual(16,len(d['runs'])); self.assertEqual('GGML CPU',d['runtime']['provider_backend']); self.assertEqual('none',d['runtime']['provider_device']); self.assertEqual(0,d['runtime']['observed_offloaded_layers']); self.assertIsNone(d['gpu_telemetry']); self.assertTrue(d['gpu_telemetry_missing_reason'])
  ids=['first-short-01']+[f'short-{i:02d}' for i in range(1,6)]+[f'medium-{i:02d}' for i in range(1,6)]+[f'long-{i:02d}' for i in range(1,6)]; self.assertEqual(ids,[r['id'] for r in d['runs']]); counts={'short':171,'medium':600,'long':1922}
  for r in d['runs']:
   self.assertEqual('complete',r['status']); self.assertEqual('max_tokens' if r['tier']=='long' else 'eos',r['stop_reason']); self.assertEqual([],r['reset_validation']['errors']); self.assertEqual(0,r['server_timings']['cache_n']); self.assertEqual(counts[r['tier']],r['server_timings']['prompt_n']); self.assertFalse(r['final_event']['truncated']); self.assertTrue(r['output_sanity']['looks_sensible']); self.assertEqual(r['output_sha256'],sha(base/r['output_path'])); self.assertFalse(r['request_isolation']['model_remap_or_reload']); self.assertFalse(r['request_isolation']['accelerator_recompilation']); self.assertFalse(r['request_isolation']['retained_prompt_or_kv_reuse'])
  self.assertEqual('verified_absent',d['stage_and_cleanup']['cleanup_state'])
 def test_opencl_proof_and_bounded_claim(self):
  c=(EXP/'tools/run_client.py').read_text();
  for x in ('offloaded 31/31 layers to GPU','OpenCL model buffer size','OpenCL compute buffer size','using kernels optimized for Adreno','OpenCL driver: OpenCL'): self.assertIn(x,c)
  self.assertIn('not GPU-exclusive',self.c['runtime']['artifacts']['opencl']['claim_boundary'])
if __name__=='__main__':unittest.main()

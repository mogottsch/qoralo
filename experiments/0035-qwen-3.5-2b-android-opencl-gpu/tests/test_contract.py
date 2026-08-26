import hashlib, json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
EXP=ROOT/'experiments/0035-qwen-3.5-2b-android-opencl-gpu'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
class ContractTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.c=json.loads((EXP/'protocol/experiment-contract.json').read_text())
 def test_protocol_and_workloads(self):
  self.assertEqual('2bb2de193745bc9b74c98639ee077f07615702655b2fc6118185148e2a0c0b46',sha(ROOT/'protocols/android-llm-benchmark/contract.json'))
  for tier,d in self.c['canonical_protocol']['workloads'].items(): self.assertEqual(d,sha(ROOT/f'protocols/android-llm-benchmark/workloads/inference-v1/{tier}.json'))
  self.assertEqual(5,self.c['canonical_protocol']['minimum_loaded_route_requests_per_tier'])
 def test_model_and_prompt_identity(self):
  a=self.c['deployment_artifact']; self.assertEqual(1280835840,a['bytes']); self.assertEqual('aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223',a['sha256'])
  self.assertEqual({'short':174,'medium':597,'long':1926},{k:v['input_tokens'] for k,v in self.c['tokenizer_and_template']['host_prompt_inventory'].items()})
 def test_reproducible_opencl_artifact(self):
  r=self.c['runtime']; self.assertEqual('GGML OpenCL GPU offload',r['provider_backend']); self.assertTrue(r['android_server']['clean_rebuilds_byte_identical']); self.assertEqual(12313808,r['android_server']['bytes']); self.assertEqual('64409e6e96a7d003ed6c68ec12363f3e6d7c34d46af40bc439cb84f060cd4ced',r['android_server']['sha256']); self.assertEqual(['libOpenCL.so','libc.so','libdl.so','libm.so'],r['dynamic_dependencies'])
  m=ROOT/r['kernel_sources']['manifest']; self.assertEqual(r['kernel_sources']['manifest_sha256'],sha(m)); self.assertEqual(170,len(m.read_text().splitlines())); self.assertFalse(r['kernel_sources']['binary_kernel_library'])
  b=(EXP/'tools/build_android.sh').read_text()
  for x in ('-DGGML_OPENCL=ON','-DGGML_OPENCL_EMBED_KERNELS=ON','-DGGML_OPENCL_USE_ADRENO_KERNELS=ON','-DGGML_OPENCL_USE_ADRENO_BIN_KERNELS=OFF','6fe718c31a45fe25151362a72ef041c3a1047cbd','b7bd2803acc779c03d96588e9ca9e9568a18698a','flock -w 1800'): self.assertIn(x,b)
 def test_phone_and_provider_gates(self):
  s=(EXP/'tools/run_phone.sh').read_text(); c=(EXP/'tools/run_client.py').read_text()
  self.assertIn('/data/local/tmp/vibevoice-0035-qwen-3.5-2b-android-opencl-gpu',s); self.assertIn('flock -n 9',s); self.assertIn('--device GPUOpenCL --gpu-layers 25',s); self.assertNotIn('/sdcard',s)
  for x in ('offloaded 25/25 layers to GPU','OpenCL model buffer size','OpenCL compute buffer size','Adreno[^\\n]*740','POST /slots/0?action=erase','server_timings.get("cache_n") != 0'): self.assertIn(x,c)
  self.assertIn('range(1, 6)',c)
 def test_provider_smoke_is_hash_bound_but_not_canonical(self):
  base=EXP/'results/android-opencl-smoke'; result=json.loads((base/'result.json').read_text()); smoke=self.c['viability_smoke']
  self.assertEqual(smoke['result_sha256'],sha(base/'result.json')); self.assertEqual(smoke['checksum_manifest_sha256'],sha(base/'SHA256SUMS'))
  self.assertEqual('android_smoke',result['scope']); self.assertEqual(1,len(result['runs'])); self.assertEqual(64,result['runs'][0]['output_tokens']); self.assertEqual('max_tokens',result['runs'][0]['stop_reason']); self.assertEqual([],result['runs'][0]['reset_validation']['errors']); self.assertTrue(result['runs'][0]['output_sanity']['looks_sensible'])
  proof=result['route']['backend_proof']; self.assertEqual({},proof['forbidden_matches']); self.assertEqual(25,result['route']['observed_offloaded_layers']); self.assertIn('Adreno740v2',proof['gpu_model_proof']); self.assertEqual('verified_absent',result['stage_and_cleanup']['cleanup_state'])
 def test_complete_campaign_shape_hashes_isolation_and_provider(self):
  base=EXP/'results/android-opencl-campaign'; d=json.loads((base/'result.json').read_text()); c=self.c['completed_campaign']
  self.assertEqual(c['result_sha256'],sha(base/'result.json')); self.assertEqual(c['checksum_manifest_sha256'],sha(base/'SHA256SUMS')); self.assertEqual('complete',d['status']); self.assertEqual(16,len(d['runs']))
  ids=['first-short-01']+[f'short-{i:02d}' for i in range(1,6)]+[f'medium-{i:02d}' for i in range(1,6)]+[f'long-{i:02d}' for i in range(1,6)]; self.assertEqual(ids,[r['id'] for r in d['runs']])
  proof=d['route']['backend_proof']; self.assertEqual({},proof['forbidden_matches']); self.assertIn('Adreno740v2',proof['gpu_model_proof']); self.assertEqual(25,d['route']['observed_offloaded_layers'])
  counts={'short':174,'medium':597,'long':1926}
  for r in d['runs']:
   self.assertEqual('complete',r['status']); self.assertEqual('eos',r['stop_reason']); self.assertEqual([],r['reset_validation']['errors']); self.assertEqual(0,r['server_timings']['cache_n']); self.assertEqual(counts[r['tier']],r['server_timings']['prompt_n']); self.assertTrue(r['output_sanity']['looks_sensible']); self.assertEqual(r['output_sha256'],sha(base/r['output_path'])); self.assertFalse(r['request_isolation']['reset_included_in_total_request']); self.assertFalse(r['request_isolation']['model_remap_or_reload']); self.assertFalse(r['request_isolation']['accelerator_recompilation']); self.assertFalse(r['request_isolation']['retained_prompt_or_kv_reuse'])
  self.assertEqual('verified_absent',d['stage_and_cleanup']['cleanup_state']); self.assertGreater(d['gpu_telemetry']['busy_percentage_max'],0)
 def test_claim_is_not_gpu_exclusive(self):
  x=self.c['route_rationale']['offload_claim_boundary']; self.assertIn('CPU retains',x); self.assertIn('not GPU-exclusive',x)
if __name__=='__main__': unittest.main()

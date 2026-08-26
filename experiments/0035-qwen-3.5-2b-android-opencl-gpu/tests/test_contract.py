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
  self.assertIn('/data/local/tmp/vibevoice-0035-qwen-3.5-2b-android-opencl-gpu',s); self.assertIn('flock -n 9',s); self.assertIn('--device GPUOpenCL0 --gpu-layers 25',s); self.assertNotIn('/sdcard',s)
  for x in ('offloaded 25/25 layers to GPU','OpenCL model buffer size','OpenCL compute buffer size','Adreno[^\\n]*740','POST /slots/0?action=erase','server_timings.get("cache_n") != 0'): self.assertIn(x,c)
  self.assertIn('range(1, 6)',c)
 def test_claim_is_not_gpu_exclusive(self):
  x=self.c['route_rationale']['offload_claim_boundary']; self.assertIn('CPU retains',x); self.assertIn('not GPU-exclusive',x)
if __name__=='__main__': unittest.main()

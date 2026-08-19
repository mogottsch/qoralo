import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class HybridResult(unittest.TestCase):
 def test_protocol(self):
  p=json.loads((ROOT/'protocol.json').read_text());m=p['matched_contract'];self.assertEqual(hashlib.sha256(m['text'].encode()).hexdigest(),m['text_sha256']);self.assertIn('mixed',p['route']);self.assertEqual(m['device'],'R5CW81PR8SY / SM-S918B / SM8550')
 def test_mixed_provider_and_physical_proof(self):
  r=json.loads((ROOT/'results/hybrid-phone.json').read_text());a=r['provider_assignment_instrumented_one_run']['aggregate'];self.assertGreater(a['cpu_events'],0);self.assertGreater(a['qnn_events'],0);self.assertEqual(a['qnn_events'],r['physical_htp_evidence']['qnn_partition_executions']);self.assertTrue(r['runtime']['cpu_fallback']);self.assertEqual(r['runtime']['route'],'mixed; not full HTP')
 def test_performance_and_non_equivalence(self):
  r=json.loads((ROOT/'results/hybrid-phone.json').read_text());self.assertGreater(r['performance_without_profiling']['warm']['rtf_median'],r['cpu_baseline_0012']['warm_rtf_median']);self.assertFalse(r['output_comparison_to_cpu']['same_length']);self.assertFalse(r['output_comparison_to_cpu']['accepted_equivalent']);self.assertTrue(r['output']['finite'] and r['output']['non_silent'] and r['output']['unclipped'])
 def test_phone_cleanup(self):
  r=json.loads((ROOT/'results/hybrid-phone.json').read_text());self.assertEqual(r['phone_safety']['cleanup'],'verified absent');self.assertTrue(r['phone_safety']['lock_held'] and r['phone_safety']['adb_lock_fd_closed'])
if __name__=='__main__':unittest.main()

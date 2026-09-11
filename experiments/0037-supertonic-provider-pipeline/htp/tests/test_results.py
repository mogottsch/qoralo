"""Committed non-sensitive result invariants; no model/device/audio execution."""
import json
from pathlib import Path
import unittest

RESULTS=Path(__file__).resolve().parents[1]/'results'


def load(name):
    return json.loads((RESULTS/name).read_text())


class ResultEvidence(unittest.TestCase):
    def test_exact_wav_qualified_once_no_inherited_verdict(self):
        run=load('first-chapter-01.json'); asr=load('asr-first-chapter-01.json'); comparison=load('comparison-01.json')
        self.assertEqual(run['wav_sha256'],'0ddfc170d5fca1a11018d68fea6a403175d422ca5b454f1cc9a6bbcddc287209')
        self.assertEqual(run['wav_sha256'],asr['wav_sha256'])
        self.assertEqual(run['wav_sha256'],comparison['HTP']['wav_sha256'])
        self.assertEqual(asr['logical_asr_passes'],1)
        self.assertIsNone(asr['settings']['initial_prompt'])
        self.assertEqual(asr['reference_words'],495)
        self.assertEqual(asr['substitutions']+asr['deletions']+asr['insertions'],15)
        self.assertAlmostEqual(asr['word_error_rate'],15/495)
        self.assertEqual(asr['exactly_matched_reference_words'],480)
        self.assertEqual(comparison['current_listening_verdicts'],{'CPU':'not_reviewed','HTP':'not_reviewed'})

    def test_own_extents_noise_and_exact_assembly(self):
        run=load('first-chapter-01.json'); comparison=load('comparison-01.json')
        self.assertEqual(len(run['chunks']),15)
        self.assertEqual(run['total_gap_frames'],14*13230)
        self.assertEqual(run['emitted_frames'],sum(c['native_latent']*3072 for c in run['chunks'])+14*13230)
        offset=0
        for c in run['chunks']:
            self.assertEqual(c['noise_offset'],offset)
            self.assertEqual(c['emitted_frames'],c['native_latent']*3072)
            self.assertEqual(set(c['edge_index_sha256']),{'2','4','8','16'})
            offset+=144*c['native_latent']
        self.assertEqual(offset,run['noise_stream_draws_consumed'])
        self.assertEqual(comparison['exact_noise_match_chunk_indices'],list(range(6)))
        self.assertEqual([c['index'] for c in comparison['noise_correspondence'] if c['cpu_nativeL']!=c['htp_nativeL']],[6,14])
        self.assertTrue(run['assembly_verified_byte_exact'])
        self.assertTrue(run['own_native_extent_noise_indices_verified'])

    def test_htp_proof_cleanup_and_original_gate_failure(self):
        run=load('first-chapter-01.json'); physical=load('physical-evidence-01.json')
        self.assertTrue(run['cpu_fallback_disabled'])
        self.assertFalse(run['profiling_enabled'])
        self.assertEqual((run['session_constructor_count'],run['max_resident_sessions'],run['neural_Run_calls']),(32,4,165))
        for key in ['cdsp_library_loaded','qnn_v73_skel_opened','qnn_skel_remote_handle_opened','user_pd_created',
                    'dsp_queue_created','remote_handles_closed','app_data_unchanged','remote_removed']:
            self.assertTrue(physical[key])
        self.assertIsNone(physical['counters'])
        self.assertEqual(physical['installed_apks_before'],physical['installed_apks_after'])
        self.assertEqual(load('native-boundary-full-source-01.json')['status'],'padding_gate_failed')
        self.assertTrue(run['strict_source_numerical_gate'].startswith('failed'))

    def test_timing_boundaries_and_session_lifecycle(self):
        run=load('first-chapter-01.json')
        generation=run['generation_wall_including_interleaved_setup_seconds']
        excluding=generation-run['interleaved_constructor_seconds']-run['interleaved_teardown_seconds']
        self.assertAlmostEqual(excluding,run['generation_wall_excluding_interleaved_lifecycle_seconds'])
        self.assertAlmostEqual(generation/run['emitted_audio_seconds'],run['rtf_generation_including_gaps_and_interleaved_setup'])
        self.assertLessEqual(run['first_native_wave_ready_from_entry_seconds'],run['first_chunk_playable_from_entry_seconds'])
        self.assertLess(run['first_chunk_playable_from_entry_seconds'],run['entry_to_complete_seconds'])
        self.assertEqual(run['phone_lifecycle']['chunks_pulled_before_chapter_file'],14)
        self.assertEqual(run['phone_lifecycle']['completed_chunks_pulled'],15)
        self.assertIn('cache_capacity1',run['session_lifecycle'])


if __name__=='__main__':
    unittest.main()

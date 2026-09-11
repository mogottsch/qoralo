"""Run with exp0007's pinned supertonic1.3.1 venv; no neural inference."""
import hashlib
import io
import json
from pathlib import Path
import unittest
import numpy as np
import soundfile as sf
from supertonic import config,core,utils

ROOT=Path(__file__).resolve().parents[1]

class RecipeTests(unittest.TestCase):
    def test_pinned_recipe(self):
        self.assertEqual(config.MODEL_CONFIGS['supertonic-3']['revision'],'724fb5abbf5502583fb520898d45929e62f02c0b')
        self.assertEqual((config.DEFAULT_TOTAL_STEPS,config.DEFAULT_SPEED,config.DEFAULT_MAX_CHUNK_LENGTH,config.DEFAULT_SILENCE_DURATION),(8,1.05,300,0.3))
    def test_raw_paragraphs_split_before_whitespace_cleanup(self):
        self.assertEqual(utils.chunk_text('First.\n\nSecond.'),['First.','Second.'])
        self.assertEqual(utils.chunk_text('First. Second.'),['First. Second.'])
    def test_overlong_sentence_is_not_invented_fallback_split(self):
        sentence='word '*100+'.'
        self.assertEqual(utils.chunk_text(sentence,300),[sentence.strip()])
    def test_abbreviation_and_order(self):
        value='Dr. Smith speaks. Then comes another sentence.'
        chunks=utils.chunk_text(value,30)
        self.assertEqual(chunks,['Dr. Smith speaks.','Then comes another sentence.'])
        self.assertEqual(''.join(''.join(chunks).split()),''.join(value.split()))
    def test_continuous_gaussian_layout(self):
        rng=np.random.RandomState(20260911);stream=rng.randn(144*(10+11+12)).astype(np.float32)
        rng=np.random.RandomState(20260911);offset=0
        for length in [10,11,12]:
            expected=rng.randn(1,144,length).astype(np.float32)
            actual=stream[offset:offset+144*length].reshape(1,144,length);offset+=144*length
            np.testing.assert_array_equal(expected,actual)
    def test_native_l_matches_source_sampler(self):
        model=object.__new__(core.Supertonic);model.sample_rate=44100;model.base_chunk_size=512;model.chunk_compress_factor=6;model.ldim=24
        state=np.random.get_state()
        try:
            for d in [1.111,3.245,10.999,22.719]:
                duration=np.array([d],dtype=np.float32)/1.05
                noise,mask=model.sample_noisy_latent(duration)
                wf=np.float32(duration[0]*np.float32(44100));native=int(np.float32(np.float32(np.float32(wf+np.float32(3072))-np.float32(1))/np.float32(3072)))
                self.assertEqual(noise.shape,(1,144,native));self.assertEqual(mask.shape,(1,1,native));self.assertTrue(np.all(mask==1))
        finally:np.random.set_state(state)
    def test_soundfile_pcm16_encoding_equivalence(self):
        values=np.random.RandomState(31).uniform(-1.2,1.2,4096).astype(np.float32)
        f=io.BytesIO();sf.write(f,values,44100,format='WAV');f.seek(0);actual,_=sf.read(f,dtype='int16')
        expected=np.clip(np.floor(np.clip(values,-1,1)*np.float32(32768)),-32768,32767).astype(np.int16)
        np.testing.assert_array_equal(expected,actual)
    def test_frozen_15_chunk_metadata(self):
        x=json.loads((ROOT/'protocol/inputs.json').read_text())
        self.assertEqual(x['chunk_count'],15)
        self.assertEqual([c['text_extent'] for c in x['chunks']],[309,213,243,153,188,298,106,212,97,239,224,236,252,229,280])
        self.assertTrue(x['source_nonwhitespace_characters_preserved_in_order'])
        self.assertEqual(x['gap_frames'],13230)
    def test_cpp_no_trimming_or_per_chunk_session_creation(self):
        text=(ROOT/'cpu/runner.cc').read_text()
        self.assertIn('r.emitted=wave.size()',text)
        self.assertIn('wav(out/("chunk-"+id(index)+".wav"),wave)',text)
        self.assertIn('if(index)assembly.insert(assembly.end(),gap,0.f)',text)
        self.assertNotIn('.AppendExecutionProvider',text)
        self.assertLess(text.index('std::make_unique<Ort::Session>'),text.index('for(int index=0;index<count;++index)'))

class ResultTests(unittest.TestCase):
    def test_single_complete_provider_pipeline(self):
        x=json.loads((ROOT/'cpu/results/first-chapter-01.json').read_text())
        self.assertEqual(x['chunk_count'],15);self.assertEqual(x['session_count'],4)
        self.assertEqual({k:v['model_run_calls'] for k,v in x['provider_evidence'].items()},{'duration':15,'text':15,'vector':120,'vocoder':15})
        self.assertEqual(x['total_gap_frames'],14*13230)
        self.assertEqual(x['emitted_frames'],x['speech_vocoder_frames']+x['total_gap_frames'])
        self.assertTrue(x['assembly_verified_exact_pcm'])
        self.assertEqual(len(x['host_chunk_availability']),15)
        self.assertLess(x['first_chunk_playable_from_entry_seconds'],x['entry_to_complete_seconds'])
        self.assertEqual(x['wav']['sha256'],'6848fcd649f11ca0b5d2ecdeb237fb3337690ead18ceb2939ba54c9e72e9a0be')
        for chunk in x['chunks']:
            self.assertEqual(chunk['emitted_frames'],chunk['native_latent']*3072)
            self.assertTrue(chunk['exact_saved_rng_correspondence'])
    def test_automatic_support_is_not_human_acceptance(self):
        x=json.loads((ROOT/'cpu/results/first-chapter-01.json').read_text())
        self.assertEqual(x['coverage_status'],'strong_automatic_support_not_human_acceptance')
        self.assertEqual(x['asr_summary']['reference_words'],495)
        self.assertEqual(x['asr_summary']['hypothesis_words'],493)
        self.assertLess(x['asr_summary']['word_error_rate'],0.03)
        self.assertEqual(x['listening_acceptance'],'not_reviewed')
        self.assertIsNone(x['warm_median_rtf'])

if __name__=='__main__':unittest.main()

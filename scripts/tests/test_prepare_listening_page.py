"""Tiny synthetic PCM fixtures only. No TTS, phone, browser or accepted-sample writes."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

spec=importlib.util.spec_from_file_location('listening',Path(__file__).resolve().parents[1]/'prepare_listening_page.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class ListeningPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.cache=self.root/'cache'
        self.wav=self.root/'fixture.wav'
        with wave.open(str(self.wav),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100);w.writeframes(b'\0\0'*441)
        self.original=self.wav.read_bytes();self.sha=hashlib.sha256(self.original).hexdigest()

    def test_real_hash_bound_wav_only_and_initially_not_reviewed(self):
        p,r=m.prepare('test-1',self.wav,self.sha,'Fixture','<script>safe text</script>',self.cache)
        self.assertEqual(self.original,(p.parent/'sample.wav').read_bytes())
        self.assertEqual(self.original,self.wav.read_bytes())
        self.assertEqual('not_reviewed',r['listening_verdict'])
        self.assertEqual(441,r['wav']['frames']);self.assertEqual(0.01,r['wav']['duration_seconds'])
        h=p.read_text();self.assertIn('<audio controls',h);self.assertIn('src="sample.wav"',h)
        self.assertIn('&lt;script&gt;',h);self.assertNotIn('<script>',h)
        self.assertNotIn('autoplay',h);self.assertNotIn('http-equiv="refresh"',h)
        self.assertIn('not a playback timestamp',h)

    def test_missing_audio_creates_no_page_or_placeholder(self):
        for path,digest in ((None,None),(self.root/'absent.wav',self.sha)):
            with self.assertRaises(ValueError):m.prepare('missing',path,digest,root=self.cache)
        self.assertFalse(self.cache.exists())

    def test_hash_mismatch_preserves_source_and_leaves_no_page(self):
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            m.prepare('bad-hash',self.wav,'0'*64,root=self.cache)
        self.assertFalse((self.cache/'bad-hash').exists())
        self.assertEqual(self.original,self.wav.read_bytes())

    def test_truncated_wav_does_not_get_a_page(self):
        self.wav.write_bytes(self.original[:-2]);sha=hashlib.sha256(self.wav.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,'Truncated'):
            m.prepare('truncated',self.wav,sha,root=self.cache)
        self.assertFalse((self.cache/'truncated').exists())

    def test_existing_sample_or_foreign_page_never_overwritten(self):
        p,r=m.prepare('existing',self.wav,self.sha,root=self.cache)
        before={x.name:x.read_bytes() for x in p.parent.iterdir()}
        with self.assertRaises(FileExistsError):m.prepare('existing',self.wav,self.sha,root=self.cache)
        self.assertEqual(before,{x.name:x.read_bytes() for x in p.parent.iterdir()})
        foreign=self.cache/'accepted-short';foreign.mkdir();(foreign/'index.html').write_text('accepted')
        with self.assertRaises(FileExistsError):m.prepare('accepted-short',self.wav,self.sha,root=self.cache)
        self.assertEqual('accepted',(foreign/'index.html').read_text())

    def test_opener_detaches_without_waiting_or_audio_playback(self):
        page,_=m.prepare('viewer',self.wav,self.sha,root=self.cache)
        process=Mock(pid=321)
        with patch.object(m.subprocess,'Popen',return_value=process) as spawn:
            self.assertEqual(321,m.open_page(page))
        args,kwargs=spawn.call_args
        self.assertEqual(['xdg-open',str(page)],args[0])
        self.assertTrue(kwargs['start_new_session']);self.assertTrue(kwargs['close_fds'])
        self.assertEqual(m.subprocess.DEVNULL,kwargs['stdin'])
        self.assertEqual(m.subprocess.DEVNULL,kwargs['stdout'])
        self.assertEqual(m.subprocess.DEVNULL,kwargs['stderr'])
        process.wait.assert_not_called()

    def test_safe_run_id_and_no_forced_duration_gate(self):
        with self.assertRaises(ValueError):m.prepare('../escape',self.wav,self.sha,root=self.cache)
        p,r=m.prepare('natural-duration',self.wav,self.sha,root=self.cache)
        self.assertTrue(p.exists());self.assertEqual(0.01,r['wav']['duration_seconds'])


if __name__=='__main__':unittest.main()

import importlib.util, json, shutil, tempfile, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('supertonic_validate',HERE/'validate.py'); mod=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(mod)
class TrackTests(unittest.TestCase):
 def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)/'track'; shutil.copytree(HERE,self.root,ignore=shutil.ignore_patterns('__pycache__'))
 def tearDown(self): self.tmp.cleanup()
 def mutate(self,name,fn):
  p=self.root/name; data=json.loads(p.read_text()); fn(data); p.write_text(json.dumps(data))
 def assert_bad(self): self.assertRaises(mod.ValidationError,mod.validate,self.root)
 def test_committed_track(self): mod.validate(HERE)
 def test_wrong_date_and_fp32_substitution_fail(self):
  self.mutate('inventory.json',lambda x:x.update(archive_filename='sherpa-onnx-supertonic-3-tts-int8-2026-05-12.tar.bz2')); self.assert_bad()
  shutil.rmtree(self.root); shutil.copytree(HERE,self.root,ignore=shutil.ignore_patterns('__pycache__'))
  self.mutate('inventory.json',lambda x:x['files'][2].update(path='duration_predictor.onnx')); self.assert_bad()
 def test_guessed_or_drifted_style_fails(self):
  self.mutate('m1-proof.json',lambda x:x.update(selected_sid=0)); self.assert_bad()
  shutil.rmtree(self.root); shutil.copytree(HERE,self.root,ignore=shutil.ignore_patterns('__pycache__'))
  self.mutate('m1-proof.json',lambda x:x['source']['inputs'][0].update(path='voice_styles/Z.json')); self.assert_bad()
 def test_non_english_qnn_or_extra_threads_fail(self):
  for key,value in [('language','fr'),('provider','qnn'),('num_threads',2)]:
   shutil.rmtree(self.root); shutil.copytree(HERE,self.root,ignore=shutil.ignore_patterns('__pycache__'))
   self.mutate('android-descriptor.json',lambda x,k=key,v=value:x.update({k:v})); self.assert_bad()
 def test_config_language_and_paths_are_exact(self):
  self.mutate('sherpa-config.json',lambda x:x.update(lang='fr')); self.assert_bad()
  shutil.rmtree(self.root); shutil.copytree(HERE,self.root,ignore=shutil.ignore_patterns('__pycache__'))
  self.mutate('sherpa-config.json',lambda x:x.update(vocoder='assets/vocoder.int8.onnx')); self.assert_bad()
 def test_missing_notices_fail(self):
  self.mutate('licenses.json',lambda x:x['notices'].pop()); self.assert_bad()
  shutil.rmtree(self.root); shutil.copytree(HERE,self.root,ignore=shutil.ignore_patterns('__pycache__'))
  (self.root/'licenses/LICENSE.OpenRAIL-M').unlink(); self.assert_bad()
 def test_host_smoke_cannot_be_performance_evidence(self):
  self.mutate('host-smoke.json',lambda x:x.update(rtf=.1)); self.assert_bad()
if __name__=='__main__': unittest.main()

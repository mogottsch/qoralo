import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

PROJECT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROJECT/'tools'))
from duration_phone_guard import GuardError
from short_product_preservation import TABLES,compare_export,compare_files
from run_short_product_gate import EXPORT_SHA

class ExportOnlyScopeTests(unittest.TestCase):
    def fixture(self):
        raw=(PROJECT/'app/src/androidTest/assets/short-product-export/contract.json').read_bytes()
        self.assertEqual(EXPORT_SHA,hashlib.sha256(raw).hexdigest());scope=json.loads(raw)
        before={t:[] for t in TABLES};before['episodes']=[dict(scope['episode']),{'id':'other','title':'fixed'}]
        before['playback_state']=[{**scope['playback'],'updatedAtEpochMs':1}]
        before['generation_jobs']=[{'id':scope['audioJobId'],'episodeId':scope['episode']['id'],'kind':'AUDIO','status':'COMPLETE'}]
        before['chapter_audio']=copy.deepcopy(scope['chapters'])
        before['installed_models']=[{'id':'supertonic-3','manifestSha256':'unchanged'}]
        return before,scope
    def test_only_owned_playback_timestamp_may_change(self):
        before,scope=self.fixture();after=copy.deepcopy(before);after['playback_state'][0]['updatedAtEpochMs']=2
        self.assertTrue(compare_export(before,after,scope)['allDurableRowsUnchangedExceptOwnedPlaybackTimestamp'])
        compare_export(before,before,scope)
    def test_any_job_model_catalog_episode_or_playback_value_change_rejected(self):
        before,scope=self.fixture()
        for table,key,value in [('episodes','title','other'),('generation_jobs','status','FAILED'),('installed_models','manifestSha256','new'),('playback_state','positionMs',0)]:
            after=copy.deepcopy(before);after[table][0][key]=value
            with self.subTest(table=table),self.assertRaises(GuardError):compare_export(before,after,scope)
        after=copy.deepcopy(before);after['generation_jobs'].append({'id':'new','episodeId':scope['episode']['id']})
        with self.assertRaises(GuardError):compare_export(before,after,scope)
    def test_no_new_episode_files_or_changed_master_are_allowed(self):
        files={'files/episodes/owned/final/episode.wav':'a'*64}
        compare_files(files,files,None)
        with self.assertRaises(GuardError):compare_files(files,{**files,'files/episodes/owned/new.wav':'b'*64},None)
        with self.assertRaises(GuardError):compare_files(files,{next(iter(files)):'c'*64},None)
    def test_export_method_never_arms_models_or_writes_destination_directly(self):
        source=(PROJECT/'app/src/androidTest/java/dev/vibevoice/podcast/e2e/ShortProductE2eTest.kt').read_text()
        method=source.split('@Test fun exportExistingReadyEpisode()',1)[1].split('private fun verifyAssembly',1)[0]
        for forbidden in ['Lock & create','Send change request','generateAudio(', 'openOutputStream(', 'writeRevision(', 'createEpisode(', 'icon("Play")','write(marker']:
            self.assertNotIn(forbidden,method)
        self.assertIn('icon("Export episode"); saveThroughLocalDocumentsUi',method)
        self.assertIn('instrumentation.context.assets.open("short-product-export/contract.json")',method)
        self.assertIn('check(!root.exists() && root.mkdirs())',method)
        self.assertIn('"newModelCalls", 0',method)
    def test_rooted_downloads_selector_uses_bounded_actual_click_ancestor(self):
        source=(PROJECT/'app/src/androidTest/java/dev/vibevoice/podcast/e2e/ShortProductE2eTest.kt').read_text()
        self.assertNotIn('downloads.first { it.parent?.isClickable',source)
        self.assertIn('endsWith(":id/roots_list")',source)
        self.assertIn('walk(roots).single { it.viewIdResourceName == "android:id/title" && it.text?.toString() == "Downloads" }',source)
        self.assertIn('clickNative(downloads, stopBefore = roots)',source)
        self.assertIn('target != stopBefore',source)
        self.assertIn('target.actionList.none { it.id == AccessibilityNodeInfo.ACTION_CLICK }',source)
        controller=(PROJECT/'tools/run_short_product_gate.py').read_text()
        self.assertIn('host_seconds=150 if export_only',controller)
        self.assertIn("'appReinstalled':False",controller)
        self.assertIn('compare_export(rows(before),rows(after)',controller)

if __name__=='__main__':unittest.main()

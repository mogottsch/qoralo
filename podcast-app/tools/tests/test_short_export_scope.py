import copy
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
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
    def test_explicit_owned_paused_position_boundary_and_timestamp(self):
        before,scope=self.fixture();after=copy.deepcopy(before);after['playback_state'][0]['updatedAtEpochMs']=2
        for delta in [-100,0,100]:
            after['playback_state'][0]['positionMs']=before['playback_state'][0]['positionMs']+delta
            result=compare_export(before,after,scope)
            self.assertTrue(result['allDurableRowsUnchangedExceptAuthorizedOwnedPlaybackPersistence'])
            self.assertEqual(delta,result['ownedPlayback']['positionDeltaMs'])
        for delta in [-101,101]:
            after['playback_state'][0]['positionMs']=before['playback_state'][0]['positionMs']+delta
            with self.assertRaises(GuardError):compare_export(before,after,scope)
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
        source=(PROJECT/'app/src/androidTest/java/dev/qoralo/podcast/e2e/ShortProductE2eTest.kt').read_text()
        method=source.split('@Test fun exportExistingReadyEpisode()',1)[1].split('private fun verifyAssembly',1)[0]
        for forbidden in ['Lock & create','Send change request','generateAudio(', 'openOutputStream(', 'writeRevision(', 'createEpisode(', 'icon("Play")','write(marker']:
            self.assertNotIn(forbidden,method)
        self.assertIn('icon("Export episode"); saveThroughLocalDocumentsUi',method)
        self.assertIn('instrumentation.context.assets.open("short-product-export/contract.json")',method)
        self.assertIn('check(!root.exists() && root.mkdirs())',method)
        self.assertIn('"newModelCalls", 0',method)
    def test_rooted_downloads_selector_uses_bounded_actual_click_ancestor(self):
        source=(PROJECT/'app/src/androidTest/java/dev/qoralo/podcast/e2e/ShortProductE2eTest.kt').read_text()
        self.assertNotIn('downloads.first { it.parent?.isClickable',source)
        self.assertIn('endsWith(":id/roots_list")',source)
        self.assertIn('waitUntil("actionable local Downloads drawer row", 15_000)',source)
        self.assertIn('SafRootReadiness.downloadsAction(current, safNodes)',source)
        predicate=(PROJECT/'app/src/androidTest/java/dev/qoralo/podcast/e2e/SafRootReadiness.java').read_text()
        self.assertIn('"android:id/title".equals(nodes.id(node)) && "Downloads".equals(nodes.text(node))',predicate)
        self.assertIn('!Objects.equals(action, list)',predicate)
        self.assertIn('rootAction != null',source)
        self.assertNotIn('waitUntil("Downloads root")',source)
        self.assertIn('target != stopBefore',source)
        self.assertIn('target.actionList.none { it.id == AccessibilityNodeInfo.ACTION_CLICK }',source)
        controller=(PROJECT/'tools/run_short_product_gate.py').read_text()
        self.assertIn('host_seconds=150 if export_only',controller)
        self.assertIn("'appReinstalled':False",controller)
        self.assertIn('compare_export(rows(before),rows(after)',controller)
    def test_actual_shared_predicate_rejects_breadcrumb_and_delayed_list_until_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            source=PROJECT/'app/src/androidTest/java/dev/qoralo/podcast/e2e/SafRootReadiness.java'
            fixture=PROJECT/'tools/tests/fixtures/SafRootReadinessFixture.java'
            subprocess.run(['javac','-d',temp,str(source),str(fixture)],check=True,timeout=30)
            subprocess.run(['java','-cp',temp,'dev.qoralo.podcast.e2e.SafRootReadinessFixture'],check=True,timeout=10)

if __name__=='__main__':unittest.main()

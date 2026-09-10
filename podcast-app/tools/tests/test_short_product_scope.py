import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROJECT/'tools'))
from duration_phone_guard import GuardError
from short_product_preservation import TABLES, compare, compare_files, parse_inventory
import run_short_product_gate as short_controller
from run_short_product_gate import CONTRACT_SHA, PACKS, disarm_owned_control

class ShortProductScopeTests(unittest.TestCase):
    def state(self):
        value={t:[] for t in TABLES}
        value['episodes']=[{'id':'old','title':'private old title'}]
        value['generation_jobs']=[{'id':'old-job','episodeId':'old','status':'FAILED'}]
        return value
    def test_only_new_owned_rows_and_existing_failed_history_are_allowed(self):
        old=self.state();new=copy.deepcopy(old)
        new['episodes'].append({'id':'owned','title':'new'})
        new['script_revisions'].append({'id':'r1','episodeId':'owned'})
        new['chapters'].append({'rowId':'c1','revisionId':'r1'})
        result=compare(old,new,'owned')
        self.assertTrue(result['existingUserRowsUnchanged'])
        self.assertEqual(1,result['tables']['chapters']['ownedAdded'])
    def test_old_mutation_deletion_and_unowned_additions_rejected(self):
        for change in ['mutate','delete','unowned']:
            old=self.state();new=copy.deepcopy(old)
            if change=='mutate':new['episodes'][0]['title']='changed'
            if change=='delete':new['generation_jobs']=[]
            if change=='unowned':new['episodes'].append({'id':'alien','title':'x'})
            with self.assertRaises(GuardError):compare(old,new,'owned')
    def test_file_bytes_and_owner_prefix_are_preserved(self):
        old=parse_inventory(('a'*64+'  files/episodes/old/source.txt\n').encode())
        new=dict(old,**{'files/episodes/owned/chapter.wav':'b'*64})
        self.assertEqual(1,compare_files(old,new,'owned')['ownedAddedFiles'])
        with self.assertRaises(GuardError):compare_files(old,{**new,'files/episodes/old/source.txt':'c'*64},'owned')
        with self.assertRaises(GuardError):compare_files(old,{**new,'files/episodes/other/x':'d'*64},'owned')
    def test_route_catalog_update_is_narrow_and_hash_pinned(self):
        old=self.state();new=copy.deepcopy(old)
        new['installed_models']=[{'id':'supertonic-3','route':'SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP','manifestSha256':PACKS['supertonic-3']}]
        compare(old,new,'owned')
        new['installed_models'][0]['manifestSha256']='0'*64
        with self.assertRaises(GuardError):compare(old,new,'owned')
    def test_catalog_exact_ids_preserve_long_rows_and_reject_deletions(self):
        old=self.state()
        old['installed_models']=[{'id':'long-other','route':'SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP','manifestSha256':'legacy'},
                                 {'id':'gemma-4-e2b','route':'GEMMA_4_E2B_LITERT_GPU','manifestSha256':PACKS['gemma-4-e2b']}]
        compare(old,copy.deepcopy(old),'owned')
        for removed in (0,1):
            new=copy.deepcopy(old);new['installed_models'].pop(removed)
            with self.assertRaises(GuardError):compare(old,new,'owned')
        new=copy.deepcopy(old);new['installed_models'][1]['route']='wrong'
        with self.assertRaises(GuardError):compare(old,new,'owned')
    def test_control_cleanup_proves_absence_or_removes_only_exact_owned_bytes(self):
        raw=json.dumps({'runId':'short-product-test','episodeId':'owned','contractSha256':CONTRACT_SHA}).encode()
        class Fake:
            counter=0
            def __init__(self,out,current):self.out=out;self.current=current;self.removals=[]
            def run(self,*args,**kwargs):
                self.counter+=1;(self.out/f'{self.counter:03d}-command.stdout').write_bytes(self.current)
            def shell(self,script):self.removals.append(script);return 'ABSENT\n'
        with tempfile.TemporaryDirectory() as temp:
            for i,current in enumerate((b'ABSENT\n',raw,b'{"foreign":true}')):
                out=Path(temp)/str(i);out.mkdir();device=Fake(out,current)
                if i==2:
                    with self.assertRaises(GuardError):disarm_owned_control(device,out,'short-product-test','owned',raw)
                    self.assertEqual([],device.removals)
                else:
                    receipt=disarm_owned_control(device,out,'short-product-test','owned',raw)
                    self.assertTrue(receipt['controlAbsent']);self.assertEqual(i,len(device.removals))
                    if i: self.assertIn('rm files/short-product-e2e/active.json',device.removals[0])
    def test_contract_short_selector_and_long_source_pin_unchanged(self):
        raw=(PROJECT/'app/src/debug/assets/short-product-e2e/contract.json').read_bytes()
        self.assertEqual(CONTRACT_SHA,hashlib.sha256(raw).hexdigest())
        value=json.loads(raw);self.assertEqual(2,value['logicalTtsRequests']);self.assertEqual(190,value['maxNormalizedCodepoints'])
        self.assertEqual(['source_notes','outline','chapter','chapter'],value['scriptRequests'])
        self.assertEqual(['edit'],value['editRequests']);self.assertFalse(value['collectProfiles'])
        baseline=subprocess.check_output(['git','show','70a6ac6:podcast-app/config/normal-supertonic-pack.properties'],cwd=PROJECT.parent)
        self.assertEqual(baseline,(PROJECT/'config/normal-supertonic-pack.properties').read_bytes())
        gradle=(PROJECT/'app/build.gradle.kts').read_text();self.assertIn('podcast.shortProductE2e',gradle)
        self.assertIn('if (shortProductE2e) "config/short-product-e2e.properties" else "config/normal-supertonic-pack.properties"',gradle)
    def test_wal_parser_failure_does_not_suppress_the_actual_file_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp);events=[]
            def inventory(device,output,label):
                events.append('files');(output/'.private-user-files').mkdir()
                (output/'.private-user-files/after.stdout').write_text('retained current inventory')
                return {}
            guard=type('Guard',(),{'snapshot':lambda self,*args: events.append('snapshot') or {}})()
            with patch.object(short_controller,'private_inventory',side_effect=inventory),patch.object(short_controller,'validate_snapshot',side_effect=GuardError('injected WAL parse failure')):
                with self.assertRaisesRegex(GuardError,'injected WAL'):
                    short_controller.capture_and_validate_after(object(),guard,out,{'errors':[]})
            self.assertEqual(['files','snapshot','snapshot'],events)
            self.assertTrue((out/'.private-user-files/after.stdout').is_file())
    def test_post_file_capture_is_independent_and_precedes_row_validation(self):
        controller=(PROJECT/'tools/run_short_product_gate.py').read_text()
        self.assertLess(controller.index("files_after=private_inventory(device,out,'after')"), controller.index('validate_snapshot(after)'))
        self.assertIn("except Exception as error:cleanup['errors'].append({'phase':'post-file-inventory'",controller)
        self.assertIn("require(files_after is not None,'post-file inventory unavailable",controller)
    def test_library_fix_only_names_the_real_action_and_selector_uses_it(self):
        path='app/src/main/java/dev/vibevoice/podcast/ui/LibraryScreen.kt'
        original=subprocess.check_output(['git','show','3957b8d:podcast-app/'+path],cwd=PROJECT.parent).decode()
        expected=original.replace('icon = { Icon(Icons.Default.Add, contentDescription = null) },',
            '// Material3 clears the animated text\'s semantics; the icon must name the action.\n                                icon = { Icon(Icons.Default.Add, contentDescription = "New episode") },')
        self.assertEqual(expected,(PROJECT/path).read_text())
        driver=(PROJECT/'app/src/androidTest/java/dev/vibevoice/podcast/e2e/ShortProductE2eTest.kt').read_text()
        self.assertIn('hasClickAction() and (hasContentDescription("New episode") or hasText("New episode"))',driver)
        self.assertNotIn('useUnmergedTree',driver)
    def test_observer_seams_do_not_override_normal_limits_or_profiles(self):
        source=(PROJECT/'app/src/debug/java/dev/vibevoice/podcast/e2e/ShortProductDiagnostics.kt').read_text()
        self.assertIn('conversation.sendMessage(request).toString()',source)
        self.assertNotIn('sendMessageAsync',source)
        self.assertNotIn('enableTtsOnly',source);self.assertNotIn('qnnProfileDirectory',source)
        self.assertIn('value.volume = 0f',source);self.assertNotIn('AudioManager',source)
        self.assertIn('require(app.repository.episode(episode).reviewEnabled)',source)
        vm=(PROJECT/'app/src/main/java/dev/vibevoice/podcast/ui/PodcastViewModel.kt').read_text()
        self.assertLess(vm.index('RuntimeDiagnostics.beforeExport'),vm.index('openOutputStream'))
        player=(PROJECT/'app/src/main/java/dev/vibevoice/podcast/ui/PlayerScreen.kt').read_text()
        self.assertLess(player.index('RuntimeDiagnostics.configurePlayer'),player.index('prepare()'))
        driver=(PROJECT/'app/src/androidTest/java/dev/vibevoice/podcast/e2e/ShortProductE2eTest.kt').read_text()
        for forbidden in ['generateScript(', 'generateAudio(', 'commitGeneratedScript(', 'setContent {', 'testPackProvider', 'MediaStore', 'FLAG_ACTIVITY_CLEAR_TASK']:
            self.assertNotIn(forbidden,driver)
        controller=(PROJECT/'tools/run_short_product_gate.py').read_text()
        self.assertNotIn("['push'",controller);self.assertNotIn('pm clear',controller)
        self.assertIn("guard.checkpoint('before-app-install')",controller)
        self.assertIn("guard.checkpoint('before-test-install')",controller)
        self.assertIn("guard.checkpoint('before-instrument')",controller)
        subprocess.run([sys.executable,'-m','py_compile',str(PROJECT/'tools/run_short_product_gate.py')],check=True)

if __name__=='__main__':unittest.main()

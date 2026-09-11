import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_user_script_diagnostic import independent_cleanup, require_safe_closure, validate_owner, compare_script
from duration_phone_guard import GuardError
from short_product_preservation import TABLES

class UserScriptDiagnosticTests(unittest.TestCase):
    def test_log_tar_or_preservation_parser_failure_never_skips_closure_or_file_capture(self):
        for fault in ('log','tar','database'):
            calls=[];errors=[]
            def action(name):
                def run():
                    calls.append(name)
                    if name==fault:raise RuntimeError('injected '+name)
                return run
            names=['ownership','log','tar','closure','files','database']
            independent_cleanup([(n,action(n)) for n in names],errors)
            self.assertEqual(names,calls);self.assertEqual(fault,errors[0]['phase'])
            self.assertLess(calls.index('files'),calls.index('database'))
    def test_closure_refuses_foreign_or_unknown_jobs_even_when_observations_fail(self):
        for job in ({'status':'RUNNING','episodeId':'foreign','kind':'SCRIPT'},
                    {'status':'QUEUED','episodeId':'foreign','kind':'SCRIPT'},
                    {'status':'RUNNING','episodeId':'owned','kind':'AUDIO'},
                    {'status':'UNKNOWN','episodeId':'owned','kind':'SCRIPT'}):
            stopped=[];errors=[]
            def close():
                require_safe_closure({'generation_jobs':[job]},'owned');stopped.append(True)
            independent_cleanup([('bad-tar',lambda: (_ for _ in ()).throw(ValueError('tar'))),('closure',close)],errors)
            self.assertEqual([],stopped);self.assertEqual(['bad-tar','closure'],[x['phase'] for x in errors])
    def test_own_script_or_idle_closure_does_not_require_tar_or_log_success(self):
        for state,owned in [({'generation_jobs':[]},None),({'generation_jobs':[{'status':'RUNNING','episodeId':'owned','kind':'SCRIPT'}]},'owned')]:
            require_safe_closure(state,owned)
        with self.assertRaises(GuardError):require_safe_closure({'generation_jobs':[{'status':'RUNNING','episodeId':'owned','kind':'SCRIPT'}]},None)
    def test_minimal_ownership_is_exact_new_episode_and_driver_identity(self):
        owned='11111111-1111-1111-1111-111111111111';candidate={'app':{'sha256':'app'},'test':{'sha256':'test'}}
        ownership={'episodeId':owned,'runId':'run','createdThroughMainUi':True}
        identity={'appApkSha256':'app','testApkSha256':'test','originalEpisodeId':'original','originalJobId':'job'}
        self.assertEqual(owned,validate_owner(ownership,identity,'run',{'original'},candidate,'original','job'))
        for field,value in [('episodeId','original'),('runId','stale'),('createdThroughMainUi',False)]:
            altered=dict(ownership,**{field:value})
            with self.assertRaises(GuardError):validate_owner(altered,identity,'run',{'original'},candidate,'original','job')
        with self.assertRaises(GuardError):validate_owner(ownership,identity,'run',{owned},candidate,'original','job')
        for field in identity:
            with self.assertRaises(GuardError):validate_owner(ownership,dict(identity,**{field:'other'}),'run',{'original'},candidate,'original','job')
    def test_script_preservation_keeps_old_rows_and_refuses_other_activity(self):
        before={t:[] for t in TABLES};before['episodes']=[{'id':'old','title':'private old'}]
        after=copy.deepcopy(before);after['episodes'].append({'id':'owned','title':'new'})
        after['generation_jobs'].append({'id':'j','episodeId':'owned','kind':'SCRIPT','status':'FAILED'})
        self.assertEqual(1,compare_script(before,after,'owned')['newScriptJobs'])
        for table,row in [('chapter_audio',{'id':'a','episodeId':'owned'}),('playback_state',{'episodeId':'owned'}),('agent_messages',{'id':'m','episodeId':'owned'})]:
            changed=copy.deepcopy(after);changed[table].append(row)
            with self.assertRaises(GuardError):compare_script(before,changed,'owned')
        changed=copy.deepcopy(after);changed['episodes'][0]['title']='altered'
        with self.assertRaises(GuardError):compare_script(before,changed,'owned')
    def test_capacity_probe_has_unconditional_outer_rollback_and_no_generation_action(self):
        src=(Path(__file__).resolve().parents[2]/'app/src/androidTest/java/dev/vibevoice/podcast/e2e/ExistingDraftCapacityTest.kt').read_text()
        self.assertIn('app.database.withTransaction {',src)
        self.assertIn('throw ProbeRollback(observed)',src)
        self.assertIn('assertIsNotEnabled()',src)
        for action in ('click("Create")','startAudio','startScript','queueScriptGeneration','performTextReplacement'):
            self.assertNotIn(action,src)
        self.assertNotIn('throw error',src)
    def test_driver_does_not_send_private_throwable_to_runner_and_no_audio_actions(self):
        src=(Path(__file__).resolve().parents[2]/'app/src/androidTest/java/dev/vibevoice/podcast/e2e/UserScriptReproductionTest.kt').read_text()
        self.assertNotIn('throw error',src)
        self.assertIn('throw AssertionError("Owned user-script diagnostic stopped;',src)
        self.assertEqual(1,src.count('click("Create")'))
        for disallowed in ('lockAndQueueAudio','startAudio','playWhenReady = true','saveThroughLocalDocumentsUi','enableUi('):self.assertNotIn(disallowed,src)
        self.assertIn('copied.sha256 == source.sha256',src)

if __name__=='__main__':unittest.main()

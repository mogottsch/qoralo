import copy
import contextlib
import io
import json
import tempfile
from unittest import mock
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
    def test_existing_edit_probe_is_one_request_no_committed_recovery_or_new_job(self):
        src=(Path(__file__).resolve().parents[2]/'app/src/androidTest/java/dev/vibevoice/podcast/e2e/ExistingEditDiagnosticTest.kt').read_text()
        self.assertEqual(1,src.count('concrete.editScript(request)'))
        self.assertIn('throw ProbeRollback(',src)
        self.assertIn('app.database.withTransaction {',src)
        self.assertIn('fileHash == revision.first.contentHash',src)
        self.assertIn('instructionHash == args.getString("editInstructionSha256")',src)
        self.assertIn('originalRequestWasNotCaptured',src)
        for token in ('throw error','queueAgentEdit(', 'applyAgentRevision(', 'queueScriptGeneration(', 'lockAndQueueAudio(', 'Process.killProcess(', 'performTextReplacement('):
            self.assertNotIn(token,src)
        self.assertIn('"Return to saved draft").performScrollTo().assertIsDisplayed().assertIsEnabled()',src)
        self.assertNotIn('"Return to saved draft").performClick()',src)
    def test_optional_observer_preserves_raw_before_optional_counters_and_does_not_change_decode(self):
        src=(Path(__file__).resolve().parents[2]/'app/src/main/java/dev/vibevoice/podcast/runtime/NativeEngines.kt').read_text()
        self.assertIn('observer: GemmaRequestObserver? = null',src)
        self.assertIn('val raw = RuntimeDiagnostics.send(conversation, request, responseFormat)',src)
        self.assertLess(src.index('observer?.responseReturned(raw)'),src.index('observer?.conversationReturned(conversation)'))
        self.assertIn('runCatching { observer?.conversationReturned(conversation) }',src)
        self.assertIn('maxNumTokens = 8_192',src);self.assertIn('"chapter", "edit" -> 4_096',src)
        self.assertIn('topK = 1, topP = 1.0, temperature = 1.0',src)
        self.assertIn('val responseSchema = responseSchemaForMode(mode)',src)
        self.assertIn('enableResponseFormat = responseFormat != null',src)
        self.assertIn('ResponseFormat::json',src)
    def test_response_format_reaches_debug_release_and_private_receipts(self):
        root=Path(__file__).resolve().parents[2]/'app/src'
        for variant in ('debug','release'):
            src=(root/variant/'java/dev/vibevoice/podcast/runtime/RuntimeDiagnostics.kt').read_text()
            self.assertIn('responseFormat: com.google.ai.edge.litertlm.ResponseFormat? = null',src)
            self.assertIn('responseFormat = responseFormat',src)
        short=(root/'debug/java/dev/vibevoice/podcast/e2e/ShortProductDiagnostics.kt').read_text()
        self.assertEqual(2,short.count('conversation.sendMessage(request, responseFormat = responseFormat)'))
        receipt=(root/'debug/java/dev/vibevoice/podcast/diagnostics/PrivateFailureReceipt.kt').read_text()
        self.assertIn('response-schema.json',receipt);self.assertIn('constrainedDecoding',receipt)
    def test_existing_edit_plan_only_never_uses_device_or_lock(self):
        import run_user_script_diagnostic as controller
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);apk=root/'app.apk';apk.write_bytes(b'local test artifact')
            candidate={'kind':'existing-edit-probe','controllerSha256':controller.digest(Path(controller.__file__)),
                'hostGuardSha256':'guard','app':{'path':str(apk),'sha256':controller.digest(apk)},
                'test':{'path':str(apk),'sha256':controller.digest(apk)}}
            path=root/'candidate.json';path.write_text(json.dumps(candidate))
            argv=['probe','--candidate',str(path),'--output',str(root/'not-created'),'--run-id','edit-probe-test',
                '--original-episode','episode','--original-job','job','--revision-id','revision',
                '--revision-sha256','hash','--edit-instruction-sha256','instruction']
            with mock.patch.object(sys,'argv',argv),mock.patch.object(controller,'host_identity',return_value={'sha256':'guard'}),\
                 mock.patch.object(controller,'Device',side_effect=AssertionError('No device in plan-only')),\
                 mock.patch.object(controller.fcntl,'flock',side_effect=AssertionError('No lock in plan-only')),contextlib.redirect_stdout(io.StringIO()) as output:
                controller.main()
            result=json.loads(output.getvalue());self.assertFalse(result['adbUsed'])
            self.assertEqual(300,result['instrumentSeconds']);self.assertIsNone(result['driverSeconds'])
            self.assertFalse((root/'not-created').exists())
    def test_no_new_episode_comparison_rejects_a_committed_recovery_or_added_edit_job(self):
        before={t:[] for t in TABLES};before['episodes']=[{'id':'original','phase':'FAILED'}]
        self.assertEqual(0,compare_script(before,copy.deepcopy(before),None)['newScriptJobs'])
        changed=copy.deepcopy(before);changed['episodes'][0]['phase']='SCRIPT_DRAFT'
        with self.assertRaises(GuardError):compare_script(before,changed,None)
        changed=copy.deepcopy(before);changed['generation_jobs'].append({'id':'new','episodeId':'original','kind':'AGENT_EDIT','status':'FAILED'})
        with self.assertRaises(GuardError):compare_script(before,changed,None)
        with self.assertRaises(GuardError):require_safe_closure({'generation_jobs':[{'status':'RUNNING','episodeId':'original','kind':'AGENT_EDIT'}]},None)

    def test_driver_does_not_send_private_throwable_to_runner_and_no_audio_actions(self):
        src=(Path(__file__).resolve().parents[2]/'app/src/androidTest/java/dev/vibevoice/podcast/e2e/UserScriptReproductionTest.kt').read_text()
        self.assertNotIn('throw error',src)
        self.assertIn('throw AssertionError("Owned user-script diagnostic stopped;',src)
        self.assertEqual(1,src.count('click("Create")'))
        for disallowed in ('lockAndQueueAudio','startAudio','playWhenReady = true','saveThroughLocalDocumentsUi','enableUi('):self.assertNotIn(disallowed,src)
        self.assertIn('copied.sha256 == source.sha256',src)

if __name__=='__main__':unittest.main()

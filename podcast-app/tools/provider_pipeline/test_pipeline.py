import importlib.util
import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(ROOT/'podcast-app/tools'))
from run_app_gate import safe_close,parse_health,require_quiet_audio,require_fresh_quiet_audio,admission_floor_kib,validate_collector_replay,REPLAY
from duration_phone_guard import GuardError
from run_publication_recovery import compare_recovery,SCOPE
from short_product_preservation import TABLES

class ProviderPipelineTests(unittest.TestCase):
    def test_synthetic_only_has_lower_floor_and_explicit_return_before_neural_entry(self):
        self.assertEqual(2048*1024,admission_floor_kib(True))
        self.assertEqual(3584*1024,admission_floor_kib(False))
        self.assertEqual(2048*1024,admission_floor_kib(False,guard_probe_only=True))
        self.assertEqual(3072*1024,admission_floor_kib(False,owned_guard=True))
        source=(ROOT/'podcast-app/tools/provider_pipeline/run_app_gate.py').read_text()
        boundary=source.index("            if synthetic_only:\n                save('synthetic-only-result.json'")
        neural=source.index("            health('health-before-inference',True)")
        self.assertIn('return # finally',source[boundary:neural])
        for name in ['PersistentPlayerRegressionTest','ProgressivePlayerRegressionTest']:
            test=(ROOT/f'podcast-app/app/src/androidTest/java/dev/vibevoice/podcast/ui/{name}.kt').read_text()
            for forbidden in ['ProviderQnnEngine(', 'ConfiguredTtsEngine(', 'ProviderNative.', 'GenerationService', 'NativeGemmaEngine(']:
                self.assertNotIn(forbidden,test)
    def test_collector_replay_requires_exact_source_apks_and_zero_model_scope(self):
        value={'status':'passed','producerOffMain':True,'playerApplicationLooper':'main','sourceDataUnchanged':True,
            'realRepoIO':True,'replay':True,'htpConcurrency':False,'sourceMasterSha256':REPLAY['masterSha256'],
            'newModelCalls':0,'newAudioJobs':0,'appApkSha256':'app','testApkSha256':'test',
            'stages':[{'stage':stage,'playerIdentity':7,'muted':True,'applicationLooper':'main','playing':True,'absolutePositionMs':1000}
                for stage in ['replay-advanced-before-fixture-complete','same-player-after-fixture-complete']]}
        validate_collector_replay(value,'app','test')
        for key,bad in [('producerOffMain',False),('playerApplicationLooper','worker'),('sourceDataUnchanged',False),('realRepoIO',False),('replay',False),('htpConcurrency',True),('sourceMasterSha256','other'),('newModelCalls',1),('newAudioJobs',1),('appApkSha256','other'),('testApkSha256','other')]:
            with self.assertRaises(GuardError):validate_collector_replay(dict(value,**{key:bad}),'app','test')
    def test_phase_consistent_budget_keeps_host_whole_start_distinct(self):
        self.assertEqual(3072*1024,admission_floor_kib(False,owned_guard=True))
        self.assertGreater(admission_floor_kib(False,owned_guard=True),(2048+600)*1024)
        source=(ROOT/'podcast-app/tools/provider_pipeline/run_app_gate.py').read_text()
        self.assertIn("validated.get('preContextFloorKiB')==2648*1024",source)
        self.assertIn("validated.get('startupMemoryCreditKiB')==0",source)
    def test_guarded_audio_reuses_only_exact_apk_completed_ui_proof(self):
        source=(ROOT/'podcast-app/tools/provider_pipeline/run_app_gate.py').read_text()
        self.assertIn("validated.get('affectedUiCases')==8",source)
        self.assertIn("validated['appApkSha256']==c['app']['sha256']",source)
        self.assertIn("validated['testApkSha256']==c['test']['sha256']",source)
        self.assertIn('if progressive and not owned_guard:',source)
    def test_guard_probe_is_non_neural_and_returns_before_audio(self):
        source=(ROOT/'podcast-app/tools/provider_pipeline/run_app_gate.py').read_text()
        start=source.index('            if guard_probe_only:\n                output=')
        end=source.index("            health('health-before-inference',True)")
        self.assertIn('return # Dedicated non-neural phase',source[start:end])
        service=(ROOT/'podcast-app/app/src/debug/java/dev/vibevoice/podcast/runtime/OwnedAudioGuardProbeService.kt').read_text()
        for forbidden in ['ProviderNative.', 'ConfiguredTtsEngine(', 'GenerationCoordinator(', 'NativeAppRuntime']:
            self.assertNotIn(forbidden,service)
        self.assertIn('START_NOT_STICKY',service)
        self.assertIn('Process.killProcess(pid)',service)
        runtime=(ROOT/'podcast-app/app/src/main/java/dev/vibevoice/podcast/runtime/ProviderQnnEngine.kt').read_text()
        self.assertEqual(2,runtime.count('catch (cancelled: CancellationException)'))
    def test_package_stop_refreshes_audio_and_probe_covers_shared_teardown(self):
        source=(ROOT/'podcast-app/tools/provider_pipeline/run_app_gate.py').read_text()
        stop=source[source.index('    def stop(state,owned):'):source.index('    owned=None;')]
        self.assertLess(stop.index('fresh_quiet_audio()'),stop.index("device.shell('am force-stop '"))
        for relative in ['app/src/main/java/dev/vibevoice/podcast/generation/GenerationCoordinator.kt','app/src/debug/java/dev/vibevoice/podcast/runtime/OwnedAudioGuardProbeService.kt']:
            self.assertIn('closeGuardedAudio(guard)',(ROOT/'podcast-app'/relative).read_text())
    def test_quiet_then_foreign_play_and_stale_unknown_close_observations_reject(self):
        quiet='PlaybackActivityMonitor dump time\n  players:\n    ID:4 -- type:AudioTrack -- u/pid:123/456 -- state:paused\n  ducked players:\n'
        require_fresh_quiet_audio(quiet,10,10.2,10.2)
        with self.assertRaises(GuardError):require_fresh_quiet_audio(quiet.replace('state:paused','state:started'),11,11.2,11.2)
        with self.assertRaises(GuardError):require_fresh_quiet_audio(quiet,10,10.2,12)
        with self.assertRaises(GuardError):require_fresh_quiet_audio(quiet,10,13,13)
        with self.assertRaises(GuardError):require_fresh_quiet_audio('unavailable',10,10.2,10.2)
    def test_current_audio_guard_ignores_history_but_preserves_active_playback_or_calls(self):
        quiet='PlaybackActivityMonitor dump time\n  players:\n    ID:4 -- type:AudioTrack -- u/pid:123/456 -- state:paused\n  ducked players:\n  history 12:00 ID:3 -- state:started\n'
        require_quiet_audio(quiet)
        with self.assertRaises(GuardError):require_quiet_audio(quiet.replace('state:paused','state:started'))
        with self.assertRaises(GuardError):require_quiet_audio(quiet+'  Actual mode = MODE_IN_COMMUNICATION\n')
        with self.assertRaises(GuardError):require_quiet_audio('unreadable')
    def test_real_format_health_fields_parse_without_weakening_resource_limits(self):
        self.assertEqual({'availableMemoryKiB':4321000,'batteryTemperatureC':28.3},
            parse_health('MemTotal:       10240000 kB\nMemAvailable:    4321000 kB\n','Current Battery Service state:\n  temperature: 283\n'))
        with self.assertRaises(GuardError):parse_health('MemAvailable: unknown','temperature: unknown')
    def test_publication_recovery_preserves_failed_attempt_and_uses_no_engine(self):
        before={t:[] for t in TABLES}
        before['episodes']=[{'id':SCOPE['episodeId'],'phase':'FAILED','lockedRevisionId':SCOPE['revisionId']}]
        before['generation_jobs']=[{'id':SCOPE['sourceJobId'],'episodeId':SCOPE['episodeId'],'kind':'AUDIO','status':'FAILED','requestedRevisionId':SCOPE['revisionId']}]
        after=copy.deepcopy(before)
        self.assertEqual(0,compare_recovery(before,after)['newNeuralCalls'])
        after['generation_jobs'][0]['status']='COMPLETE'
        with self.assertRaises(GuardError):compare_recovery(before,after)
        source=(ROOT/'podcast-app/app/src/main/java/dev/vibevoice/podcast/generation/GenerationCoordinator.kt').read_text()
        self.assertLess(source.index('if (recovery != null)'),source.index('engine=ttsFactory()'))
        self.assertIn('return // Crucially before constructing/loading any TtsEngine.',source)
        driver=(ROOT/'podcast-app/app/src/androidTest/java/dev/vibevoice/podcast/e2e/ProviderPublicationRecoveryTest.kt').read_text()
        for forbidden in ('ProviderNative','GemmaLiteRtGpuEngine','renderChapter','throw error','performClick'):
            self.assertNotIn(forbidden,driver)
    def test_only_authenticated_owned_audio_work_can_be_closed(self):
        safe_close({'generation_jobs':[]},None)
        safe_close({'generation_jobs':[{'status':'RUNNING','episodeId':'owned','kind':'AUDIO'}]},'owned')
        for row,owner in [({'status':'RUNNING','episodeId':'user','kind':'AUDIO'},'owned'),
            ({'status':'RUNNING','episodeId':'owned','kind':'SCRIPT'},'owned'),
            ({'status':'UNKNOWN','episodeId':'owned','kind':'AUDIO'},'owned'),
            ({'status':'RUNNING','episodeId':'owned','kind':'AUDIO'},None)]:
            with self.assertRaises(GuardError):safe_close({'generation_jobs':[row]},owner)
    def test_source_only_copy_is_labelled_and_audio_uses_real_ui(self):
        src=(ROOT/'podcast-app/app/src/androidTest/java/dev/vibevoice/podcast/e2e/ProviderAppIntegrationTest.kt').read_text()
        self.assertIn('no new SCRIPT inference',src)
        self.assertIn('onNodeWithContentDescription("New episode").performClick()',src)
        self.assertIn('onNodeWithText("Lock & create").performClick()',src)
        self.assertIn('copied_real_chapter_normal_audio_complete',src)
        for prohibited in ('throw error','queueScriptGeneration(','.play()','startAudio(', 'applyAgentRevision('):self.assertNotIn(prohibited,src)
    def test_no_case_specific_shapes_in_app_native_or_frontend(self):
        native=(ROOT/'podcast-app/app/src/main/cpp/provider_runtime.cpp').read_text()
        self.assertNotIn('309,213,243',native)
        self.assertIn('edges(n+1,kText+1,2)',native)
        self.assertIn('e.gaussian.next()',native)
        self.assertIn('size.native_length*kHop',native)
        self.assertIn('session.disable_cpu_ep_fallback',native)
        self.assertIn('Nonzero inactive provider latent; no repair',native)
        front=(ROOT/'podcast-app/app/src/main/java/dev/vibevoice/podcast/runtime/ProviderTextFrontend.kt').read_text()
        self.assertIn('ProviderUnicode14.normalize',front)
        self.assertIn('original == grouped',front)
    def test_plan_uses_nonce_pack_revision_and_frontend_not_mutable_status_fields(self):
        plan=(ROOT/'podcast-app/app/src/main/java/dev/vibevoice/podcast/runtime/ProviderAudioPlan.kt').read_text()
        for field in ['nonce','revisionSha256','packSha256','unicodeTableSha256','idsSha256']:
            self.assertIn('"'+field+'"',plan)
        self.assertIn('hash(bytes) == job',plan)
        self.assertIn('bytes.contentEquals(expected)',plan)
    def test_model_stage_stops_on_failed_preconditions_and_cleanup_is_independent(self):
        src=(ROOT/'podcast-app/tools/provider_pipeline/run_app_gate.py').read_text()
        self.assertIn('set -eu; mkdir -p no_backup/model-packs/',src)
        self.assertLess(src.index('before=stable(\'before\')'),src.index("health('health-after-idle-close',True)"))
        self.assertLess(src.index("health('health-after-idle-close',True)"),src.index("device.run(['install'"))
        self.assertIn("health('health-before-inference',True)",src)
        self.assertIn('independent_cleanup(actions',src)
        self.assertIn('foreign active work; never stop it',src)
        self.assertIn('os.set_inheritable(lock.fileno(),False)',src)
        self.assertLess(src.index("('files-after',files_after)"),src.index("('db-after',db_after)"))

if __name__=='__main__':unittest.main()

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(ROOT/'podcast-app/tools'))
from run_app_gate import safe_close,parse_health
from duration_phone_guard import GuardError

class ProviderPipelineTests(unittest.TestCase):
    def test_real_format_health_fields_parse_without_weakening_resource_limits(self):
        self.assertEqual({'availableMemoryKiB':4321000,'batteryTemperatureC':28.3},
            parse_health('MemTotal:       10240000 kB\nMemAvailable:    4321000 kB\n','Current Battery Service state:\n  temperature: 283\n'))
        with self.assertRaises(GuardError):parse_health('MemAvailable: unknown','temperature: unknown')
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

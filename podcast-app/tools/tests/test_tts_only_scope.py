import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from prepare_wiring_gate import PROJECT
import run_tts_only_gate as controller
from duration_phone_guard import host_identity


class TtsOnlyScopeTests(unittest.TestCase):
    def test_canonical_asset_and_contract_exactly_pin_one_app_request(self):
        root=PROJECT/'app/src/debug/assets/tts-only'
        text=(root/'canonical.txt').read_bytes();contract=(root/'contract.json').read_bytes();value=json.loads(contract)
        self.assertEqual(226,len(text));self.assertEqual('424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67',hashlib.sha256(text).hexdigest())
        self.assertEqual(controller.CONTRACT_SHA,hashlib.sha256(contract).hexdigest())
        self.assertEqual({'duration':1,'text':1,'vector':5,'vocoder':1},value['expectedSessionRunCounts'])
        self.assertEqual(1,value['ttsRequests']);self.assertEqual(0,value['gemmaRequests']);self.assertEqual(0,value['retries']);self.assertEqual(0,value['capacityProbes'])
        self.assertEqual('M1/SID5',value['voice']);self.assertEqual(1.0,value['speed']);self.assertEqual(20260813,value['seedXor'])

    def test_service_has_one_existing_render_path_no_gemma_or_capacity_probe(self):
        service=(PROJECT/'app/src/debug/java/dev/vibevoice/podcast/wiring/TtsOnlyService.kt').read_text()
        self.assertEqual(1,service.count('tts.renderChapter('));self.assertEqual(1,service.count('tts.load('))
        for forbidden in ['GemmaLiteRtGpuEngine','createOutline(','createChapter(','capacity-output','splitToSequence','System.loadLibrary']:
            self.assertNotIn(forbidden,service)
        self.assertIn('TtsOnlyContract.load',service);self.assertIn('WavInspector.inspectSupertonicOutput(output)',service)
        self.assertNotIn('output.delete',service)
        self.assertLess(service.index('tts.renderChapter('),service.index('optional("wav-metrics")'))

    def test_profile_hook_only_in_debug_and_not_production_render_options(self):
        debug=(PROJECT/'app/src/debug/java/dev/vibevoice/podcast/runtime/RuntimeDiagnostics.kt').read_text()
        release=(PROJECT/'app/src/release/java/dev/vibevoice/podcast/runtime/RuntimeDiagnostics.kt').read_text()
        self.assertIn('enableTtsOnly',debug);self.assertNotIn('enableTtsOnly',release)
        self.assertNotIn('TtsOnlyService',(PROJECT/'app/src/main/AndroidManifest.xml').read_text())
        self.assertIn('not native-buffer capture',(PROJECT/'app/src/debug/java/dev/vibevoice/podcast/wiring/TtsOnlyContract.kt').read_text())

    def test_controller_pins_new_scope_before_dispatch_and_reuses_guard(self):
        source=(PROJECT/'tools/run_tts_only_gate.py').read_text()
        self.assertIn('TtsOnlyTest',source);self.assertNotIn('DurationLoadOnlyTest',source);self.assertNotIn('RealRuntimeWiringTest',source)
        self.assertIn('--approved-tts-controller-sha256',source)
        self.assertIn('check_controller(args); guard.checkpoint("before-instrument")',source)
        self.assertIn('device.shell(command, timeout=360)',source)
        self.assertNotIn('["push"',source)
        # Current host-only eligibility correction; frozen canonical receipts keep their original guard pin.
        self.assertEqual('5ca6be91be151acd2937b5e65871a40361f9bae99ae444880eae0e29b6f2c425',host_identity()['sha256'])

    def test_private_battery_histories_never_enter_labelled_core_extract(self):
        raw='''Current Battery Service state:
  AC powered: false
  USB powered: true
  level: 73
  scale: 100
  voltage: 4088
  temperature: 321
  LearnedSleepHistory: SECRET_SLEEP_SCHEDULE
  ChargingHistory: SECRET_DATES
PODCAST_THERMAL_SECTION
Temperature{mValue=34.5, mType=0, mName=PRIVATE_SENSOR_NAME, mStatus=0}
'''
        record=controller.core_conditions(raw);serialized=json.dumps(record)
        self.assertEqual('73',record['battery']['level'])
        self.assertEqual([{'value':34.5,'type':0,'status':0}],record['thermalSamples'])
        for private in ['SECRET_SLEEP_SCHEDULE','SECRET_DATES','PRIVATE_SENSOR_NAME']:
            self.assertNotIn(private,serialized)
        self.assertIn('not raw dumpsys',record['evidenceKind'])


if __name__=='__main__':unittest.main()

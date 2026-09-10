import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_tts_long_gate as controller
import run_tts_only_gate as canonical
from duration_phone_guard import host_identity

PROJECT = controller.PROJECT


class TtsLongScopeTests(unittest.TestCase):
    def test_pinned_whole_noncanonical_text_and_bounds(self):
        root = PROJECT / 'app/src/debug/assets/tts-long'
        contract = json.loads((root / 'contract.json').read_text())
        self.assertEqual(controller.CONTRACT_SHA, hashlib.sha256((root / 'contract.json').read_bytes()).hexdigest())
        text = (root / 'narration.txt').read_bytes()
        self.assertEqual(contract['input']['sha256'], hashlib.sha256(text).hexdigest())
        normalized = re.sub(r'\s+', ' ', text.decode()).strip()  # restricted ASCII fixture, not a replacement frontend
        self.assertEqual(1324, len(normalized))
        self.assertLess(len(normalized), 2039)
        self.assertEqual(contract['input']['normalizedSha256'], hashlib.sha256(normalized.encode()).hexdigest())
        self.assertFalse(contract['input']['canonical']); self.assertFalse(contract['input']['durationForced'])
        self.assertEqual(1, contract['ttsRequests']); self.assertEqual(1, contract['capacityProbes'])
        self.assertEqual(0, contract['gemmaRequests']); self.assertEqual(0, contract['retries'])
        self.assertEqual({'verify': 60, 'load': 120, 'render': 180, 'close': 30}, contract['deadlineSeconds'])
        self.assertEqual([420, 435, 450], [contract[k] for k in ('serviceSeconds', 'driverSeconds', 'hostSeconds')])
        self.assertEqual({'duration': 1, 'text': 1, 'vector': 5, 'vocoder': 1}, contract['expectedSessionRunCounts'])

    def test_same_single_renderer_and_fail_closed_native_capacity(self):
        service = (PROJECT / 'app/src/debug/java/dev/vibevoice/podcast/wiring/TtsOnlyService.kt').read_text()
        native = (PROJECT / 'app/src/main/cpp/podcast_runtime.cpp').read_text()
        self.assertEqual(1, service.count('tts.renderChapter(')); self.assertEqual(1, service.count('tts.load('))
        self.assertIn('app.artifacts.modelPackRoot(contract.packId)', service)
        self.assertNotIn('output.delete', service)
        self.assertIn('active_latent > engine.latent_length', native)
        self.assertIn('text_length = duration_text[1]', native)
        self.assertIn('latent_length = vector_latent[2]', native)
        self.assertLess(service.index('tts.renderChapter('), service.index('optional("wav-metrics")'))

    def test_reviewed_guard_privacy_and_three_prelaunch_checkpoints_remain(self):
        self.assertIs(controller.capture_conditions, canonical.capture_conditions)
        self.assertEqual(controller.PRIVACY_SOURCE_SHA, controller.digest(PROJECT / 'tools/run_tts_only_gate.py'))
        self.assertEqual('3ad4c644a7733d1f1feeb7bbbe83532cc0be0f727f32f59dda00c951dd6e202d', host_identity()['sha256'])
        source = (PROJECT / 'tools/run_tts_long_gate.py').read_text()
        for phase in ('before-app-install', 'before-test-install', 'before-instrument'):
            self.assertIn("check_controller(args); guard.checkpoint('" + phase + "')", source)
        self.assertIn('device.shell(command, timeout=450)', source)
        self.assertIn('close_inherited_fds()', source)

    def test_existing_wrong_or_partial_namespace_is_never_replaced(self):
        class Device:
            def __init__(self, answer): self.answer = answer; self.calls = []
            def shell(self, command, **kwargs): self.calls.append(command); return self.answer
            def run(self, *args, **kwargs): raise AssertionError('must not push or overwrite')
        for answer in ('INCOMPLETE', 'UNSAFE', 'bad_hash  manifest.json'):
            with self.subTest(answer=answer):
                d = Device(answer); cleanup = {'scratchCreated': False}
                with self.assertRaisesRegex(ValueError, 'preserve it and stop'):
                    controller.stage_new_pack(d, {'manifestSha256': 'approved'}, '/data/local/tmp/test', cleanup)
                self.assertEqual(1, len(d.calls)); self.assertFalse(cleanup['scratchCreated'])

    def test_new_namespace_staging_has_only_bounded_new_destination_writes(self):
        class Device:
            def __init__(self): self.calls = []
            def shell(self, command, **kwargs):
                self.calls.append((command, kwargs))
                if command.startswith('run-as') and 'if test -L' in command: return 'ABSENT'
                if 'sha256sum no_backup/model-packs/supertonic-3/current' in command: return controller.OLD_MANIFEST_SHA + '  manifest.json'
                if 'sha256sum' in command: return 'approved  manifest.json'
                return ''
            def run(self, arguments, **kwargs): self.calls.append((arguments, kwargs)); return ''
        d = Device(); cleanup = {'scratchCreated': False}
        controller.stage_new_pack(d, {'root': '/new/local/pack', 'manifestSha256': 'approved'}, '/data/local/tmp/owned', cleanup)
        self.assertTrue(cleanup['scratchCreated'])
        pushes = [c for c in d.calls if isinstance(c[0], list)]
        self.assertEqual([(['push', '/new/local/pack', '/data/local/tmp/owned/current'], {'timeout': 180})], pushes)
        copy = next(c for c in d.calls if isinstance(c[0], str) and 'cp -R' in c[0])
        self.assertEqual(120, copy[1]['timeout']); self.assertIn(controller.PACK_ID, copy[0])
        self.assertNotIn('supertonic-3/current', copy[0])

    def test_plan_and_unapproved_execution_never_touch_device_or_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); apk = root / 'fake.apk'; apk.write_bytes(b'synthetic-plan-only')
            data = json.loads((PROJECT / 'app/src/debug/assets/tts-long/contract.json').read_text())
            item = {'path': str(apk), 'bytes': apk.stat().st_size, 'sha256': controller.digest(apk)}
            candidate = root / 'candidate.json'
            candidate.write_text(json.dumps({'kind': 'tts-long', 'sourceDirty': False, 'contractSha256': controller.CONTRACT_SHA, 'contract': data, 'app': item, 'test': item, 'modelPack': {}}))
            argv = ['run_tts_long_gate', '--candidate', str(candidate), '--output', str(root / 'out'), '--run-id', 'tts-long-host-check']
            with patch.object(controller, 'verify_local_pack'), patch.object(controller, 'Device', side_effect=AssertionError('no ADB')), patch.object(controller.fcntl, 'flock', side_effect=AssertionError('no lock')):
                with patch.object(sys, 'argv', argv): controller.main()
                with patch.object(sys, 'argv', argv + ['--execute']), patch.dict('os.environ', {}, clear=True):
                    with self.assertRaises(SystemExit): controller.main()
            self.assertFalse((root / 'out').exists())


if __name__ == '__main__':
    unittest.main()

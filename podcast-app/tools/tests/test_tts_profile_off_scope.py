import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_tts_profile_off_gate as off
import run_tts_long_gate as previous

PROJECT = off.PROJECT


class ProfileOffScopeTests(unittest.TestCase):
    def test_only_pinned_observability_changes_in_whole_request(self):
        old = json.loads((PROJECT / 'app/src/debug/assets/tts-long/contract.json').read_text())
        path = PROJECT / 'app/src/debug/assets/tts-long-profile-off/contract.json'
        new = json.loads(path.read_text())
        self.assertEqual(off.CONTRACT_SHA, off.digest(path)); self.assertFalse(new['collectProfiles'])
        self.assertEqual({'collectProfiles', 'profilingEvidence'}, set(new) - set(old))
        for key in set(old) - {'id', 'benchmarkScope'}:
            self.assertEqual(old[key], new[key], key)
        old_text = (PROJECT / 'app/src/debug/assets/tts-long/narration.txt').read_bytes()
        self.assertEqual(old_text, (path.parent / 'narration.txt').read_bytes())
        self.assertEqual(new['input']['sha256'], hashlib.sha256(old_text).hexdigest())
        self.assertTrue(new['profilingEvidence'].startswith('UNAVAILABLE_BY_DESIGN'))
        self.assertEqual('3f5e6840b91830528d542d5a01bddb7d0af454f00ddeb911e5a4db0ebae4c295', off.digest(PROJECT / 'tools/run_tts_long_gate.py'))
        self.assertEqual(off.PRIVACY_SOURCE_SHA, off.digest(PROJECT / 'tools/run_tts_only_gate.py'))

    def test_controller_matches_approved_logic_except_variant_pins_and_labels(self):
        class Normalize(ast.NodeTransformer):
            def visit_Constant(self, node):
                mapping = {off.CONTRACT_SHA: previous.CONTRACT_SHA,
                           'tts-long-profile-off': 'tts-long',
                           'app/src/debug/assets/tts-long-profile-off/contract.json': 'app/src/debug/assets/tts-long/contract.json'}
                if isinstance(node.value, str): node.value = mapping.get(node.value, node.value)
                return node
            def visit_Dict(self, node):
                pairs = [(k, v) for k, v in zip(node.keys, node.values)
                         if not isinstance(k, ast.Constant) or k.value not in ('collectProfiles', 'profileEvidence')]
                node.keys = [k for k, _ in pairs]; node.values = [v for _, v in pairs]
                return self.generic_visit(node)
        def normalized(path):
            tree = ast.parse(path.read_text()); tree.body.pop(0)  # module description only
            return ast.dump(Normalize().visit(tree), include_attributes=False)
        self.assertEqual(normalized(PROJECT / 'tools/run_tts_long_gate.py'), normalized(PROJECT / 'tools/run_tts_profile_off_gate.py'))

    def test_existing_hook_only_and_unavailable_counts_not_zero_measurements(self):
        service = (PROJECT / 'app/src/debug/java/dev/qoralo/podcast/wiring/TtsOnlyService.kt').read_text()
        native = (PROJECT / 'app/src/main/cpp/podcast_runtime.cpp').read_text()
        self.assertIn('if (contract.collectProfiles) RuntimeDiagnostics.enableTtsOnly(evidence)', service)
        self.assertIn('NativeStdioCapture(root).use', service)
        self.assertEqual(1, service.count('tts.load(')); self.assertEqual(1, service.count('tts.renderChapter('))
        self.assertIn('UNAVAILABLE_BY_DESIGN', service)
        self.assertIn('.put("observedPerComponentRuns", JSONObject.NULL)', service)
        self.assertIn('if (!profile.empty())', native)
        self.assertIn('options.EnableProfiling(profile.c_str());', native)
        self.assertIn('provider["profiling_level"] = "detailed";', native)
        self.assertLess(service.index('if (contract.collectProfiles)'), service.index('tts.load('))
        self.assertLess(service.index('tts.renderChapter('), service.index('optional("wav-metrics")'))

    def test_profile_off_plan_and_unapproved_execution_do_not_acquire_lock_or_use_device(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); apk = root / 'fake.apk'; apk.write_bytes(b'synthetic-plan-only')
            contract = json.loads((PROJECT / 'app/src/debug/assets/tts-long-profile-off/contract.json').read_text())
            item = {'path': str(apk), 'bytes': apk.stat().st_size, 'sha256': off.digest(apk)}
            candidate = root / 'candidate.json'
            candidate.write_text(json.dumps({'kind': 'tts-long-profile-off', 'sourceDirty': False, 'contractSha256': off.CONTRACT_SHA,
                                            'contract': contract, 'app': item, 'test': item, 'modelPack': {}}))
            argv = ['profile-off', '--candidate', str(candidate), '--output', str(root / 'out'), '--run-id', 'tts-long-profile-off-host']
            with patch.object(off, 'verify_local_pack'), patch.object(off, 'Device', side_effect=AssertionError('no ADB')), patch.object(off.fcntl, 'flock', side_effect=AssertionError('no lock')):
                with patch.object(sys, 'argv', argv): off.main()
                with patch.object(sys, 'argv', argv + ['--execute']), patch.dict('os.environ', {}, clear=True):
                    with self.assertRaises(SystemExit): off.main()
            self.assertFalse((root / 'out').exists())


if __name__ == '__main__':
    unittest.main()

import hashlib
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / 'podcast-app'
BASE = 'cc7e772ca825f6f5e939071b4737ba8a7976504a'


def frozen(path):
    return subprocess.check_output(['git', 'show', BASE + ':podcast-app/' + path], cwd=ROOT).decode()


class NormalIntegrationScopeTests(unittest.TestCase):
    def test_normal_source_pin_uses_existing_distinct_data_namespace(self):
        props = dict(line.split('=', 1) for line in (PROJECT / 'config/normal-supertonic-pack.properties').read_text().splitlines()
                     if line and not line.startswith('#'))
        self.assertEqual({'supertonic.pack.id': 'supertonic-3-t2048-l2048-parity',
                          'supertonic.manifest.sha256': '116fda95a907f6dc35bfe7c2144fe2818ed438cc109c1faa3f95cafc2fc84066'}, props)
        gradle = (PROJECT / 'app/build.gradle.kts').read_text()
        self.assertIn('config/normal-supertonic-pack.properties', gradle)
        self.assertIn('"SUPERTONIC_PACK_ID", "\\"$supertonicPackId\\""', gradle)
        self.assertIn('"SUPERTONIC_MANIFEST_SHA256", "\\"$supertonicManifest\\""', gradle)
        ui = (PROJECT / 'app/src/main/java/dev/vibevoice/podcast/ui/PodcastApp.kt').read_text()
        self.assertIn('modelPackRoot(BuildConfig.SUPERTONIC_PACK_ID)', ui)
        self.assertIn('Supertonic 3 · experimental', ui)
        self.assertIn('speech coverage unverified', ui)

    def test_coordinator_changes_only_model_directory_and_id_selection(self):
        path = 'app/src/main/java/dev/vibevoice/podcast/generation/GenerationCoordinator.kt'
        expected = frozen(path).replace('Triple("supertonic-3", "supertonic-3", BuildConfig.SUPERTONIC_MANIFEST_SHA256)',
                                        'Triple(BuildConfig.SUPERTONIC_PACK_ID, BuildConfig.SUPERTONIC_PACK_ID, BuildConfig.SUPERTONIC_MANIFEST_SHA256)')
        self.assertEqual(expected, (PROJECT / path).read_text())

    def test_only_two_prompt_strings_change_no_limits_parser_sampler_or_global_minimum(self):
        path = 'app/src/main/java/dev/vibevoice/podcast/runtime/NativeEngines.kt'
        expected = frozen(path).replace(
            'Design a coherent spoken podcast outline from the supplied notes and instructions. Return only JSON:',
            'Design a coherent spoken podcast outline from the supplied notes and instructions. Follow the requested chapter count and IDs. Each brief is a short content plan, not a miniature transcript. Return only JSON:').replace(
            'Write the requested complete spoken podcast chapter in one response. Use the outline, notes, and instructions; do not emit stage directions or analysis. Return only JSON:',
            'Write the requested complete spoken podcast chapter in one response. Develop the outline brief into a full source-grounded narration with an opening, explanation and closing; do not merely repeat or summarize the brief. Follow the instructions, including any requested spoken-word length. Do not emit stage directions or analysis. Return only JSON:')
        self.assertEqual(expected, (PROJECT / path).read_text())

    def test_native_and_legacy_runtime_pack_authorities_stay_unchanged(self):
        for path in ['app/src/main/cpp/podcast_runtime.cpp', 'config/trusted-local-runtime.json', 'tools/prepare_local_runtime.py']:
            self.assertEqual(frozen(path), (PROJECT / path).read_text(), path)
        self.assertEqual('a3de4cd62a83275977036516ff1e0c04a3beda454794e7c331aed7b936ad8b35',
                         hashlib.sha256((PROJECT / 'app/src/main/cpp/podcast_runtime.cpp').read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()

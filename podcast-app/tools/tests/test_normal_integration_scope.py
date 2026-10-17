import hashlib
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / 'podcast-app'
BASE = 'cc7e772ca825f6f5e939071b4737ba8a7976504a'


def frozen(path):
    # Historical commits predate the package rename; keep their original tree paths.
    historical = path.replace('java/dev/qoralo/podcast/', 'java/dev/vibevoice/podcast/')
    return subprocess.check_output(['git', 'show', BASE + ':podcast-app/' + historical], cwd=ROOT).decode()


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
        ui = (PROJECT / 'app/src/main/java/dev/qoralo/podcast/ui/PodcastApp.kt').read_text()
        self.assertIn('modelPackRoot(BuildConfig.SUPERTONIC_PACK_ID)', ui)
        self.assertIn('Supertonic 3 · experimental', ui)
        self.assertIn('speech coverage unverified', ui)

    def test_coordinator_changes_only_model_directory_and_id_selection(self):
        path = 'app/src/main/java/dev/qoralo/podcast/generation/GenerationCoordinator.kt'
        expected = frozen(path).replace('Triple("supertonic-3", "supertonic-3", BuildConfig.SUPERTONIC_MANIFEST_SHA256)',
                                        'Triple(BuildConfig.SUPERTONIC_PACK_ID, BuildConfig.SUPERTONIC_PACK_ID, BuildConfig.SUPERTONIC_MANIFEST_SHA256)')
        self.assertEqual(expected, (PROJECT / path).read_text())

    def test_target_prompt_binding_only_no_limits_parser_sampler_or_global_minimum(self):
        path = 'app/src/main/java/dev/qoralo/podcast/runtime/NativeEngines.kt'
        historical = path.replace('java/dev/qoralo/podcast/', 'java/dev/vibevoice/podcast/')
        expected = subprocess.check_output(['git','show','7980d11:podcast-app/'+historical],cwd=ROOT).decode()
        expected = expected.replace('.put("requestedChapterId", chapter.id)',
            '.put("requestedChapterId", chapter.id)\n            .put("requestedChapter", JSONObject().put("id", chapter.id).put("title", chapter.title).put("brief", chapter.brief))')
        expected = expected.replace('generate("chapter", serialized)', 'generate("chapter", serialized, singleChapterInstruction(chapter))')
        expected = expected.replace('generate(mode: String, request: String): String', 'generate(mode: String, request: String, specificInstruction: String? = null): String')
        expected = expected.replace('        RuntimeDiagnostics.beforeRequest(mode, request, systemInstruction(mode), maxOutput)',
            '        val instruction = specificInstruction ?: systemInstruction(mode)\n        RuntimeDiagnostics.beforeRequest(mode, request, instruction, maxOutput)')
        expected = expected.replace('Contents.of(systemInstruction(mode))', 'Contents.of(instruction)')
        expected = re.sub(r'^        "chapter" -> .*$', '        "chapter" -> error("A chapter request requires its concrete single-chapter instruction")', expected, flags=re.MULTILINE)
        expected = re.sub(r'^        "edit" -> .*$', '        "edit" -> SCRIPT_EDIT_INSTRUCTION', expected, flags=re.MULTILINE)
        self.assertEqual(expected, (PROJECT / path).read_text())

    def test_native_and_legacy_runtime_pack_authorities_stay_unchanged(self):
        for path in ['app/src/main/cpp/podcast_runtime.cpp', 'config/trusted-local-runtime.json', 'tools/prepare_local_runtime.py']:
            self.assertEqual(frozen(path), (PROJECT / path).read_text(), path)
        self.assertEqual('a3de4cd62a83275977036516ff1e0c04a3beda454794e7c331aed7b936ad8b35',
                         hashlib.sha256((PROJECT / 'app/src/main/cpp/podcast_runtime.cpp').read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()

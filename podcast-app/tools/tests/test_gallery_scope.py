from pathlib import Path
import unittest
import xml.etree.ElementTree as E

PROJECT = Path(__file__).resolve().parents[2]
ANDROID = '{http://schemas.android.com/apk/res/android}'


class GalleryScopeTests(unittest.TestCase):
    def test_gallery_is_nonexported_and_in_nonproduction_process(self):
        root = E.parse(PROJECT / 'app/src/debug/AndroidManifest.xml').getroot()
        gallery = next(x for x in root.find('application').findall('activity') if x.get(ANDROID + 'name') == '.gallery.SyntheticGalleryActivity')
        self.assertEqual('false', gallery.get(ANDROID + 'exported'))
        self.assertEqual(':ui_gallery', gallery.get(ANDROID + 'process'))
        main = (PROJECT / 'app/src/main/AndroidManifest.xml').read_text()
        self.assertNotIn('SyntheticGalleryActivity', main)
        application = (PROJECT / 'app/src/main/java/dev/vibevoice/podcast/PodcastApplication.kt').read_text()
        guarded = application.split('if (getProcessName() == packageName) {', 1)[1].split('}', 1)[0]
        self.assertIn('GenerationWatchdog', guarded)
        self.assertIn('QueuedCommandDispatcher', guarded)

    def test_gallery_has_only_fixture_state_no_repository_or_model_invocations(self):
        source = (PROJECT / 'app/src/debug/java/dev/vibevoice/podcast/gallery/SyntheticGalleryActivity.kt').read_text()
        for token in ['PodcastRepository', 'GenerationService', 'GemmaLiteRtGpuEngine', 'SupertonicQnnHtpEngine', 'queueScriptGeneration', 'lockAndQueueAudio']:
            self.assertNotIn(token, source)
        self.assertIn('synthetic-ui-gallery-30s.wav', source)
        self.assertIn('SourcesScreen', source)
        self.assertIn('ReviewScreen', source)
        self.assertIn('PlayerScreen', source)

    def test_capture_is_emulator_guarded_and_uses_actual_accessibility_tree(self):
        source = (PROJECT / 'app/src/androidTest/java/dev/vibevoice/podcast/gallery/SyntheticGalleryCaptureTest.kt').read_text()
        self.assertIn('Build.HARDWARE in setOf("ranchu", "goldfish")', source)
        self.assertIn('uiAutomation.rootInActiveWindow', source)
        self.assertIn('uiAutomation.takeScreenshot()', source)
        self.assertNotIn('useUnmergedTree', source)


if __name__ == '__main__':
    unittest.main()

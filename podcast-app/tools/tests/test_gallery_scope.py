from pathlib import Path
import unittest
import xml.etree.ElementTree as E

PROJECT = Path(__file__).resolve().parents[2]
ANDROID = '{http://schemas.android.com/apk/res/android}'


def main_process_block(application):
    """Read this guard's balanced block, including its nested deletion-reaper loop."""
    marker = 'if (getProcessName() == packageName) {'
    start = application.index(marker) + len(marker)
    depth = 1
    for end in range(start, len(application)):
        depth += (application[end] == '{') - (application[end] == '}')
        if depth == 0:
            return application[start:end]
    raise ValueError('Unclosed main-process guard')


class GalleryScopeTests(unittest.TestCase):
    def test_process_guard_parser_handles_nested_blocks_without_accepting_outside_startup(self):
        source = 'if (getProcessName() == packageName) { launch { while (active) { reap() } }; GenerationWatchdog() } QueuedCommandDispatcher()'
        guarded = main_process_block(source)
        self.assertIn('GenerationWatchdog', guarded)
        self.assertNotIn('QueuedCommandDispatcher', guarded)
        with self.assertRaises(ValueError):
            main_process_block('if (getProcessName() == packageName) { launch { reap() }')

    def test_gallery_is_nonexported_and_in_nonproduction_process(self):
        root = E.parse(PROJECT / 'app/src/debug/AndroidManifest.xml').getroot()
        gallery = next(x for x in root.find('application').findall('activity') if x.get(ANDROID + 'name') == '.gallery.SyntheticGalleryActivity')
        self.assertEqual('false', gallery.get(ANDROID + 'exported'))
        self.assertEqual(':ui_gallery', gallery.get(ANDROID + 'process'))
        self.assertEqual('${applicationId}.ui_gallery', gallery.get(ANDROID + 'taskAffinity'))
        self.assertEqual('true', gallery.get(ANDROID + 'excludeFromRecents'))
        main = (PROJECT / 'app/src/main/AndroidManifest.xml').read_text()
        self.assertNotIn('SyntheticGalleryActivity', main)
        application = (PROJECT / 'app/src/main/java/dev/qoralo/podcast/PodcastApplication.kt').read_text()
        guarded = main_process_block(application)
        self.assertIn('GenerationWatchdog', guarded)
        self.assertIn('QueuedCommandDispatcher', guarded)

    def test_gallery_has_only_fixture_state_no_repository_or_model_invocations(self):
        source = (PROJECT / 'app/src/debug/java/dev/qoralo/podcast/gallery/SyntheticGalleryActivity.kt').read_text()
        for token in ['PodcastRepository', 'GenerationService', 'GemmaLiteRtGpuEngine', 'SupertonicQnnHtpEngine', 'queueScriptGeneration', 'lockAndQueueAudio']:
            self.assertNotIn(token, source)
        self.assertIn('synthetic-ui-gallery-30s.wav', source)
        self.assertIn('SourcesScreen', source)
        self.assertIn('ReviewScreen', source)
        self.assertIn('PlayerScreen', source)
        self.assertIn('view.createAccessibilityNodeInfo()', source)
        self.assertIn('node?.windowId', source)
        self.assertNotIn('params.title =', source)

    def test_capture_is_emulator_guarded_and_uses_actual_accessibility_tree(self):
        source = (PROJECT / 'app/src/androidTest/java/dev/qoralo/podcast/gallery/SyntheticGalleryCaptureTest.kt').read_text()
        self.assertIn('Build.HARDWARE in setOf("ranchu", "goldfish")', source)
        self.assertIn('automation.windows', source)
        self.assertIn('FLAG_RETRIEVE_INTERACTIVE_WINDOWS', source)
        self.assertIn('automation.takeScreenshot()', source)
        self.assertIn('GalleryCapturePolicy.retainEvidence', source)
        self.assertIn('windowObservations', source)
        self.assertIn('run-summary.json', source)
        self.assertIn('GalleryCapturePolicy.ownsWindow', source)
        self.assertIn('lastOwnershipSnapshot', source)
        self.assertIn('it.windowId == expected.id', source)
        self.assertIn('Intent.FLAG_ACTIVITY_CLEAR_TASK', source)
        self.assertIn('galleryInfo.taskAffinity ==', source)
        self.assertIn('automation.clearCache()', source)
        self.assertIn('GalleryFrameContent.problems', source)
        self.assertIn('frameContentVerified', source)
        self.assertIn('GalleryCapturePolicy.captureValidatedPair', source)
        self.assertIn('$frame-initial.png', source)
        self.assertIn('finalScreenshotSha256', source)
        self.assertIn('treeSha256', source)
        self.assertNotIn('useUnmergedTree', source)


if __name__ == '__main__':
    unittest.main()

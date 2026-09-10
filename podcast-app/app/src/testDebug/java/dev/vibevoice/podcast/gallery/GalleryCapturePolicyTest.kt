package dev.vibevoice.podcast.gallery

import org.junit.Assert.*
import org.junit.Test

class GalleryCapturePolicyTest {
    private val app = GalleryWindowObservation(7, true, false, galleryWindowTitle("ui-test-library"), "app", true, true,
        2, "[0,0][320,700]", true, true, true, true)
    private var clock = 0L
    private fun await(ime: Boolean = false, sample: () -> List<GalleryWindowObservation>) = GalleryCapturePolicy.awaitWindow(
        "app", "ui-test-library", ime, { clock }, { clock += it }, sample)

    @Test fun acknowledgementRejectsOldFrameRunAndWrongProcessOrOwnerTitle() {
        val good = GalleryAcknowledgement("library", "ui-test-library", "app:ui_gallery", 123, true, galleryWindowTitle("ui-test-library"))
        assertTrue(GalleryCapturePolicy.acknowledges("library", "ui-test-library", "app", good))
        for (bad in listOf(good.copy(frame = "instructions"), good.copy(token = "ui-old-library"), good.copy(process = "app"),
            good.copy(pid = 0), good.copy(synthetic = false), good.copy(windowTitle = "stale"))) {
            assertFalse(GalleryCapturePolicy.acknowledges("library", "ui-test-library", "app", bad))
        }
    }

    @Test fun missingRootsReachBoundedDeadlineRatherThanPassingFrameAcknowledgement() {
        val result = await { listOf(app.copy(rootAvailable = false)) }
        assertNull(result.selected); assertEquals(10_000L, clock); assertEquals(50, result.polls)
    }
    @Test fun foreignPackageStaleTokenInvisibleAndEmptyRootsAreRejected() {
        for (bad in listOf(app.copy(rootPackage = "keyboard"), app.copy(title = galleryWindowTitle("ui-old-library")),
            app.copy(rootHasContent = false), app.copy(rootVisible = false), app.copy(application = false))) {
            clock = 0
            assertNull(await { listOf(bad) }.selected)
        }
    }
    @Test fun delayedRootRequiresStableRepeatedIdentity() {
        val result = await { if (clock < 1400) emptyList() else listOf(app) }
        assertEquals(app, result.selected); assertEquals(1800L, clock)
    }
    @Test fun changingWindowRestartsStabilityWindow() {
        val result = await { listOf(if (clock < 200) app else app.copy(id = 8)) }
        assertEquals(8, result.selected!!.id); assertEquals(600L, clock)
    }
    @Test fun keyboardFocusAllowsVisibleMatchingAppRootWithoutPretendingAppIsFocused() {
        val unfocused = app.copy(active = false, focused = false)
        val keyboard = app.copy(id = 9, application = false, ime = true, title = "Keyboard", rootPackage = "keyboard", layer = 3)
        val result = await(ime = true) { listOf(unfocused, keyboard) }
        assertEquals(unfocused, result.selected); assertFalse(result.selected!!.focused)
    }
    @Test fun requestedImeWithoutKeyboardTimesOutEvenWithCorrectRoot() {
        assertNull(await(ime = true) { listOf(app) }.selected)
        assertEquals(10_000L, clock)
    }
    @Test fun missingTreeRetainsScreenshotAndBothMetadataWrites() {
        val calls = mutableListOf<String>()
        val result = GalleryCapturePolicy.retainEvidence(false, screenshot = { calls += "png" }, tree = { error("must not run") },
            metadata = { calls += "metadata" })
        assertEquals(listOf("metadata", "png", "metadata"), calls)
        assertTrue(result.single().contains("unavailable"))
    }
    @Test fun throwingTreeDoesNotEraseScreenshotOrTurnPartialCaptureIntoSuccess() {
        val calls = mutableListOf<String>()
        val result = GalleryCapturePolicy.retainEvidence(true, screenshot = { calls += "png" }, tree = { calls += "tree"; error("lost root") },
            metadata = { calls += "metadata:${it.size}" })
        assertEquals(listOf("metadata:0", "png", "tree", "metadata:1"), calls)
        assertTrue(result.single().contains("lost root"))
    }
    @Test fun screenshotFailureStillAttemptsTreeAndFinalMetadata() {
        var tree = false
        var retained = emptyList<String>()
        val result = GalleryCapturePolicy.retainEvidence(true, screenshot = { error("no bitmap") }, tree = { tree = true }, metadata = { retained = it })
        assertTrue(tree); assertEquals(result, retained); assertTrue(result.single().startsWith("screenshot:"))
    }
}

package dev.vibevoice.podcast.gallery

import org.junit.Assert.*
import org.junit.Test

class GalleryFrameContentTest {
    private fun values(vararg text: String, enabled: Boolean = true) = text.map { GallerySemanticValue(it, null, enabled) }

    @Test fun freshOwnedWindowCannotMakePreviousFrameSemanticsComplete() {
        val token = "ui-fresh-sources"
        val owner = GalleryAcknowledgement("sources", token, "app:ui_gallery", 123, true, setOf(99), 1000)
        assertTrue(GalleryCapturePolicy.ownsWindow("sources", token, "app", 123, owner, 99, 1200))
        // These are the six real wrong-frame relationships found in both polish-03 matrices.
        val stale = mapOf(
            "sources" to values("Your first episode", "Create an episode"),
            "sources-empty" to values("Your first episode", "Create an episode"),
            "review" to values("Initial instructions", "Create"),
            "script-loading" to values("Creating episode", "Creating What flooding remembers"),
            "failure" to values("Creating episode", "Creating What flooding remembers"),
            "player" to values("Creating episode", "Creating What flooding remembers"),
        )
        for ((frame, oldTree) in stale) assertTrue("Stale $frame tree must remain partial even with fresh owned IDs", GalleryFrameContent.problems(frame, oldTree).isNotEmpty())
    }

    @Test fun sourcePresenceIsCheckedThroughRealContinueEnabledState() {
        assertTrue(GalleryFrameContent.problems("sources", values("Add sources", "Continue")).isEmpty())
        assertTrue(GalleryFrameContent.problems("sources-empty", values("Add sources", "Continue", enabled = false)).isEmpty())
        assertTrue(GalleryFrameContent.problems("sources-empty", values("Add sources", "Continue")).isNotEmpty())
    }

    @Test fun normalAndFailedAgentFramesAreNotInterchangeable() {
        assertTrue(GalleryFrameContent.problems("agent", values("Edit the script", "Ask for a change…")).isEmpty())
        assertTrue(GalleryFrameContent.problems("agent-error", values("Edit the script", "Ask for a change…")).isNotEmpty())
        assertTrue(GalleryFrameContent.problems("agent", values("Edit the script", "Ask for a change…", "Change wasn’t applied")).isNotEmpty())
    }

    @Test fun matchingTextAndContentDescriptionsAllowCurrentFrame() {
        val player = listOf(GallerySemanticValue("Now playing", null, true), GallerySemanticValue(null, "Playback position", true))
        assertTrue(GalleryFrameContent.problems("player", player).isEmpty())
        assertTrue(GalleryFrameContent.problems("transcript", values("Frozen chapter transcript", "Close transcript")).isEmpty())
    }

    @Test fun ownedButPreviouslyUsedWindowIsNotAFreshFrameWindow() {
        var clock = 0L
        val app = GalleryWindowObservation(10, true, false, "VibeVoice", "app", true, true, 1, "[0,0][320,700]",
            true, true, true, true, "ui-new-frame", 10)
        val result = GalleryCapturePolicy.awaitWindow("app", "ui-new-frame", false, { clock }, { clock += it }, { listOf(app) }, previousWindowIds = setOf(10))
        assertNull(result.selected); assertEquals(10_000L, clock)
    }
}

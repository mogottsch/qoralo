package dev.qoralo.podcast.gallery

import org.junit.Assert.*
import org.junit.Test

class GalleryPairedCaptureTest {
    @Test fun subsetParserIsBoundedUniqueAndWhitelistOnly() {
        val allowed = listOf("library", "sources", "paste")
        assertEquals(allowed, GalleryCapturePolicy.selectFrames("all", allowed))
        assertEquals(listOf("library"), GalleryCapturePolicy.selectFrames("library", allowed))
        assertEquals(listOf("library", "sources"), GalleryCapturePolicy.selectFrames("library,sources", allowed))
        for (invalid in listOf("", "library,", ",sources", "library,library", "library,unknown", "all,library")) {
            assertThrows(IllegalArgumentException::class.java) { GalleryCapturePolicy.selectFrames(invalid, allowed) }
        }
        assertThrows(IllegalArgumentException::class.java) { GalleryCapturePolicy.selectFrames("all", (1..16).map { "frame-$it" }) }
    }

    @Test fun finalImageIsCapturedOnlyAfterContentMatchesAndOwnershipBracketsIt() {
        val calls = mutableListOf<String>()
        assertTrue(GalleryCapturePolicy.captureValidatedPair(true, { calls += it }, { calls += "final-image" }, { calls += "publish" }))
        assertEquals(listOf("before", "final-image", "after", "publish"), calls)
    }

    @Test fun wrongContentCannotPublishAnInitialImageAsAValidatedPair() {
        val calls = mutableListOf<String>()
        assertFalse(GalleryCapturePolicy.captureValidatedPair(false, { calls += it }, { calls += "image" }, { calls += "publish" }))
        assertTrue(calls.isEmpty())
    }

    @Test fun ownershipFailureAfterCandidateCapturePreventsPublicationButKeepsCandidate() {
        var candidateRetained = false
        var published = false
        assertThrows(IllegalStateException::class.java) {
            GalleryCapturePolicy.captureValidatedPair(true, { if (it == "after") error("Owner changed") },
                { candidateRetained = true }, { published = true })
        }
        assertTrue(candidateRetained); assertFalse(published)
    }
}

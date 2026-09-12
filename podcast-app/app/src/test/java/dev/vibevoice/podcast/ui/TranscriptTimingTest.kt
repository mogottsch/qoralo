package dev.vibevoice.podcast.ui

import dev.vibevoice.podcast.data.ChapterAudioEntity
import dev.vibevoice.podcast.data.ChapterEntity
import dev.vibevoice.podcast.runtime.*
import org.junit.Assert.*
import org.junit.Test
import java.io.File

class TranscriptTimingTest {
    private val binding = AudioAttemptBinding("episode", "job", "revision", "revision-hash", "pack-hash", ProviderTextFrontend.VERSION)
    private fun chapter(position: Int = 0, text: String = "First passage.\n\nSecond passage.") =
        ChapterEntity("row-$position", "revision", "chapter-$position", position, "Chapter $position", text, 60)
    private fun chunk(index: Int, chapter: Int, segment: Int, start: Long, speechFrames: Long, gap: Long = 0, sourceStart: Int = 0, sourceEnd: Int = 14) =
        AvailableAudioChunk(index, chapter, "chapter-$chapter", segment, File("synthetic-$index.wav"), "hash-$index", start, speechFrames + gap, gap,
            AudioPassageKind.PROVIDER_SEGMENT, sourceStart, sourceEnd)
    private val chunks = listOf(chunk(0, 0, 0, 0, 44_100), chunk(1, 0, 1, 44_100, 44_100, 13_230, 16, 31), chunk(2, 1, 0, 101_430, 44_100, 30_870))
    private fun timeline(state: AudioAvailabilityState = AudioAvailabilityState.GENERATING) = TranscriptTiming.progressive("episode",
        listOf(chapter(), chapter(1, "Third passage.")), AudioAvailability(binding, chunks, state))

    @Test fun measuredSegmentsAreEndExclusiveAndNeverHighlightInsertedGaps() {
        val t = timeline()
        assertEquals(0, t.activeIndex(0)); assertEquals(0, t.activeIndex(999))
        assertNull(t.activeIndex(1000)); assertNull(t.activeIndex(1299))
        assertEquals(1, t.activeIndex(1300)); assertEquals(1, t.activeIndex(2299))
        assertNull(t.activeIndex(2300)); assertNull(t.activeIndex(2999))
        assertEquals(2, t.activeIndex(3000)); assertNull(t.activeIndex(4000)); assertNull(t.activeIndex(-1))
    }
    @Test fun chapterBoundaryAndBackwardSeekUseAbsolutePositionWithoutSpeedScaling() {
        val t = timeline()
        assertEquals("chapter-1", t.passages[t.activeIndex(3200)!!].chapterId)
        // Position is already the media clock at any playback speed, never wall time.
        for (speed in listOf(1f, 1.25f, 1.5f, 2f)) {
            assertEquals("speed=$speed", 0, t.activeIndex(500)); assertEquals("speed=$speed", 1, t.activeIndex(1500))
        }
    }
    @Test fun partialGenerationKeepsFutureTextButDoesNotInventTiming() {
        val t = TranscriptTiming.progressive("episode", listOf(chapter(), chapter(1, "Third passage.")), AudioAvailability(binding, chunks.take(1), AudioAvailabilityState.GENERATING))
        assertEquals(3, t.passages.size); assertEquals(TranscriptPrecision.SEGMENT, t.passages[0].precision)
        assertTrue(t.passages.drop(1).all { it.interval == null && it.precision == TranscriptPrecision.UNAVAILABLE })
        assertNull(t.activeIndex(1000)); assertNull(t.activeIndex(3000))
        assertEquals("Second passage.", t.passages[1].text)
    }
    @Test fun staleForeignAttemptAndUnknownFrontendNeverBorrowSegmentTiming() {
        assertTrue(timeline(AudioAvailabilityState.STALE).passages.all { it.interval == null })
        for (b in listOf(binding.copy(episodeId = "other"), binding.copy(frontendVersion = null))) {
            assertTrue(TranscriptTiming.progressive("episode", listOf(chapter()), AudioAvailability(b, chunks, AudioAvailabilityState.GENERATING)).passages.all { it.interval == null })
        }
        assertTrue(TranscriptTiming.progressive("episode", listOf(chapter().copy(revisionId = "other")), AudioAvailability(binding, chunks, AudioAvailabilityState.GENERATING)).passages.isEmpty())
        assertTrue(TranscriptTiming.progressive("episode", listOf(chapter().copy(stableChapterId = "other")), AudioAvailability(binding, chunks, AudioAvailabilityState.GENERATING)).passages.all { it.interval == null })
    }
    @Test fun stoppedGenerationStillHasTruthfulPartialSegmentTiming() {
        assertEquals(1, timeline(AudioAvailabilityState.FAILED).activeIndex(1500)); assertEquals(1, timeline(AudioAvailabilityState.COMPLETE).activeIndex(1500))
    }
    @Test fun completeChapterRecoveryIsNeverMisidentifiedAsTheFirstProviderSegment() {
        val full = chunks[0].copy(passageKind = AudioPassageKind.COMPLETE_CHAPTER, sourceStartUtf16 = null, sourceEndUtf16 = null)
        val t = TranscriptTiming.progressive("episode", listOf(chapter()), AudioAvailability(binding, listOf(full), AudioAvailabilityState.COMPLETE))
        assertEquals(chapter().text, t.passages.single().text); assertEquals(TranscriptPrecision.CHAPTER, t.passages.single().precision)
    }
    @Test fun malformedOrOverlappingSpansFailClosedWithoutSubstringCrashes() {
        for (bad in listOf(chunks[0].copy(sourceStartUtf16 = -1), chunks[0].copy(sourceEndUtf16 = 999), chunks[0].copy(sourceEndUtf16 = 0))) {
            assertTrue(TranscriptTiming.progressive("episode", listOf(chapter()), AudioAvailability(binding, listOf(bad), AudioAvailabilityState.COMPLETE)).passages.all { it.interval == null })
        }
        val overlap = listOf(chunks[0], chunks[1].copy(sourceStartUtf16 = 3))
        assertTrue(TranscriptTiming.progressive("episode", listOf(chapter()), AudioAvailability(binding, overlap, AudioAvailabilityState.COMPLETE)).passages.all { it.interval == null })
    }
    @Test fun chapterFallbackHasNoSentenceOrWordInterpolationAndRejectsOtherEpisode() {
        val audio = ChapterAudioEntity("a", "episode", "revision", "chapter-0", 0, "a.wav", "hash", 88_244, 44_100, 1, 44_100, 30_870, 74_970)
        val t = TranscriptTiming.chapters("episode", "revision", listOf(chapter()), listOf(audio))
        assertEquals(1, t.passages.size); assertEquals(chapter().text, t.passages.single().text)
        assertEquals(TranscriptPrecision.CHAPTER, t.passages.single().precision)
        assertNull(t.activeIndex(699)); assertEquals(0, t.activeIndex(700)); assertNull(t.activeIndex(1700))
        assertNull(TranscriptTiming.chapters("other", "revision", listOf(chapter()), listOf(audio)).activeIndex(1000))
    }
    @Test fun verifiedFinalProviderPassagesUseReceiptSpansAndKeepGapsUntimed() {
        val audio = ChapterAudioEntity("a", "episode", "revision", "chapter-0", 0, "a.wav", "hash", 202_904, 44_100, 1, 101_430, 0, 101_430)
        val verified = listOf(dev.vibevoice.podcast.runtime.TranscriptPassage("chapter-0", 0, 0, 0, 14, 0, 44_100),
            dev.vibevoice.podcast.runtime.TranscriptPassage("chapter-0", 0, 1, 16, 31, 57_330, 101_430))
        val t = TranscriptTiming.finalAudio("episode", "revision", listOf(chapter()), listOf(audio), verified)
        assertEquals(listOf("First passage.", "Second passage."), t.passages.map { it.text })
        assertEquals(0, t.activeIndex(999)); assertNull(t.activeIndex(1000)); assertNull(t.activeIndex(1299))
        assertEquals(1, t.activeIndex(1300)); assertNull(t.activeIndex(2300))
        val coarse = TranscriptTiming.finalAudio("episode", "revision", listOf(chapter()), listOf(audio), verified.map { it.copy(chapterId = "other") })
        assertEquals(TranscriptPrecision.CHAPTER, coarse.passages.single().precision)
        val outOfBounds = TranscriptTiming.finalAudio("episode", "revision", listOf(chapter()), listOf(audio), verified.map { it.copy(endFrame = 999_999) })
        assertEquals(TranscriptPrecision.CHAPTER, outOfBounds.passages.single().precision)
    }
    @Test fun fractionalFinalFrameDoesNotLightUpWhileWaitingAtAvailableEnd() {
        val t = TranscriptTiming.progressive("episode", listOf(chapter()), AudioAvailability(binding, listOf(chunks[0].copy(frameCount = 44_110)), AudioAvailabilityState.GENERATING))
        assertEquals(0, t.activeIndex(999)); assertNull(t.activeIndex(1000))
    }
    @Test fun manualScrollStaysInControlAcrossNewChunksChaptersSeeksAndGapsUntilExplicitResume() {
        val manual = TranscriptFollowPolicy().manualScroll()
        assertNull(manual.target(0)); assertNull(manual.target(2)); assertNull(manual.target(null))
        assertEquals(2, manual.resume().target(2)); assertNull(manual.resume().target(null))
    }
}

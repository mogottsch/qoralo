package dev.qoralo.podcast.ui

import dev.qoralo.podcast.data.ChapterAudioEntity
import dev.qoralo.podcast.data.ChapterEntity
import dev.qoralo.podcast.runtime.AudioAvailability
import dev.qoralo.podcast.runtime.AudioAvailabilityState
import dev.qoralo.podcast.runtime.AudioPassageKind
import dev.qoralo.podcast.runtime.ProviderTextFrontend

/** Measured audio interval; end-exclusive. Never estimated word alignment. */
data class TranscriptInterval(val startFrame: Long, val endFrame: Long, val sampleRateHz: Int) {
    init { require(startFrame >= 0 && endFrame > startFrame && sampleRateHz > 0) }
    fun contains(positionMs: Long): Boolean = positionMs >= 0 &&
        positionMs.toDouble() * sampleRateHz >= startFrame.toDouble() * 1000 &&
        positionMs.toDouble() * sampleRateHz < endFrame.toDouble() * 1000
}

enum class TranscriptPrecision { SEGMENT, CHAPTER, UNAVAILABLE }
data class TranscriptPassage(
    val key: String,
    val chapterId: String,
    val chapterPosition: Int,
    val chapterTitle: String,
    val text: String,
    val interval: TranscriptInterval?,
    val precision: TranscriptPrecision,
)

data class TranscriptTimeline(val passages: List<TranscriptPassage>, val availableEndMs: Long? = null) {
    fun activeIndex(positionMs: Long): Int? {
        // An exhausted progressive playlist has no current speech, even when ms rounding
        // places its endpoint just inside the final PCM frame.
        if (availableEndMs != null && positionMs >= availableEndMs) return null
        return passages.indexOfFirst { it.interval?.contains(positionMs) == true }.takeIf { it >= 0 }
    }
}

object TranscriptTiming {
    private fun row(chapter: ChapterEntity, start: Int, end: Int, interval: TranscriptInterval?, precision: TranscriptPrecision) =
        TranscriptPassage("${chapter.rowId}:$start", chapter.stableChapterId, chapter.position, chapter.title,
            chapter.text.substring(start, end).trim(), interval, precision)

    /** The reader/producer, not UI heuristics, authenticates both source spans and PCM boundaries. */
    fun progressive(episodeId: String, chapters: List<ChapterEntity>, audio: AudioAvailability): TranscriptTimeline {
        val bound = chapters.filter { it.revisionId == audio.binding.revisionId }.sortedBy { it.position }
        val trusted = audio.binding.episodeId == episodeId && audio.state != AudioAvailabilityState.STALE
        val rows = bound.flatMap { chapter ->
            val chunks = if (trusted) audio.chunks.filter { it.chapterId == chapter.stableChapterId && it.chapterPosition == chapter.position } else emptyList()
            val complete = chunks.singleOrNull { it.passageKind == AudioPassageKind.COMPLETE_CHAPTER }
            if (complete != null && complete.endFrame > complete.speechStartFrame) {
                listOf(row(chapter, 0, chapter.text.length, TranscriptInterval(complete.speechStartFrame, complete.endFrame, 44_100), TranscriptPrecision.CHAPTER))
            } else if (audio.binding.frontendVersion == ProviderTextFrontend.VERSION) {
                // Source grouping is known before audio exists. Keep every planned text row
                // stable; arriving audio may add timing, never replace a reader's text/key.
                val planned = ProviderTextFrontend.segmentSpans(chapter.text)
                val ordered = chunks.sortedBy { it.segmentIndex }
                val valid = ordered.withIndex().all { (index, chunk) ->
                    val span = planned.getOrNull(index)
                    chunk.passageKind == AudioPassageKind.PROVIDER_SEGMENT && chunk.segmentIndex == index && span != null &&
                        chunk.sourceStartUtf16 == span.startUtf16 && chunk.sourceEndUtf16 == span.endUtf16 &&
                        chunk.speechStartFrame >= 0 && chunk.endFrame > chunk.speechStartFrame &&
                        (index == 0 || chunk.speechStartFrame >= ordered[index - 1].endFrame)
                }
                planned.mapIndexed { index, span ->
                    val interval = if (valid) ordered.getOrNull(index)?.let { TranscriptInterval(it.speechStartFrame, it.endFrame, 44_100) } else null
                    row(chapter, span.startUtf16, span.endUtf16, interval,
                        if (interval != null) TranscriptPrecision.SEGMENT else TranscriptPrecision.UNAVAILABLE)
                }
            } else segmentedRows(chapter, emptyList())
        }
        return TranscriptTimeline(rows, audio.availableMs)
    }

    data class MeasuredSpan(val sourceStart: Int, val sourceEnd: Int, val interval: TranscriptInterval)

    /** Missing future text remains readable, untimed. Invalid/overlapping evidence fails closed. */
    fun segmentedRows(chapter: ChapterEntity, spans: List<MeasuredSpan>): List<TranscriptPassage> {
        var end = 0
        var frameEnd = 0L
        val valid = spans.all { span ->
            val ok = span.sourceStart >= end && span.sourceEnd > span.sourceStart && span.sourceEnd <= chapter.text.length &&
                span.interval.startFrame >= frameEnd
            end = span.sourceEnd; frameEnd = span.interval.endFrame; ok
        }
        if (!valid) return listOf(row(chapter, 0, chapter.text.length, null, TranscriptPrecision.UNAVAILABLE))
        val rows = mutableListOf<TranscriptPassage>()
        var cursor = 0
        spans.forEach { span ->
            if (chapter.text.substring(cursor, span.sourceStart).isNotBlank()) rows += row(chapter, cursor, span.sourceStart, null, TranscriptPrecision.UNAVAILABLE)
            rows += row(chapter, span.sourceStart, span.sourceEnd, span.interval, TranscriptPrecision.SEGMENT)
            cursor = span.sourceEnd
        }
        if (chapter.text.substring(cursor).isNotBlank()) rows += row(chapter, cursor, chapter.text.length, null, TranscriptPrecision.UNAVAILABLE)
        return rows
    }

    fun finalAudio(episodeId: String, revisionId: String?, chapters: List<ChapterEntity>, audio: List<ChapterAudioEntity>,
                   verified: List<dev.qoralo.podcast.runtime.TranscriptPassage>): TranscriptTimeline {
        val fallback = chapters(episodeId, revisionId, chapters, audio)
        if (verified.isEmpty()) return fallback
        val bound = chapters.filter { it.revisionId == revisionId }
        return TranscriptTimeline(fallback.passages.flatMap { coarse ->
            val chapter = bound.singleOrNull { it.stableChapterId == coarse.chapterId && it.position == coarse.chapterPosition }
            val passages = verified.filter { it.chapterId == coarse.chapterId && it.chapterPosition == coarse.chapterPosition }.sortedBy { it.segmentIndex }
            val interval = coarse.interval
            if (chapter == null || interval == null || interval.sampleRateHz != 44_100 || passages.isEmpty() ||
                passages.any { it.speechStartFrame < interval.startFrame || it.endFrame > interval.endFrame || it.endFrame <= it.speechStartFrame }) listOf(coarse)
            else segmentedRows(chapter, passages.map { MeasuredSpan(it.sourceStartUtf16, it.sourceEndUtf16, TranscriptInterval(it.speechStartFrame, it.endFrame, 44_100)) })
        })
    }

    /** Legacy masters only have measured chapter boundaries. Never subdivide by word count. */
    fun chapters(episodeId: String, revisionId: String?, chapters: List<ChapterEntity>, audio: List<ChapterAudioEntity>): TranscriptTimeline {
        return TranscriptTimeline(chapters.filter { it.revisionId == revisionId }.sortedBy { it.position }.map { chapter ->
            val clip = audio.singleOrNull { it.episodeId == episodeId && it.lockedRevisionId == revisionId && it.stableChapterId == chapter.stableChapterId && it.position == chapter.position }
            val interval = clip?.takeIf { it.startFrame >= 0 && it.endFrame > it.startFrame && it.sampleRateHz > 0 }
                ?.let { TranscriptInterval(it.startFrame, it.endFrame, it.sampleRateHz) }
            row(chapter, 0, chapter.text.length, interval, if (interval != null) TranscriptPrecision.CHAPTER else TranscriptPrecision.UNAVAILABLE)
        })
    }
}

/** Manual browsing stays in charge until explicit resume; chapter changes and seeks do not reset it. */
data class TranscriptFollowPolicy(val following: Boolean = true) {
    fun manualScroll() = copy(following = false)
    fun resume() = copy(following = true)
    fun target(activeIndex: Int?): Int? = activeIndex.takeIf { following }
}

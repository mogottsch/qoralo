package dev.vibevoice.podcast.ui

import dev.vibevoice.podcast.runtime.*
import org.junit.Assert.*
import org.junit.Test
import java.io.File

class ProgressivePlaybackPolicyTest {
    private fun chunk(i:Int,start:Long,frames:Long,chapter:Int=0,gap:Long=0)=AvailableAudioChunk(i,chapter,"c$chapter",i,File("$i.wav"),"hash$i",start,frames,gap)
    @Test fun underrunWaitsAtAbsoluteFrontierAndNewAudioDoesNotRestartAtZero() {
        val intent=ProgressivePlaybackIntent();intent.play();intent.ended(441000,AudioAvailabilityState.GENERATING)
        assertTrue(intent.isWaiting(AudioAvailabilityState.GENERATING));assertNull(intent.appended(441000))
        assertEquals(10000L,intent.appended(882000));assertTrue(intent.wantsPlayback);assertNull(intent.waitingAtFrame)
    }
    @Test fun explicitPauseSleepFocusAndNoisyRoutePreventLaterResume() {
        for(reason in PlaybackStopReason.values()) {
            val intent=ProgressivePlaybackIntent();intent.play();intent.ended(441000,AudioAvailabilityState.GENERATING)
            intent.stop(reason);assertFalse(intent.wantsPlayback);assertNull(intent.appended(882000));assertEquals(reason,intent.lastStopReason)
        }
    }
    @Test fun finalizationAndFailureNeverProduceASeekOrImplicitReplay() {
        val intent=ProgressivePlaybackIntent();intent.play();intent.ended(441000,AudioAvailabilityState.GENERATING)
        intent.finalized();assertNull(intent.appended(441000));assertFalse(intent.wantsPlayback)
        intent.play();intent.ended(441000,AudioAvailabilityState.FAILED);assertFalse(intent.wantsPlayback);assertNull(intent.waitingAtFrame)
    }
    @Test fun seeksOnlyMapToAvailableMediaAndChapterSkipNeedsPublishedTarget() {
        val first=chunk(0,0,441000)
        val timeline=ProgressiveTimeline(listOf(first))
        assertEquals(ProgressiveTimeline.Location(0,10000),timeline.location(99999))
        assertNull(timeline.adjacentChapter(100,1))
        val second=chunk(1,441000,441000+30870,1,30870)
        val grown=ProgressiveTimeline(listOf(first,second))
        assertEquals(ProgressiveTimeline.Location(1,0),grown.location(10000))
        assertEquals(10700L,grown.adjacentChapter(100,1))
        assertEquals(10000L,grown.absoluteMs(1,0));assertEquals(10700L,grown.absoluteMs(1,700))
    }
    @Test fun fractionalFrameDurationsDoNotAccumulatePerItemMillisecondRounding() {
        var start=0L;val chunks=(0 until 100).map { i ->chunk(i,start,3072).also { start+=3072 } }
        val timeline=ProgressiveTimeline(chunks)
        assertEquals(307200L*1000/44100,timeline.availableMs)
        for(i in chunks.indices) assertEquals(chunks[i].startFrame*1000/44100,timeline.absoluteMs(i,0))
    }
    @Test fun processRecreationDefaultsToPausedEvenWithPersistedPosition() {
        val restored=ProgressivePlaybackIntent();assertFalse(restored.wantsPlayback);assertNull(restored.appended(900000))
    }
}

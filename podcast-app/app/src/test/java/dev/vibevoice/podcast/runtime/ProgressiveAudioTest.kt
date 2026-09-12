package dev.vibevoice.podcast.runtime

import dev.vibevoice.podcast.data.ArtifactStore
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.io.RandomAccessFile

class ProgressiveAudioTest {
    @get:Rule val temp=TemporaryFolder()
    private fun artifacts()=ArtifactStore(temp.newFolder(),temp.newFolder())
    private fun binding(job:String="a".repeat(64))=AudioAttemptBinding("episode",job,"revision","revision-hash","pack-hash")
    private fun wave(name:String,frames:Int=44100):File=temp.newFile(name).also { f ->
        RandomAccessFile(f,"rw").use { out ->
            fun u16(v:Int){out.write(v and 255);out.write((v ushr 8) and 255)}
            fun u32(v:Int){u16(v and 65535);u16((v ushr 16) and 65535)}
            out.writeBytes("RIFF");u32(36+frames*2);out.writeBytes("WAVEfmt ");u32(16);u16(1);u16(1);u32(44100);u32(88200);u16(2);u16(16);out.writeBytes("data");u32(frames*2)
            repeat(frames){u16(1000+(it%13))}
        }
    }
    @Test fun delayedImmutableChunksExposeExactAvailableTimelineAndGaps() {
        val a=artifacts();val b=binding();val publisher=ProgressiveAudio.create(a,b);val reader=ProgressiveAudio.Reader(a,b)
        assertFalse(reader.read(AudioAvailabilityState.GENERATING).canListen)
        val first=wave("first.wav");val second=wave("second.wav");val third=wave("third.wav")
        publisher.append(0,"c1",0,first,WavInspector.inspectSupertonicOutput(first))
        assertEquals(1000L,reader.read(AudioAvailabilityState.GENERATING).availableMs)
        publisher.append(0,"c1",1,second,WavInspector.inspectSupertonicOutput(second))
        publisher.append(1,"c2",0,third,WavInspector.inspectSupertonicOutput(third))
        val live=reader.read(AudioAvailabilityState.GENERATING)
        assertEquals(listOf(0L,13230L,30870L),live.chunks.map { it.gapBeforeFrames })
        assertEquals(4000L,live.availableMs)
        val joined=live.chunks.flatMap { it.file.readBytes().drop(44) }.toByteArray()
        val expected=first.readBytes().drop(44).toByteArray()+ByteArray(13230*2)+second.readBytes().drop(44).toByteArray()+ByteArray(30870*2)+third.readBytes().drop(44).toByteArray()
        assertArrayEquals(expected,joined)
        publisher.finish(live.availableFrames,"master-hash")
        assertEquals(live.chunks,reader.read(AudioAvailabilityState.COMPLETE,"master-hash").chunks)
        assertEquals(AudioAvailabilityState.COMPLETE,reader.read(AudioAvailabilityState.COMPLETE,"master-hash").state)
    }
    @Test fun malformedGrowingSourceIsNeverPublished() {
        val a=artifacts();val b=binding();val publisher=ProgressiveAudio.create(a,b);val source=wave("growing.wav")
        val metadata=WavInspector.inspectSupertonicOutput(source);source.appendBytes(byteArrayOf(1,2))
        assertThrows(IllegalArgumentException::class.java){publisher.append(0,"c1",0,source,metadata)}
        assertFalse(ProgressiveAudio.Reader(a,b).read(AudioAvailabilityState.GENERATING).canListen)
    }
    @Test fun recreatedReaderKeepsPartialAvailabilityButNeverMixesAttempts() {
        val a=artifacts();val b=binding();val writer=ProgressiveAudio.create(a,b);val f=wave("part.wav")
        writer.append(0,"c1",0,f,WavInspector.inspectSupertonicOutput(f))
        val failed=ProgressiveAudio.Reader(a,b).read(AudioAvailabilityState.FAILED)
        assertTrue(failed.canListen);assertEquals(AudioAvailabilityState.FAILED,failed.state)
        assertFalse(ProgressiveAudio.Reader(a,binding("b".repeat(64))).read(AudioAvailabilityState.GENERATING).canListen)
        assertThrows(IllegalArgumentException::class.java){ProgressiveAudio.create(a,b)}
        StreamPlaybackStore.save(a,b,700,1.5f,true,123)
        val restored=StreamPlaybackStore.read(a,b)!!;assertEquals(700L,restored.positionMs);assertEquals(1.5f,restored.speed);assertTrue(restored.transcriptVisible)
        assertNull(StreamPlaybackStore.read(a,binding("b".repeat(64))))
    }
    @Test fun tamperedEntriesAndPrematureCompletionFailClosed() {
        val a=artifacts();val b=binding();val writer=ProgressiveAudio.create(a,b);val f=wave("part.wav")
        writer.append(0,"c1",0,f,WavInspector.inspectSupertonicOutput(f))
        val reader=ProgressiveAudio.Reader(a,b);assertTrue(reader.read(AudioAvailabilityState.GENERATING).canListen)
        assertEquals(AudioAvailabilityState.STALE,reader.read(AudioAvailabilityState.COMPLETE).state)
        File(ProgressiveAudio.root(a,b),"000000.json").appendText(" ")
        assertEquals(AudioAvailabilityState.STALE,reader.read(AudioAvailabilityState.GENERATING).state)
    }
}

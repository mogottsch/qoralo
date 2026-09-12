package dev.vibevoice.podcast.runtime

import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.io.RandomAccessFile

class ProviderWaveAssemblyTest {
    @get:Rule val temporary = TemporaryFolder()
    private fun wave(name: String, samples: Int, value: Int): File = temporary.newFile(name).also { file ->
        RandomAccessFile(file,"rw").use { out ->
            fun u16(v: Int) { out.write(v and 255);out.write((v ushr 8) and 255) }
            fun u32(v: Int) { u16(v and 65535);u16((v ushr 16) and 65535) }
            out.writeBytes("RIFF");u32(36+samples*2);out.writeBytes("WAVEfmt ");u32(16)
            u16(1);u16(1);u32(44100);u32(88200);u16(2);u16(16);out.writeBytes("data");u32(samples*2)
            repeat(samples) { u16(value) }
        }
    }
    @Test fun fullNativePayloadsAndOnlyBetweenSegmentGapsAreByteExact() {
        val a=wave("one.wav",3072,1200);val b=wave("two.wav",6144,-1500)
        val output=File(temporary.root,"chapter.wav")
        ProviderWaveAssembly.assemble(listOf(a to WavInspector.inspectSupertonicOutput(a),b to WavInspector.inspectSupertonicOutput(b)),output,13230)
        val expected=a.readBytes().drop(44).toByteArray()+ByteArray(13230*2)+b.readBytes().drop(44).toByteArray()
        assertArrayEquals(expected,output.readBytes().drop(44).toByteArray())
        assertEquals(3072L+6144+13230,WavInspector.inspectSupertonicOutput(output).frameCount)
    }
    @Test fun oneSegmentHasNoAddedGapAndChangedSourceIsRejected() {
        val a=wave("one.wav",3072,800);val metadata=WavInspector.inspectSupertonicOutput(a)
        val output=File(temporary.root,"one-chapter.wav")
        ProviderWaveAssembly.assemble(listOf(a to metadata),output,13230)
        assertArrayEquals(a.readBytes(),output.readBytes())
        RandomAccessFile(a,"rw").use { it.seek(50);it.write(3) }
        assertThrows(IllegalArgumentException::class.java) { ProviderWaveAssembly.assemble(listOf(a to metadata),File(temporary.root,"bad.wav"),13230) }
    }
}

package dev.moket.ttsbench;

import java.io.*;
import java.nio.*;
import java.nio.file.*;

public final class WavWriter {
    private WavWriter() {}
    /** Creates a new mono PCM16 WAV and refuses to overwrite evidence. Call only after timing. */
    public static void writeNew(File output, AudioData audio) throws IOException {
        Files.createDirectories(output.toPath().getParent());
        try(OutputStream raw=Files.newOutputStream(output.toPath(), StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
            BufferedOutputStream out=new BufferedOutputStream(raw)) {
            int dataBytes=Math.multiplyExact(audio.samples().length,2);
            ByteBuffer h=ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN);
            h.put("RIFF".getBytes(java.nio.charset.StandardCharsets.US_ASCII)).putInt(36+dataBytes).put("WAVEfmt ".getBytes(java.nio.charset.StandardCharsets.US_ASCII));
            h.putInt(16).putShort((short)1).putShort((short)1).putInt(audio.sampleRate()).putInt(audio.sampleRate()*2).putShort((short)2).putShort((short)16);
            h.put("data".getBytes(java.nio.charset.StandardCharsets.US_ASCII)).putInt(dataBytes); out.write(h.array());
            ByteBuffer b=ByteBuffer.allocate(8192).order(ByteOrder.LITTLE_ENDIAN);
            for(float sample:audio.samples()){float x=Math.max(-1,Math.min(1,sample)); b.putShort((short)Math.round(x*32767));if(b.remaining()<2){out.write(b.array(),0,b.position());b.clear();}}
            out.write(b.array(),0,b.position());
        }
    }
}

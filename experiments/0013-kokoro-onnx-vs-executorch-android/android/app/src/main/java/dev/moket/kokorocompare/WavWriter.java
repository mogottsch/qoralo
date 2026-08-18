package dev.moket.kokorocompare;

import java.io.*;
import java.nio.*;

final class WavWriter {
    private WavWriter() {}
    static void writePcm16Mono(File output, float[] samples, int sampleRate) throws Exception {
        output.getParentFile().mkdirs();
        int dataBytes=Math.multiplyExact(samples.length,2);
        try(DataOutputStream out=new DataOutputStream(new BufferedOutputStream(new FileOutputStream(output)))) {
            out.writeBytes("RIFF");writeLe32(out,36+dataBytes);out.writeBytes("WAVEfmt ");writeLe32(out,16);writeLe16(out,1);writeLe16(out,1);writeLe32(out,sampleRate);writeLe32(out,sampleRate*2);writeLe16(out,2);writeLe16(out,16);out.writeBytes("data");writeLe32(out,dataBytes);
            for(float sample:samples){int pcm=Math.round(sample*32767.0f);pcm=Math.max(-32768,Math.min(32767,pcm));writeLe16(out,pcm);}
        }
    }
    static void writeFloat32(File output,float[] samples)throws Exception{output.getParentFile().mkdirs();try(OutputStream out=new BufferedOutputStream(new FileOutputStream(output))){out.write(Hashing.littleEndianFloats(samples));}}
    private static void writeLe16(DataOutputStream out,int value)throws IOException{out.writeByte(value&255);out.writeByte((value>>>8)&255);}
    private static void writeLe32(DataOutputStream out,int value)throws IOException{out.writeByte(value&255);out.writeByte((value>>>8)&255);out.writeByte((value>>>16)&255);out.writeByte((value>>>24)&255);}
}

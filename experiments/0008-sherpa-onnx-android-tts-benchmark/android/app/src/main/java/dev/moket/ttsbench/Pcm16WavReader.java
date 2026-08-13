package dev.moket.ttsbench;

import java.io.*;
import java.nio.*;
import java.nio.file.Files;

/** Strict mono PCM16 decoder used only for Pocket reference audio. */
public final class Pcm16WavReader {
    private Pcm16WavReader() {}
    public static AudioData read(File file)throws IOException{
        byte[] b=Files.readAllBytes(file.toPath());if(b.length<44||!ascii(b,0,"RIFF")||!ascii(b,8,"WAVE"))throw new IOException("invalid reference WAV header");
        ByteBuffer in=ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN);int format=-1,channels=-1,rate=-1,bits=-1,dataAt=-1,dataSize=-1;
        for(int at=12;at+8<=b.length;){String id=new String(b,at,4,java.nio.charset.StandardCharsets.US_ASCII);long size=Integer.toUnsignedLong(in.getInt(at+4));long next=(long)at+8+size+(size&1);if(next>b.length)throw new IOException("truncated reference WAV chunk");
            if(id.equals("fmt ")){if(size<16)throw new IOException("short reference WAV fmt");format=Short.toUnsignedInt(in.getShort(at+8));channels=Short.toUnsignedInt(in.getShort(at+10));rate=in.getInt(at+12);bits=Short.toUnsignedInt(in.getShort(at+22));}
            else if(id.equals("data")){dataAt=at+8;dataSize=(int)size;break;}at=(int)next;}
        if(format!=1||channels!=1||bits!=16||rate<=0||dataAt<0||(dataSize&1)!=0)throw new IOException("reference WAV must be mono PCM16");
        float[] samples=new float[dataSize/2];for(int i=0;i<samples.length;i++)samples[i]=in.getShort(dataAt+i*2)/32768f;return new AudioData(samples,rate);
    }
    private static boolean ascii(byte[] b,int at,String expected){if(at+expected.length()>b.length)return false;for(int i=0;i<expected.length();i++)if(b[at+i]!=(byte)expected.charAt(i))return false;return true;}
}

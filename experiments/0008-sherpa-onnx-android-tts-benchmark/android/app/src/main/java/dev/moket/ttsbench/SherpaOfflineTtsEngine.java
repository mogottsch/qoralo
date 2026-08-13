package dev.moket.ttsbench;

import java.io.*;
import java.lang.reflect.*;
import java.util.*;

/**
 * Thin adapter for the pinned sherpa-onnx 1.13.5 AAR. The model descriptor points to a
 * verified filesystem configuration; no AssetManager is supplied. Reflection keeps pure
 * JVM domain tests independent of the 49 MB native AAR.
 */
public final class SherpaOfflineTtsEngine implements BenchmarkRunner.Engine {
    private final Object offlineTts; private final Method generate; private final int sid;
    private SherpaOfflineTtsEngine(Object tts,Method generate,int sid){this.offlineTts=tts;this.generate=generate;this.sid=sid;}
    public static BenchmarkRunner.Engine create(BenchmarkDescriptor d,Map<String,File> verified)throws Exception{
        if(!"cpu".equals(d.provider()))throw new IllegalArgumentException("only CPU is permitted");
        File config=verified.get(d.sherpaConfigPath());if(config==null)throw new IOException("sherpa config is not in verified inventory");
        // The pinned benchmark AAR exposes OfflineTts.createFromJson(String, String, int).
        Class<?> type=Class.forName("com.k2fsa.sherpa.onnx.OfflineTts");
        Method factory=type.getMethod("createFromJson",String.class,String.class,int.class);
        Object tts=factory.invoke(null,config.getAbsolutePath(),"cpu",d.numThreads());
        Method generate=type.getMethod("generate",String.class,int.class,Class.forName("com.k2fsa.sherpa.onnx.OfflineTtsCallback"));
        return new SherpaOfflineTtsEngine(tts,generate,d.speakerId());
    }
    @Override public AudioData synthesize(String text,BenchmarkRunner.AudioCallback sink)throws Exception{
        Class<?> cb=generate.getParameterTypes()[2];Object proxy=Proxy.newProxyInstance(cb.getClassLoader(),new Class<?>[]{cb},(p,m,args)->{if(args!=null&&args.length>0&&args[0] instanceof float[] samples)sink.onAudio(samples);return 1;});
        Object out=generate.invoke(offlineTts,text,sid,proxy);float[] samples=(float[])out.getClass().getMethod("getSamples").invoke(out);int rate=((Number)out.getClass().getMethod("getSampleRate").invoke(out)).intValue();return new AudioData(samples,rate);
    }
    @Override public void close()throws Exception{try{offlineTts.getClass().getMethod("release").invoke(offlineTts);}catch(NoSuchMethodException ignored){}}
}

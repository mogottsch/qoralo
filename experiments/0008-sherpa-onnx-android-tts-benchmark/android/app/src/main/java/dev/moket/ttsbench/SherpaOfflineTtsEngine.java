package dev.moket.ttsbench;

import java.io.*;
import java.lang.reflect.*;
import java.util.*;

/**
 * Reflection adapter for the pinned sherpa-onnx 1.13.5 Android API. Model and
 * frontend paths come exclusively from the hash-verified external inventory.
 * Reflection keeps JVM domain tests independent of the 49 MB native AAR.
 */
public final class SherpaOfflineTtsEngine implements BenchmarkRunner.Engine {
    private static final String PKG="com.k2fsa.sherpa.onnx.";
    private final Object offlineTts; private final Method generate; private final int sid;
    private final Object generationConfig;
    private SherpaOfflineTtsEngine(Object tts,Method generate,int sid,Object generationConfig){this.offlineTts=tts;this.generate=generate;this.sid=sid;this.generationConfig=generationConfig;}

    public static BenchmarkRunner.Engine create(BenchmarkDescriptor d,Map<String,File> verified)throws Exception{
        if(!"cpu".equals(d.provider()))throw new IllegalArgumentException("only CPU is permitted");
        File configFile=verified.get(d.sherpaConfigPath());if(configFile==null)throw new IOException("sherpa config is not in verified inventory");
        SherpaConfig spec=SherpaConfig.parse(configFile,verified);

        String modelName=switch(spec.modelType()){case "pocket"->"Pocket";case "kokoro"->"Kokoro";case "supertonic"->"Supertonic";default->throw new IOException("unsupported model type");};
        Class<?> leafType=Class.forName(PKG+"OfflineTts"+modelName+"ModelConfig");Object leaf=leafType.getConstructor().newInstance();
        for(var e:spec.modelValues().entrySet())invokeSetter(leaf,"set"+camel(e.getKey()),e.getValue());

        Class<?> modelType=Class.forName(PKG+"OfflineTtsModelConfig");Object model=modelType.getConstructor().newInstance();
        modelType.getMethod("set"+modelName,leafType).invoke(model,leaf);
        modelType.getMethod("setProvider",String.class).invoke(model,"cpu");
        modelType.getMethod("setNumThreads",int.class).invoke(model,d.numThreads());
        modelType.getMethod("setDebug",boolean.class).invoke(model,false);

        Class<?> configType=Class.forName(PKG+"OfflineTtsConfig");Object config=configType.getConstructor().newInstance();
        configType.getMethod("setModel",modelType).invoke(config,model);
        configType.getMethod("setRuleFsts",String.class).invoke(config,spec.ruleFsts());
        configType.getMethod("setRuleFars",String.class).invoke(config,spec.ruleFars());
        Class<?> ttsType=Class.forName(PKG+"OfflineTts");Class<?> assetsType=Class.forName("android.content.res.AssetManager");Object tts=ttsType.getConstructor(assetsType,configType).newInstance(null,config);
        Class<?> callbackType=Class.forName("kotlin.jvm.functions.Function1");

        Object generation=null;Method generate;
        if(spec.referenceAudio()!=null){AudioData reference=Pcm16WavReader.read(new File(spec.referenceAudio()));Class<?> generationType=Class.forName(PKG+"GenerationConfig");generation=generationType.getConstructor().newInstance();
            generationType.getMethod("setSid",int.class).invoke(generation,d.speakerId());generationType.getMethod("setReferenceAudio",float[].class).invoke(generation,(Object)reference.samples());generationType.getMethod("setReferenceSampleRate",int.class).invoke(generation,reference.sampleRate());generationType.getMethod("setNumSteps",int.class).invoke(generation,spec.numSteps());if(spec.referenceText()!=null)generationType.getMethod("setReferenceText",String.class).invoke(generation,spec.referenceText());
            generate=ttsType.getMethod("generateWithConfigAndCallback",String.class,generationType,callbackType);
        }else generate=ttsType.getMethod("generateWithCallback",String.class,int.class,float.class,callbackType);
        return new SherpaOfflineTtsEngine(tts,generate,d.speakerId(),generation);
    }
    @Override public AudioData synthesize(String text,BenchmarkRunner.AudioCallback sink)throws Exception{
        Class<?> callbackType=generate.getParameterTypes()[generate.getParameterCount()-1];Object callback=Proxy.newProxyInstance(callbackType.getClassLoader(),new Class<?>[]{callbackType},(p,m,args)->{if(args!=null&&args.length>0&&args[0] instanceof float[] samples)sink.onAudio(samples);return Integer.valueOf(1);});
        Object out=generationConfig==null?generate.invoke(offlineTts,text,sid,1.0f,callback):generate.invoke(offlineTts,text,generationConfig,callback);
        float[] samples=(float[])out.getClass().getMethod("getSamples").invoke(out);int rate=((Number)out.getClass().getMethod("getSampleRate").invoke(out)).intValue();return new AudioData(samples,rate);
    }
    @Override public void close()throws Exception{offlineTts.getClass().getMethod("release").invoke(offlineTts);}
    private static void invokeSetter(Object target,String name,String value)throws ReflectiveOperationException{target.getClass().getMethod(name,String.class).invoke(target,value);}
    private static String camel(String key){StringBuilder b=new StringBuilder();boolean upper=true;for(char c:key.toCharArray()){if(c=='_'){upper=true;continue;}b.append(upper?Character.toUpperCase(c):c);upper=false;}return b.toString();}
}

package dev.moket.ttsbench;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;

public final class BenchmarkRunner {
    public interface Clock { long nanoTime(); }
    public interface EngineFactory { Engine create(BenchmarkDescriptor descriptor,Map<String,File> verifiedFiles)throws Exception; }
    public interface Engine extends AutoCloseable { AudioData synthesize(String text,AudioCallback callback)throws Exception; default void close()throws Exception{} }
    public interface AudioCallback { void onAudio(float[] samples); }
    public interface MemoryReader { MemoryMetrics boundary(String phase,long peakPss,long peakRss)throws Exception; MemoryMetrics.Source samplerSource(); }
    private final Clock clock; private final EngineFactory engines; private final MemoryReader memory;
    public BenchmarkRunner(Clock clock,EngineFactory engines,MemoryReader memory){this.clock=clock;this.engines=engines;this.memory=memory;}

    public BenchmarkResult run(BenchmarkDescriptor d,Map<String,File> files,String transcriptText,File output,String campaignId){
        Objects.requireNonNull(transcriptText,"transcriptText");
        long load=0; MemoryMetrics loadMemory=null; List<BenchmarkResult.Run> runs=new ArrayList<>(); String stage="load";
        try {
            Engine engine;long loadPeakPss,loadPeakRss;
            try(MemoryMetrics.PhaseSampler sampler=new MemoryMetrics.PhaseSampler(memory.samplerSource(),10)){
                long a=clock.nanoTime();engine=engines.create(d,files);load=clock.nanoTime()-a;
                loadPeakPss=sampler.peakPss();loadPeakRss=sampler.peakRss();
            }
            try(engine){loadMemory=memory.boundary("load",loadPeakPss,loadPeakRss);int count=1+d.warmRuns();for(int i=0;i<count;i++){stage="synthesis_"+i;String state=i==0?"cold":"warm";AtomicLong callback=new AtomicLong(-1);AudioData audio;long elapsed;long pp,pr;
                    try(MemoryMetrics.PhaseSampler sampler=new MemoryMetrics.PhaseSampler(memory.samplerSource(),10)){
                        // The monotonic boundary contains only the sherpa synthesis call.
                        final long start=clock.nanoTime();
                        audio=engine.synthesize(transcriptText,chunk->{if(chunk!=null&&chunk.length>0)callback.compareAndSet(-1,clock.nanoTime()-start);});
                        elapsed=clock.nanoTime()-start;pp=sampler.peakPss();pr=sampler.peakRss();
                    }
                    // Capture the synthesis boundary before validation, evidence I/O, and hashing can affect memory.
                    MemoryMetrics mm=memory.boundary(state,pp,pr);
                    AudioValidation validation=AudioValidation.inspect(audio);if(!validation.valid())throw new InvalidAudioException(validation.reason());
                    String name=campaignId+"-"+state+"-"+i+".wav";File wav=new File(output,name);WavWriter.writeNew(wav,audio);String hash=SecureFiles.sha256(wav);
                    double duration=audio.durationSeconds();double rtf=(elapsed/1e9)/duration;
                    runs.add(new BenchmarkResult.Run(state,elapsed,callback.get(),callback.get()<0?"no_non_empty_callback_observed":null,audio.samples().length,audio.sampleRate(),duration,rtf,name,hash,validation,mm));}}
            List<Double> warm=new ArrayList<>();for(var r:runs)if(r.state().equals("warm")&&r.validation().valid())warm.add(r.rtf());Double med=warm.size()>=3?BenchmarkResult.median(warm):null;
            return new BenchmarkResult(load,loadMemory,List.copyOf(runs),med,null);
        } catch(OutOfMemoryError e){return new BenchmarkResult(load,loadMemory,List.copyOf(runs),null,new BenchmarkResult.Failure(stage,"oom",String.valueOf(e.getMessage()),e.getClass().getName()));}
        catch(Exception e){return new BenchmarkResult(load,loadMemory,List.copyOf(runs),null,new BenchmarkResult.Failure(stage,code(e),String.valueOf(e.getMessage()),e.getClass().getName()));}
    }
    public static void writeResultNew(File file,BenchmarkResult result)throws IOException{Files.createDirectories(file.toPath().getParent());Files.write(file.toPath(),result.toJson().getBytes(StandardCharsets.UTF_8),StandardOpenOption.CREATE_NEW);}
    private static String code(Exception e){if(e instanceof InvalidAudioException)return "invalid_audio";if(e instanceof FileAlreadyExistsException)return "evidence_collision";return "failure";}
    private static final class InvalidAudioException extends IOException{InvalidAudioException(String m){super(m);}}
}

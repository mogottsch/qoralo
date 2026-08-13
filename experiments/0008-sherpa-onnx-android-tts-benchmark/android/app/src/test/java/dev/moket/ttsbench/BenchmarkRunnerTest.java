package dev.moket.ttsbench;

import static org.junit.Assert.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.*;
import org.junit.rules.TemporaryFolder;

public class BenchmarkRunnerTest {
 @Rule public TemporaryFolder tmp=new TemporaryFolder();
 private BenchmarkDescriptor descriptor(){return new BenchmarkDescriptor("x","transcript.txt","a".repeat(64),"config.json",Map.of("config.json","b".repeat(64)),"cpu",1,3,0,"en");}
 private static BenchmarkRunner.MemoryReader memory(){return new BenchmarkRunner.MemoryReader(){public MemoryMetrics boundary(String p,long pp,long pr){return new MemoryMetrics(1,2,3,"cumulative_process_lifetime",p,pp,pr);}public MemoryMetrics.Source samplerSource(){return ()->new MemoryMetrics.Sample(4,5);}};}
 @Test public void coldWarmCallbackTimingAndIoAreOutsideSynthesisTimer()throws Exception{AtomicLong now=new AtomicLong();BenchmarkRunner.Clock clock=()->now.getAndAdd(10);BenchmarkRunner.EngineFactory ef=(d,f)->(text,cb)->{cb.onAudio(new float[0]);cb.onAudio(new float[]{.2f});return new AudioData(new float[]{-.2f,.2f},2);};File output=tmp.newFolder();BenchmarkResult r=new BenchmarkRunner(clock,ef,memory()).run(descriptor(),Map.of(),output,"campaign");assertNull(r.failure());assertEquals(4,r.runs().size());assertEquals("cold",r.runs().get(0).state());assertEquals(List.of("warm","warm","warm"),r.runs().subList(1,4).stream().map(BenchmarkResult.Run::state).toList());assertEquals(20,r.runs().get(0).synthesisNanos());assertEquals(10,r.runs().get(0).firstCallbackNanos());assertNull(r.runs().get(0).callbackUnavailableReason());assertNotNull(r.warmMedianRtf());for(var run:r.runs()){assertTrue(new File(output,run.wavPath()).exists());assertEquals(64,run.wavSha256().length());}}
 @Test public void missingCallbackIsUnavailableNotZero()throws Exception{AtomicLong n=new AtomicLong();BenchmarkResult r=new BenchmarkRunner(n::getAndIncrement,(d,f)->(t,cb)->new AudioData(new float[]{.1f},1),memory()).run(descriptor(),Map.of(),tmp.newFolder(),"no-callback");assertEquals(-1,r.runs().get(0).firstCallbackNanos());assertEquals("no_non_empty_callback_observed",r.runs().get(0).callbackUnavailableReason());}
 @Test public void invalidAudioAndEngineExceptionsBecomeStructuredFailures(){BenchmarkResult invalid=new BenchmarkRunner(System::nanoTime,(d,f)->(t,c)->new AudioData(new float[2],2),memory()).run(descriptor(),Map.of(),tmp.getRoot(),"bad");assertEquals("invalid_audio",invalid.failure().code());BenchmarkResult failed=new BenchmarkRunner(System::nanoTime,(d,f)->{throw new IOException("load broke");},memory()).run(descriptor(),Map.of(),tmp.getRoot(),"fail");assertEquals("load",failed.failure().stage());assertTrue(failed.toJson().contains("load broke"));}
 @Test public void resultFileIsWriteOnce()throws Exception{File f=new File(tmp.newFolder(),"r.json");BenchmarkResult r=new BenchmarkResult(1,List.of(),null,new BenchmarkResult.Failure("load","failure","x","IOException"));BenchmarkRunner.writeResultNew(f,r);assertThrows(IOException.class,()->BenchmarkRunner.writeResultNew(f,r));assertTrue(new String(java.nio.file.Files.readAllBytes(f.toPath()),java.nio.charset.StandardCharsets.UTF_8).contains("failure"));}
 @Test public void samplerCapturesPeaks()throws Exception{AtomicLong x=new AtomicLong();try(MemoryMetrics.PhaseSampler s=new MemoryMetrics.PhaseSampler(()->{long v=x.incrementAndGet();return new MemoryMetrics.Sample(v,v*2);},1)){Thread.sleep(20);assertTrue(s.peakPss()>0);assertTrue(s.peakRss()>=s.peakPss());}}
}

package dev.moket.ttsbench;

import static org.junit.Assert.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.*;
import org.junit.rules.TemporaryFolder;

public class CoreTest {
 @Rule public TemporaryFolder tmp=new TemporaryFolder();
 private static String hash(char c){return String.valueOf(c).repeat(64);}
 @Test public void descriptorParsesAndEnforcesCpuRunsAndHashes(){String j="{\"candidate\":\"kokoro\",\"transcript\":\"input.txt\",\"transcript_sha256\":\""+hash('a')+"\",\"sherpa_config_path\":\"model/config.json\",\"provider\":\"cpu\",\"num_threads\":1,\"warm_runs\":3,\"speaker_id\":3,\"language\":\"en\",\"files\":{\"input.txt\":\""+hash('b')+"\"}}";BenchmarkDescriptor d=BenchmarkDescriptor.parse(j);assertEquals(3,d.speakerId());assertEquals(3,d.warmRuns());assertThrows(IllegalArgumentException.class,()->new BenchmarkDescriptor("x","t",hash('a'),"c",Map.of("x",hash('b')),"qnn",1,3,0,"en"));assertThrows(IllegalArgumentException.class,()->new BenchmarkDescriptor("x","t",hash('a'),"c",Map.of("x",hash('b')),"cpu",1,2,0,"en"));}
 @Test public void secureFilesAcceptsPinnedRegularFileAndRejectsTraversalHashAndSymlink()throws Exception{File root=tmp.newFolder("external");File f=new File(root,"models/a");f.getParentFile().mkdirs();Files.write(f.toPath(),"ok".getBytes(java.nio.charset.StandardCharsets.UTF_8));String h=SecureFiles.sha256(f);assertEquals(f.getCanonicalFile(),SecureFiles.verify(root,Map.of("models/a",h)).get("models/a"));assertThrows(IOException.class,()->SecureFiles.verify(root,Map.of("../outside",h)));assertThrows(IOException.class,()->SecureFiles.verify(root,Map.of("models/a",hash('0'))));Path link=new File(root,"link").toPath();try{Files.createSymbolicLink(link,f.toPath());assertThrows(IOException.class,()->SecureFiles.verify(root,Map.of("link",h)));}catch(UnsupportedOperationException ignored){}}
 @Test public void audioDetectsSilenceClippingAndNonFinite(){assertEquals("silence",AudioValidation.inspect(new AudioData(new float[4],4)).reason());assertEquals("clipping",AudioValidation.inspect(new AudioData(new float[]{.2f,1f},2)).reason());assertEquals("non_finite_sample",AudioValidation.inspect(new AudioData(new float[]{.2f,Float.NaN},2)).reason());assertTrue(AudioValidation.inspect(new AudioData(new float[]{-.2f,.2f},2)).valid());}
 @Test public void wavIsNativePcmAndWriteOnce()throws Exception{File out=new File(tmp.newFolder(),"x.wav");WavWriter.writeNew(out,new AudioData(new float[]{-.5f,.5f},8000));byte[] b=Files.readAllBytes(out.toPath());assertEquals("RIFF",new String(b,0,4));assertEquals(48,b.length);assertEquals(8000,ByteBuffer.wrap(b,24,4).order(ByteOrder.LITTLE_ENDIAN).getInt());assertThrows(FileAlreadyExistsException.class,()->WavWriter.writeNew(out,new AudioData(new float[]{.2f},8000)));assertEquals(64,SecureFiles.sha256(out).length());}
 @Test public void medianHandlesOddAndEven(){assertEquals(2,BenchmarkResult.median(List.of(3d,1d,2d)),0);assertEquals(2.5,BenchmarkResult.median(List.of(4d,1d,3d,2d)),0);assertThrows(IllegalArgumentException.class,()->BenchmarkResult.median(List.of()));}
 @Test public void procMemoryLabelsAndParsesCumulativeHwm()throws Exception{MemoryMetrics m=MemoryMetrics.fromProc("VmRSS:\t12 kB\nVmHWM:\t20 kB\n",99,"warm",100,200);assertEquals(12288,m.rssBytes());assertEquals(20480,m.vmHwmBytes());assertEquals("cumulative_process_lifetime",m.vmHwmSemantics());assertEquals("warm",m.phase());assertThrows(IOException.class,()->MemoryMetrics.procKb("VmRSS: 1 kB","VmHWM"));}
}

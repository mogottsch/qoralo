package dev.moket.ttsbench;

import java.io.*;
import java.nio.file.*;
import java.util.*;

public record MemoryMetrics(long pssBytes, long rssBytes, long vmHwmBytes,
        String vmHwmSemantics, String phase, long sampledPeakPssBytes, long sampledPeakRssBytes) {
    public MemoryMetrics { if(!"cumulative_process_lifetime".equals(vmHwmSemantics))throw new IllegalArgumentException("VmHWM must be labeled cumulative"); }
    public static long procKb(String status,String key) throws IOException { for(String line:status.split("\\R")){String[] p=line.trim().split("\\s+");if(p.length>=2&&p[0].equals(key+":"))return Math.multiplyExact(Long.parseLong(p[1]),1024);}throw new IOException("missing "+key); }
    public static MemoryMetrics fromProc(String status,long pssBytes,String phase,long peakPss,long peakRss)throws IOException{return new MemoryMetrics(pssBytes,procKb(status,"VmRSS"),procKb(status,"VmHWM"),"cumulative_process_lifetime",phase,peakPss,peakRss);}
    public static String readProcStatus() throws IOException{return new String(Files.readAllBytes(Path.of("/proc/self/status")), java.nio.charset.StandardCharsets.UTF_8);}

    public interface Source { Sample sample() throws Exception; }
    public record Sample(long pssBytes,long rssBytes) {}
    public static final class PhaseSampler implements AutoCloseable {
        private final Source source; private final Thread worker; private volatile boolean running=true; private volatile long peakPss=-1,peakRss=-1;
        public PhaseSampler(Source source,long intervalMs){
            if(intervalMs<=0)throw new IllegalArgumentException("intervalMs");this.source=Objects.requireNonNull(source);sampleNow();
            worker=new Thread(()->{while(running){try{Thread.sleep(intervalMs);sampleNow();}catch(InterruptedException e){return;}}},"memory-sampler");worker.setDaemon(true);worker.start();
        }
        private void sampleNow(){try{Sample s=source.sample();if(s.pssBytes()>=0)peakPss=Math.max(peakPss,s.pssBytes());if(s.rssBytes()>=0)peakRss=Math.max(peakRss,s.rssBytes());}catch(Exception ignored){/* unavailable samples remain -1 rather than fabricated */}}
        public long peakPss(){return peakPss;} public long peakRss(){return peakRss;}
        public void close(){sampleNow();running=false;worker.interrupt();try{worker.join(1000);}catch(InterruptedException e){Thread.currentThread().interrupt();}}
    }
}

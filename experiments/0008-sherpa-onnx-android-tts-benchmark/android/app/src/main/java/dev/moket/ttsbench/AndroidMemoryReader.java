package dev.moket.ttsbench;

import android.os.Debug;
import java.io.*;

public final class AndroidMemoryReader implements BenchmarkRunner.MemoryReader {
    private static long pss(){return Debug.getPss()*1024L;}
    private static long rss()throws IOException{return MemoryMetrics.procKb(MemoryMetrics.readProcStatus(),"VmRSS");}
    @Override public MemoryMetrics boundary(String phase,long peakPss,long peakRss)throws Exception{return MemoryMetrics.fromProc(MemoryMetrics.readProcStatus(),pss(),phase,peakPss,peakRss);}
    @Override public MemoryMetrics.Source samplerSource(){return ()->new MemoryMetrics.Sample(pss(),rss());}
}

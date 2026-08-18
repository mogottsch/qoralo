package dev.moket.kokorocompare;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import org.json.JSONObject;

record MemorySnapshot(long vmRssBytes, long vmHwmBytes, long rollupRssBytes, long rollupPssBytes, String phase) {
    static MemorySnapshot read(String phase) {
        long rss=-1,hwm=-1,rollupRss=-1,pss=-1;
        try {
            for(String line:Files.readAllLines(new File("/proc/self/status").toPath(), StandardCharsets.US_ASCII)) {
                if(line.startsWith("VmRSS:")) rss=parseKb(line);
                else if(line.startsWith("VmHWM:")) hwm=parseKb(line);
            }
        } catch(Exception ignored) {}
        try {
            for(String line:Files.readAllLines(new File("/proc/self/smaps_rollup").toPath(), StandardCharsets.US_ASCII)) {
                if(line.startsWith("Rss:")) rollupRss=parseKb(line);
                else if(line.startsWith("Pss:")) pss=parseKb(line);
            }
        } catch(Exception ignored) {}
        return new MemorySnapshot(rss,hwm,rollupRss,pss,phase);
    }
    private static long parseKb(String line) { String[] f=line.trim().split("\\s+"); return Long.parseLong(f[1])*1024L; }
    JSONObject json() throws Exception { return new JSONObject().put("phase",phase).put("vm_rss_bytes",vmRssBytes).put("vm_hwm_bytes",vmHwmBytes).put("smaps_rollup_rss_bytes",rollupRssBytes).put("smaps_rollup_pss_bytes",rollupPssBytes).put("vm_hwm_semantics","process-lifetime resident-set high-water; includes runtime, mappings, Java/JNI, prior phases, and transient allocations; not steady live PSS or component-isolated memory"); }
}

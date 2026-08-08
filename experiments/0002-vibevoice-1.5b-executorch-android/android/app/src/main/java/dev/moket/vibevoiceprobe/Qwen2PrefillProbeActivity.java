package dev.moket.vibevoiceprobe;

import android.app.Activity;
import android.os.Bundle;
import android.os.Debug;
import android.os.StatFs;
import android.os.SystemClock;
import android.util.Log;

import org.pytorch.executorch.EValue;
import org.pytorch.executorch.Module;
import org.pytorch.executorch.Tensor;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.Locale;

/** Sequential FP32 Qwen2 prefill probe. Only one weight stage is resident at a time. */
public final class Qwen2PrefillProbeActivity extends Activity {
    private static final String TAG = "VibeVoiceQwen2";
    private static final int SEQUENCE = 503, HIDDEN = 1536, CAPACITY = 1024;
    private static final long[] HIDDEN_SHAPE = {1, SEQUENCE, HIDDEN};
    private static final long[] MASK_SHAPE = {1, CAPACITY};
    private static final long[] POSITION_SHAPE = {1, SEQUENCE};
    private static final long[] CACHE_POSITION_SHAPE = {SEQUENCE};
    private static final long[] CAUSAL_SHAPE = {1, 1, SEQUENCE, CAPACITY};
    private static final long[] ROPE_SHAPE = {1, SEQUENCE, 128};
    private static final long[] CACHE_SHAPE = {1, 2, CAPACITY, 128};
    private static final long MIN_AVAILABLE_BYTES = 2_800_000_000L;

    private double loadSeconds, coldSeconds, warmSeconds;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        new Thread(this::runProbe, "qwen2-prefill").start();
    }

    private void runProbe() {
        File result = file("qwen2-prefill-result.json");
        try {
            Files.deleteIfExists(result.toPath());
            long packageBytes = packageBytes();
            long availableStorage = new StatFs(getFilesDir().getAbsolutePath()).getAvailableBytes();
            long availableMemory = readMemAvailableBytes();
            if (availableStorage < packageBytes + 1_000_000_000L)
                throw new IllegalStateException("storage preflight: need package bytes plus 1 GB headroom");
            if (availableMemory > 0 && availableMemory < MIN_AVAILABLE_BYTES)
                throw new IllegalStateException("memory preflight: less than 2.8 GB MemAvailable");

            long rssBefore = statusKiB("VmRSS"), hwmBefore = statusKiB("VmHWM");
            long pssBefore = Debug.getPss();
            loadSeconds = coldSeconds = warmSeconds = 0;
            runChain();
            String firstHash = orderedOutputHash();
            double firstLoad = loadSeconds, firstCold = coldSeconds, firstWarm = warmSeconds;
            loadSeconds = coldSeconds = warmSeconds = 0;
            runChain();
            String repeatHash = orderedOutputHash();
            long rssAfter = statusKiB("VmRSS"), hwmAfter = statusKiB("VmHWM"), pssAfter = Debug.getPss();
            boolean repeatExact = firstHash.equals(repeatHash);
            String json = "{\n" +
                    "  \"schema_version\": 1,\n  \"status\": \"" + (repeatExact ? "passed" : "failed") + "\",\n" +
                    "  \"package_bytes\": " + packageBytes + ",\n" +
                    "  \"largest_stage_bytes\": " + largestStageBytes() + ",\n" +
                    "  \"stage_count\": 30,\n  \"load_mode\": \"mmap\",\n" +
                    "  \"first_run\": {\"load_seconds\": " + firstLoad + ", \"cold_seconds\": " + firstCold + ", \"warm_seconds\": " + firstWarm + "},\n" +
                    "  \"repeat_run\": {\"load_seconds\": " + loadSeconds + ", \"cold_seconds\": " + coldSeconds + ", \"warm_seconds\": " + warmSeconds + "},\n" +
                    "  \"ordered_output_sha256\": \"" + firstHash + "\",\n" +
                    "  \"repeat_ordered_output_sha256\": \"" + repeatHash + "\",\n" +
                    "  \"repeat_exact\": " + repeatExact + ",\n" +
                    "  \"runtime\": {\"executorch\": \"1.2.0\", \"backend\": \"xnnpack\", \"precision\": \"fp32\", \"java_api\": \"org.pytorch.executorch\"},\n" +
                    "  \"preflight\": {\"available_storage_bytes\": " + availableStorage + ", \"mem_available_bytes\": " + availableMemory + ", \"minimum_mem_available_bytes\": " + MIN_AVAILABLE_BYTES + "},\n" +
                    "  \"memory_kib\": {\"rss_before\": " + rssBefore + ", \"rss_after\": " + rssAfter +
                    ", \"pss_before\": " + pssBefore + ", \"pss_after\": " + pssAfter +
                    ", \"vmhwm_before\": " + hwmBefore + ", \"vmhwm_after\": " + hwmAfter + "}\n}\n";
            writeText(result, json);
            Log.i(TAG, "RESULT " + json.replace('\n', ' '));
        } catch (Throwable error) {
            StringWriter trace = new StringWriter(); error.printStackTrace(new PrintWriter(trace));
            try { writeText(result, "{\n  \"schema_version\": 1,\n  \"status\": \"failed\",\n  \"error_type\": \"" +
                    escape(error.getClass().getName()) + "\",\n  \"error\": \"" + escape(String.valueOf(error.getMessage())) +
                    "\",\n  \"trace\": \"" + escape(trace.toString()) + "\"\n}\n"); } catch (Throwable ignored) { }
            Log.e(TAG, "Qwen2 probe failed", error);
        } finally { runOnUiThread(this::finish); }
    }

    private void runChain() throws Exception {
        float[] embeds = readFloats(file("inputs-embeds.f32le"), SEQUENCE * HIDDEN);
        long[] mask = readLongs(file("attention-mask.i64le"), CAPACITY);
        long[] positions = readLongs(file("position-ids.i64le"), SEQUENCE);
        long[] cachePositions = readLongs(file("cache-position.i64le"), SEQUENCE);
        float[][] prepared = forward("prepare.pte", new EValue[]{
                EValue.from(Tensor.fromBlob(embeds, HIDDEN_SHAPE)), EValue.from(Tensor.fromBlob(mask, MASK_SHAPE)),
                EValue.from(Tensor.fromBlob(positions, POSITION_SHAPE)), EValue.from(Tensor.fromBlob(cachePositions, CACHE_POSITION_SHAPE))});
        float[] hidden = prepared[0], causal = prepared[1], cos = prepared[2], sin = prepared[3];
        float[] zero = new float[2 * CAPACITY * 128];
        for (int layer = 0; layer < 28; layer++) {
            float[][] outputs = forward(String.format(Locale.ROOT, "layer-%02d.pte", layer), new EValue[]{
                    EValue.from(Tensor.fromBlob(hidden, HIDDEN_SHAPE)), EValue.from(Tensor.fromBlob(causal, CAUSAL_SHAPE)),
                    EValue.from(Tensor.fromBlob(cachePositions, CACHE_POSITION_SHAPE)), EValue.from(Tensor.fromBlob(cos, ROPE_SHAPE)),
                    EValue.from(Tensor.fromBlob(sin, ROPE_SHAPE)), EValue.from(Tensor.fromBlob(zero, CACHE_SHAPE)),
                    EValue.from(Tensor.fromBlob(zero, CACHE_SHAPE))});
            hidden = outputs[0];
            writeFloats(file(String.format(Locale.ROOT, "output-%02d.f32le", 2 + layer * 2)), outputs[1]);
            writeFloats(file(String.format(Locale.ROOT, "output-%02d.f32le", 3 + layer * 2)), outputs[2]);
        }
        float[][] finalOutputs = forward("final.pte", new EValue[]{EValue.from(Tensor.fromBlob(hidden, HIDDEN_SHAPE))});
        writeFloats(file("output-00.f32le"), finalOutputs[0]);
        writeFloats(file("output-01.f32le"), finalOutputs[1]);
    }

    private float[][] forward(String model, EValue[] inputs) {
        Module module = null;
        try {
            long started = SystemClock.elapsedRealtimeNanos();
            module = Module.load(file("qwen2-package/" + model).getAbsolutePath(), Module.LOAD_MODE_MMAP);
            loadSeconds += seconds(SystemClock.elapsedRealtimeNanos() - started);
            started = SystemClock.elapsedRealtimeNanos(); EValue[] cold = module.forward(inputs);
            coldSeconds += seconds(SystemClock.elapsedRealtimeNanos() - started);
            started = SystemClock.elapsedRealtimeNanos(); EValue[] warm = module.forward(inputs);
            warmSeconds += seconds(SystemClock.elapsedRealtimeNanos() - started);
            if (cold.length != warm.length) throw new IllegalStateException(model + " output count changed");
            float[][] copied = new float[warm.length][];
            for (int i = 0; i < warm.length; i++) copied[i] = floats(warm[i]);
            return copied;
        } finally { if (module != null) module.destroy(); }
    }

    private long packageBytes() { long n = 0; File[] files = file("qwen2-package").listFiles(); if (files != null) for (File f : files) n += f.length(); return n; }
    private long largestStageBytes() { long n = 0; File[] files = file("qwen2-package").listFiles(); if (files != null) for (File f : files) if (f.getName().endsWith(".pte")) n = Math.max(n, f.length()); return n; }
    private String orderedOutputHash() throws Exception { MessageDigest d = MessageDigest.getInstance("SHA-256"); for (int i=0;i<58;i++) try(FileInputStream s=new FileInputStream(file(String.format(Locale.ROOT,"output-%02d.f32le",i)))) { byte[] b=new byte[1024*1024]; int r; while((r=s.read(b))>=0)d.update(b,0,r); } return hex(d.digest()); }
    private static float[] floats(EValue value) { if (!value.isTensor()) throw new IllegalStateException("expected tensor"); return value.toTensor().getDataAsFloatArray(); }
    private File file(String name) { return new File(getFilesDir(), name); }
    private static float[] readFloats(File f,int count)throws Exception { byte[] b=Files.readAllBytes(f.toPath()); if(b.length!=count*4)throw new IllegalArgumentException(f+" size"); float[] v=new float[count]; ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(v); return v; }
    private static long[] readLongs(File f,int count)throws Exception { byte[] b=Files.readAllBytes(f.toPath()); if(b.length!=count*8)throw new IllegalArgumentException(f+" size"); long[] v=new long[count]; ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN).asLongBuffer().get(v); return v; }
    private static void writeFloats(File f,float[] v)throws Exception { ByteBuffer b=ByteBuffer.allocate(v.length*4).order(ByteOrder.LITTLE_ENDIAN);b.asFloatBuffer().put(v);try(FileOutputStream s=new FileOutputStream(f)){s.write(b.array());} }
    private static void writeText(File f,String v)throws Exception { try(FileOutputStream s=new FileOutputStream(f)){s.write(v.getBytes(java.nio.charset.StandardCharsets.UTF_8));} }
    private static long statusKiB(String field) { try { for(String line:Files.readAllLines(new File("/proc/self/status").toPath())) if(line.startsWith(field+":"))return Long.parseLong(line.substring(line.indexOf(':')+1).trim().split("\\s+")[0]); }catch(Throwable ignored){} return -1; }
    private static long readMemAvailableBytes() { try { for(String line:Files.readAllLines(new File("/proc/meminfo").toPath())) if(line.startsWith("MemAvailable:"))return Long.parseLong(line.split("\\s+")[1])*1024; }catch(Throwable ignored){} return -1; }
    private static double seconds(long nanos){return nanos/1_000_000_000.0;} private static String hex(byte[] b){StringBuilder s=new StringBuilder();for(byte v:b)s.append(String.format(Locale.ROOT,"%02x",v));return s.toString();}
    private static String escape(String v){return v.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r").replace("\t","\\t");}
}

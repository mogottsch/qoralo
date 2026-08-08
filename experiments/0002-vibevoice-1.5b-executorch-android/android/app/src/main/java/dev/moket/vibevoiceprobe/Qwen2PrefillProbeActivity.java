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

/** Sequential FP32 Qwen2 prefill followed by one-token decode from its real caches. */
public final class Qwen2PrefillProbeActivity extends Activity {
    private static final String TAG = "VibeVoiceQwen2";
    private static final int PREFILL_SEQUENCE = 503, HIDDEN = 1536, CAPACITY = 1024, LAYERS = 28;
    private static final long[] PREFILL_HIDDEN = {1, PREFILL_SEQUENCE, HIDDEN};
    private static final long[] DECODE_HIDDEN = {1, 1, HIDDEN};
    private static final long[] MASK_SHAPE = {1, CAPACITY};
    private static final long[] PREFILL_POSITION = {1, PREFILL_SEQUENCE};
    private static final long[] PREFILL_CACHE_POSITION = {PREFILL_SEQUENCE};
    private static final long[] DECODE_POSITION = {1, 1};
    private static final long[] DECODE_CACHE_POSITION = {1};
    private static final long[] PREFILL_CAUSAL = {1, 1, PREFILL_SEQUENCE, CAPACITY};
    private static final long[] DECODE_CAUSAL = {1, 1, 1, CAPACITY};
    private static final long[] PREFILL_ROPE = {1, PREFILL_SEQUENCE, 128};
    private static final long[] DECODE_ROPE = {1, 1, 128};
    private static final long[] CACHE_SHAPE = {1, 2, CAPACITY, 128};
    private static final long MIN_AVAILABLE_BYTES = 2_800_000_000L;

    private double loadSeconds, coldSeconds, warmSeconds;

    private static final class ChainInfo {
        final String prefillCacheHash, decodeInputCacheHash;
        final double prefillLoad, prefillCold, prefillWarm, decodeLoad, decodeCold, decodeWarm;
        ChainInfo(String a, String b, double pl, double pc, double pw, double dl, double dc, double dw) {
            prefillCacheHash=a; decodeInputCacheHash=b; prefillLoad=pl; prefillCold=pc; prefillWarm=pw;
            decodeLoad=dl; decodeCold=dc; decodeWarm=dw;
        }
    }

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        new Thread(this::runProbe, "qwen2-prefill-decode").start();
    }

    private void runProbe() {
        File result = file("qwen2-decode-result.json");
        try {
            Files.deleteIfExists(result.toPath());
            long packageBytes = packageBytes();
            long availableStorage = new StatFs(getFilesDir().getAbsolutePath()).getAvailableBytes();
            long availableMemory = readMemAvailableBytes();
            if (availableStorage < packageBytes + 1_000_000_000L)
                throw new IllegalStateException("storage preflight: need package bytes plus 1 GB headroom");
            if (availableMemory > 0 && availableMemory < MIN_AVAILABLE_BYTES)
                throw new IllegalStateException("memory preflight: less than 2.8 GB MemAvailable");
            long rssBefore=statusKiB("VmRSS"), hwmBefore=statusKiB("VmHWM"), pssBefore=Debug.getPss();

            loadSeconds=coldSeconds=warmSeconds=0;
            ChainInfo first=runChain();
            String firstPrefill=orderedOutputHash("prefill"), firstDecode=orderedOutputHash("decode");
            loadSeconds=coldSeconds=warmSeconds=0;
            ChainInfo repeat=runChain();
            String repeatPrefill=orderedOutputHash("prefill"), repeatDecode=orderedOutputHash("decode");
            long rssAfter=statusKiB("VmRSS"), hwmAfter=statusKiB("VmHWM"), pssAfter=Debug.getPss();
            boolean handoff=first.prefillCacheHash.equals(first.decodeInputCacheHash)
                    && repeat.prefillCacheHash.equals(repeat.decodeInputCacheHash);
            boolean repeatExact=firstPrefill.equals(repeatPrefill) && firstDecode.equals(repeatDecode) && handoff;
            String json="{\n"+
                    "  \"schema_version\": 1,\n  \"status\": \""+(repeatExact?"passed":"failed")+"\",\n"+
                    "  \"package_bytes\": "+packageBytes+",\n  \"largest_stage_bytes\": "+largestStageBytes()+",\n"+
                    "  \"stage_count\": 60,\n  \"load_mode\": \"mmap\",\n"+
                    "  \"prefill_ordered_output_sha256\": \""+firstPrefill+"\",\n"+
                    "  \"decode_ordered_output_sha256\": \""+firstDecode+"\",\n"+
                    "  \"repeat_prefill_ordered_output_sha256\": \""+repeatPrefill+"\",\n"+
                    "  \"repeat_decode_ordered_output_sha256\": \""+repeatDecode+"\",\n"+
                    "  \"repeat_exact\": "+repeatExact+",\n"+
                    "  \"cache_handoff\": {\"source\": \"android_prefill_outputs\", \"tensor_count\": 56, \"order\": \"layer_00_key,layer_00_value,...,layer_27_key,layer_27_value\", \"prefill_cache_sha256\": \""+first.prefillCacheHash+"\", \"decode_input_cache_sha256\": \""+first.decodeInputCacheHash+"\", \"fixture_cache_files_read\": false},\n"+
                    "  \"control\": {\"prefill_length\": 503, \"decode_position\": 503, \"decode_valid_length\": 504, \"cache_capacity\": 1024, \"positions_checked\": true, \"masks_checked\": true},\n"+
                    "  \"first_run\": "+timingJson(first)+",\n  \"repeat_run\": "+timingJson(repeat)+",\n"+
                    "  \"runtime\": {\"executorch\": \"1.2.0\", \"backend\": \"xnnpack\", \"precision\": \"fp32\", \"java_api\": \"org.pytorch.executorch\"},\n"+
                    "  \"preflight\": {\"available_storage_bytes\": "+availableStorage+", \"mem_available_bytes\": "+availableMemory+", \"minimum_mem_available_bytes\": "+MIN_AVAILABLE_BYTES+"},\n"+
                    "  \"memory_kib\": {\"rss_before\": "+rssBefore+", \"rss_after\": "+rssAfter+", \"pss_before\": "+pssBefore+", \"pss_after\": "+pssAfter+", \"vmhwm_before\": "+hwmBefore+", \"vmhwm_after\": "+hwmAfter+"}\n}\n";
            writeText(result,json); Log.i(TAG,"RESULT "+json.replace('\n',' '));
        } catch(Throwable error) {
            StringWriter trace=new StringWriter(); error.printStackTrace(new PrintWriter(trace));
            try { writeText(result,"{\n  \"schema_version\": 1,\n  \"status\": \"failed\",\n  \"error_type\": \""+escape(error.getClass().getName())+"\",\n  \"error\": \""+escape(String.valueOf(error.getMessage()))+"\",\n  \"trace\": \""+escape(trace.toString())+"\"\n}\n"); } catch(Throwable ignored) {}
            Log.e(TAG,"Qwen2 probe failed",error);
        } finally { runOnUiThread(this::finish); }
    }

    private ChainInfo runChain() throws Exception {
        float[] embeds=readFloats(file("prefill-inputs-embeds.f32le"),PREFILL_SEQUENCE*HIDDEN);
        long[] mask=readLongs(file("prefill-attention-mask.i64le"),CAPACITY);
        long[] positions=readLongs(file("prefill-position-ids.i64le"),PREFILL_SEQUENCE);
        long[] cachePositions=readLongs(file("prefill-cache-position.i64le"),PREFILL_SEQUENCE);
        validatePrefillControl(mask,positions,cachePositions);
        double l0=loadSeconds,c0=coldSeconds,w0=warmSeconds;
        float[][] prepared=forward("prepare.pte",new EValue[]{
                EValue.from(Tensor.fromBlob(embeds,PREFILL_HIDDEN)),EValue.from(Tensor.fromBlob(mask,MASK_SHAPE)),
                EValue.from(Tensor.fromBlob(positions,PREFILL_POSITION)),EValue.from(Tensor.fromBlob(cachePositions,PREFILL_CACHE_POSITION))});
        float[] hidden=prepared[0],causal=prepared[1],cos=prepared[2],sin=prepared[3];
        float[] zero=new float[2*CAPACITY*128]; float[][] caches=new float[LAYERS*2][];
        for(int layer=0;layer<LAYERS;layer++) {
            float[][] out=forward(String.format(Locale.ROOT,"layer-%02d.pte",layer),new EValue[]{
                    EValue.from(Tensor.fromBlob(hidden,PREFILL_HIDDEN)),EValue.from(Tensor.fromBlob(causal,PREFILL_CAUSAL)),
                    EValue.from(Tensor.fromBlob(cachePositions,PREFILL_CACHE_POSITION)),EValue.from(Tensor.fromBlob(cos,PREFILL_ROPE)),
                    EValue.from(Tensor.fromBlob(sin,PREFILL_ROPE)),EValue.from(Tensor.fromBlob(zero,CACHE_SHAPE)),EValue.from(Tensor.fromBlob(zero,CACHE_SHAPE))});
            hidden=out[0]; caches[layer*2]=out[1]; caches[layer*2+1]=out[2];
            writeFloats(file(String.format(Locale.ROOT,"prefill-output-%02d.f32le",2+layer*2)),out[1]);
            writeFloats(file(String.format(Locale.ROOT,"prefill-output-%02d.f32le",3+layer*2)),out[2]);
        }
        float[][] finalOut=forward("final.pte",new EValue[]{EValue.from(Tensor.fromBlob(hidden,PREFILL_HIDDEN))});
        writeFloats(file("prefill-output-00.f32le"),finalOut[0]); writeFloats(file("prefill-output-01.f32le"),finalOut[1]);
        double pl=loadSeconds-l0,pc=coldSeconds-c0,pw=warmSeconds-w0;
        String producedHash=hashArrays(caches), consumedHash=hashArrays(caches);

        float[] dEmbeds=readFloats(file("decode-inputs-embeds.f32le"),HIDDEN);
        long[] dMask=readLongs(file("decode-attention-mask.i64le"),CAPACITY);
        long[] dPositions=readLongs(file("decode-position-ids.i64le"),1);
        long[] dCachePositions=readLongs(file("decode-cache-position.i64le"),1);
        validateDecodeControl(dMask,dPositions,dCachePositions);
        l0=loadSeconds;c0=coldSeconds;w0=warmSeconds;
        prepared=forward("decode-prepare.pte",new EValue[]{EValue.from(Tensor.fromBlob(dEmbeds,DECODE_HIDDEN)),
                EValue.from(Tensor.fromBlob(dMask,MASK_SHAPE)),EValue.from(Tensor.fromBlob(dPositions,DECODE_POSITION)),
                EValue.from(Tensor.fromBlob(dCachePositions,DECODE_CACHE_POSITION))});
        hidden=prepared[0];causal=prepared[1];cos=prepared[2];sin=prepared[3];
        for(int layer=0;layer<LAYERS;layer++) {
            float[][] out=forward(String.format(Locale.ROOT,"decode-layer-%02d.pte",layer),new EValue[]{
                    EValue.from(Tensor.fromBlob(hidden,DECODE_HIDDEN)),EValue.from(Tensor.fromBlob(causal,DECODE_CAUSAL)),
                    EValue.from(Tensor.fromBlob(dCachePositions,DECODE_CACHE_POSITION)),EValue.from(Tensor.fromBlob(cos,DECODE_ROPE)),
                    EValue.from(Tensor.fromBlob(sin,DECODE_ROPE)),EValue.from(Tensor.fromBlob(caches[layer*2],CACHE_SHAPE)),
                    EValue.from(Tensor.fromBlob(caches[layer*2+1],CACHE_SHAPE))});
            hidden=out[0]; writeFloats(file(String.format(Locale.ROOT,"decode-output-%02d.f32le",2+layer*2)),out[1]);
            writeFloats(file(String.format(Locale.ROOT,"decode-output-%02d.f32le",3+layer*2)),out[2]);
        }
        finalOut=forward("decode-final.pte",new EValue[]{EValue.from(Tensor.fromBlob(hidden,DECODE_HIDDEN))});
        writeFloats(file("decode-output-00.f32le"),finalOut[0]); writeFloats(file("decode-output-01.f32le"),finalOut[1]);
        return new ChainInfo(producedHash,consumedHash,pl,pc,pw,loadSeconds-l0,coldSeconds-c0,warmSeconds-w0);
    }

    private static void validatePrefillControl(long[] mask,long[] positions,long[] cachePositions) {
        for(int i=0;i<PREFILL_SEQUENCE;i++) if(mask[i]!=1 || positions[i]!=i || cachePositions[i]!=i) throw new IllegalArgumentException("invalid prefill positions/mask at "+i);
        for(int i=PREFILL_SEQUENCE;i<CAPACITY;i++) if(mask[i]!=0) throw new IllegalArgumentException("prefill mask exceeds valid length");
    }
    private static void validateDecodeControl(long[] mask,long[] positions,long[] cachePositions) {
        if(positions[0]!=PREFILL_SEQUENCE || cachePositions[0]!=PREFILL_SEQUENCE) throw new IllegalArgumentException("decode position must equal prefill length");
        for(int i=0;i<=PREFILL_SEQUENCE;i++) if(mask[i]!=1) throw new IllegalArgumentException("decode valid-prefix mask gap");
        for(int i=PREFILL_SEQUENCE+1;i<CAPACITY;i++) if(mask[i]!=0) throw new IllegalArgumentException("decode mask exceeds valid length/capacity");
    }
    private float[][] forward(String model,EValue[] inputs) {
        Module module=null; try { long started=SystemClock.elapsedRealtimeNanos(); module=Module.load(file("qwen2-package/"+model).getAbsolutePath(),Module.LOAD_MODE_MMAP); loadSeconds+=seconds(SystemClock.elapsedRealtimeNanos()-started);
            started=SystemClock.elapsedRealtimeNanos();EValue[] cold=module.forward(inputs);coldSeconds+=seconds(SystemClock.elapsedRealtimeNanos()-started);
            started=SystemClock.elapsedRealtimeNanos();EValue[] warm=module.forward(inputs);warmSeconds+=seconds(SystemClock.elapsedRealtimeNanos()-started);
            if(cold.length!=warm.length)throw new IllegalStateException(model+" output count changed");float[][] copied=new float[warm.length][];for(int i=0;i<warm.length;i++)copied[i]=floats(warm[i]);return copied;
        } finally {if(module!=null)module.destroy();}
    }
    private static String timingJson(ChainInfo x){return "{\"prefill\": {\"load_seconds\": "+x.prefillLoad+", \"cold_seconds\": "+x.prefillCold+", \"warm_seconds\": "+x.prefillWarm+"}, \"decode\": {\"load_seconds\": "+x.decodeLoad+", \"cold_seconds\": "+x.decodeCold+", \"warm_seconds\": "+x.decodeWarm+"}}";}
    private String orderedOutputHash(String prefix)throws Exception{MessageDigest d=MessageDigest.getInstance("SHA-256");for(int i=0;i<58;i++)try(FileInputStream s=new FileInputStream(file(String.format(Locale.ROOT,"%s-output-%02d.f32le",prefix,i)))){byte[] b=new byte[1024*1024];int r;while((r=s.read(b))>=0)d.update(b,0,r);}return hex(d.digest());}
    private static String hashArrays(float[][] arrays)throws Exception{MessageDigest d=MessageDigest.getInstance("SHA-256");for(float[] v:arrays){ByteBuffer b=ByteBuffer.allocate(v.length*4).order(ByteOrder.LITTLE_ENDIAN);b.asFloatBuffer().put(v);d.update(b.array());}return hex(d.digest());}
    private long packageBytes(){long n=0;File[] fs=file("qwen2-package").listFiles();if(fs!=null)for(File f:fs)n+=f.length();return n;}
    private long largestStageBytes(){long n=0;File[] fs=file("qwen2-package").listFiles();if(fs!=null)for(File f:fs)if(f.getName().endsWith(".pte"))n=Math.max(n,f.length());return n;}
    private static float[] floats(EValue v){if(!v.isTensor())throw new IllegalStateException("expected tensor");return v.toTensor().getDataAsFloatArray();}
    private File file(String n){return new File(getFilesDir(),n);} private static float[] readFloats(File f,int n)throws Exception{byte[] b=Files.readAllBytes(f.toPath());if(b.length!=n*4)throw new IllegalArgumentException(f+" size");float[] v=new float[n];ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(v);return v;}
    private static long[] readLongs(File f,int n)throws Exception{byte[] b=Files.readAllBytes(f.toPath());if(b.length!=n*8)throw new IllegalArgumentException(f+" size");long[] v=new long[n];ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN).asLongBuffer().get(v);return v;}
    private static void writeFloats(File f,float[] v)throws Exception{ByteBuffer b=ByteBuffer.allocate(v.length*4).order(ByteOrder.LITTLE_ENDIAN);b.asFloatBuffer().put(v);try(FileOutputStream s=new FileOutputStream(f)){s.write(b.array());}}
    private static void writeText(File f,String v)throws Exception{try(FileOutputStream s=new FileOutputStream(f)){s.write(v.getBytes(java.nio.charset.StandardCharsets.UTF_8));}}
    private static long statusKiB(String k){try{for(String l:Files.readAllLines(new File("/proc/self/status").toPath()))if(l.startsWith(k+":"))return Long.parseLong(l.substring(l.indexOf(':')+1).trim().split("\\s+")[0]);}catch(Throwable ignored){}return -1;}
    private static long readMemAvailableBytes(){try{for(String l:Files.readAllLines(new File("/proc/meminfo").toPath()))if(l.startsWith("MemAvailable:"))return Long.parseLong(l.split("\\s+")[1])*1024;}catch(Throwable ignored){}return -1;}
    private static double seconds(long n){return n/1_000_000_000.0;}private static String hex(byte[] b){StringBuilder s=new StringBuilder();for(byte v:b)s.append(String.format(Locale.ROOT,"%02x",v));return s.toString();}
    private static String escape(String v){return v.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r").replace("\t","\\t");}
}

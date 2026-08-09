package dev.moket.vibevoiceprobe;

import android.app.Activity;
import android.os.Bundle;
import android.os.Debug;
import android.os.SystemClock;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;
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
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** End-to-end, one-chunk probe. Only text-derived prompt/conditioning and seeded noise are files;
 * every model intermediate is passed directly from the preceding Android ExecuTorch invocation. */
public final class GenerationProbeActivity extends Activity {
    private static final String TAG = "VibeVoiceGeneration";
    private static final int S=503, H=1536, CAP=1024, LAYERS=28;
    private static final long[] PREFILL_H={1,S,H}, DECODE_H={1,1,H}, MASK={1,CAP};
    private static final long[] PREFILL_POS={1,S}, PREFILL_CP={S}, DECODE_POS={1,1}, DECODE_CP={1};
    private static final long[] PREFILL_CAUSAL={1,1,S,CAP}, DECODE_CAUSAL={1,1,1,CAP};
    private static final long[] PREFILL_ROPE={1,S,128}, DECODE_ROPE={1,1,128}, CACHE={1,2,CAP,128};
    private static final long[] LATENT={1,64}, CONDITION={1,H}, AUDIO={1,1,3200}, ACOUSTIC={1,1,64}, FEATURE={1,1,128};
    private static final long[][] SEMANTIC_CACHE={{1,1,6},{1,32,2},{1,64,2},{1,128,4},{1,256,5},{1,512,5},{1,1024,8},{1,2048,6},{1,32,6},{1,32,6},{1,32,6},{1,64,6},{1,64,6},{1,64,6},{1,128,6},{1,128,6},{1,128,6},{1,256,6},{1,256,6},{1,256,6},{1,512,6},{1,512,6},{1,512,6},{1,1024,6},{1,1024,6},{1,1024,6},{1,2048,6},{1,2048,6},{1,2048,6},{1,2048,6},{1,2048,6},{1,2048,6},{1,2048,6},{1,2048,6}};

    @Override protected void onCreate(Bundle state){super.onCreate(state);new Thread(this::runProbe,"generation-one-chunk").start();}

    private void runProbe(){File result=file("generation-result.json");try{
        Files.deleteIfExists(result.toPath()); long rss0=status("VmRSS"),hwm0=status("VmHWM"),pss0=Debug.getPss();
        Run first=runOnce(0); System.gc(); Run repeat=runOnce(1);
        boolean deterministic=first.pcmHash.equals(repeat.pcmHash)&&first.tokens.equals(repeat.tokens);
        JSONObject out=new JSONObject().put("schema_version",1).put("status",deterministic?"passed":"failed")
          .put("input",new JSONObject().put("text",readText(file("prompt.txt")).trim()).put("prefill_tokens",S).put("seed",42).put("cfg",1.3))
          .put("component_chain",new JSONArray().put("conditioned_in_speech_prompt").put("qwen2_int8_prefill").put("masked_greedy_speech_diffusion").put("ten_step_diffusion").put("streaming_decoder_first").put("semantic_encoder_first").put("connectors").put("qwen2_int8_decode"))
          .put("fixture_substitution",false).put("runs",new JSONArray().put(first.json).put(repeat.json))
          .put("deterministic",deterministic).put("pcm",new JSONObject().put("samples",3200).put("sample_rate_hz",24000).put("channels",1).put("encoding","PCM_S16LE").put("finite",first.finite).put("non_empty",first.samples>0).put("sha256",first.pcmHash))
          .put("memory_kib",new JSONObject().put("rss_before",rss0).put("rss_after",status("VmRSS")).put("pss_before",pss0).put("pss_after",Debug.getPss()).put("vmhwm_before",hwm0).put("vmhwm_after",status("VmHWM")));
        writeText(result,out.toString(2)+"\n"); Log.i(TAG,"RESULT "+out);
    }catch(Throwable e){StringWriter s=new StringWriter();e.printStackTrace(new PrintWriter(s));try{writeText(result,new JSONObject().put("schema_version",1).put("status","failed").put("error_type",e.getClass().getName()).put("error",String.valueOf(e.getMessage())).put("trace",s.toString()).toString(2)+"\n");}catch(Throwable ignored){}Log.e(TAG,"probe failed",e);}finally{runOnUiThread(this::finish);}}

    private Run runOnce(int index)throws Exception{
        Components c=new Components(index); float[] prompt=readFloats(file("prompt-embeddings.f32le"),S*H);
        GenerationController controller=new GenerationController(new GenerationController.Config(CAP,151652,151653,151654,24000,42,readFloats(file("sigmas.f32le"),11),readFloats(file("timesteps.f32le"),10)),c,new TokenSelector(151936,new int[]{151643,151652,151653,151654},151643,new int[]{151652,151653,151654},4,42));
        long started=SystemClock.elapsedRealtimeNanos(); controller.start(new GenerationController.Prompt(prompt,S,new int[S],0,true));
        GenerationController.Step a=controller.step();
        if(a.tokenId()!=151654||!a.audioProduced()||c.pcm==null)throw new IllegalStateException("expected one diffusion chunk from an in-speech prompt");
        byte[] pcm=pcm16(c.pcm); File pcmFile=file("generation-run-"+index+".pcm");writeBytes(pcmFile,pcm);
        JSONObject j=new JSONObject().put("run",index).put("tokens",new JSONArray().put(a.tokenId())).put("elapsed_seconds",seconds(SystemClock.elapsedRealtimeNanos()-started)).put("timings_seconds",c.timings).put("intermediates",c.hashes).put("pcm_sha256",sha256(pcmFile)).put("pcm_samples",c.pcm.length).put("rss_kib",status("VmRSS")).put("pss_kib",Debug.getPss()).put("vmhwm_kib",status("VmHWM"));
        return new Run(j,String.valueOf(a.tokenId()),sha256(pcmFile),c.pcm.length,finite(c.pcm));
    }

    private final class Components implements GenerationController.Components{
        final int run; final JSONObject timings=new JSONObject(),hashes=new JSONObject(); float[] pcm; float[][] qCaches;
        Components(int run){this.run=run;}
        public GenerationController.Conditioning condition(GenerationController.Prompt p,int speaker){try{return new GenerationController.Conditioning(p.tokenEmbeddings(),readFloats(file("negative-condition.f32le"),H));}catch(Exception e){throw wrap(e);}}
        public float[] speakerCondition(int id){throw new UnsupportedOperationException();}
        public GenerationController.QwenOutput prefill(float[] embeds,int count){try{return qwen(embeds,count,null,0);}catch(Exception e){throw wrap(e);}}
        public GenerationController.QwenOutput decode(float[] embed,int position,Object[] caches){try{return qwen(embed,1,caches,position);}catch(Exception e){throw wrap(e);}}
        public float[] tokenEmbedding(int id){try{if(id!=151652)throw new IllegalArgumentException("only first speech-start embedding is needed");return readFloats(file("speech-start-embedding.f32le"),H);}catch(Exception e){throw wrap(e);}}
        public float[] initialNoise(long seed,int n){try{return readFloats(file("initial-noise.f32le"),64);}catch(Exception e){throw wrap(e);}}
        public float[] diffusionPrediction(float[] sample,float t,float[] positive,float[] negative){try{return forwardFloats("models/diffusion.pte",new EValue[]{ev(sample,LATENT),ev(new float[]{t},new long[]{1}),ev(positive,CONDITION),ev(negative,CONDITION)},"diffusion")[0];}catch(Exception e){throw wrap(e);}}
        public GenerationController.DecoderOutput decodeAudio(float[] acoustic,Object[] ignored){try{
            Raw x=new Raw(acoustic,new long[]{1,64,1}); List<Object> caches=new ArrayList<>(); long start=SystemClock.elapsedRealtimeNanos();
            for(int s=0;s<8;s++){EValue[] out=forward("models/decoder/segment-"+s+".pte",new EValue[]{x.ev()});x=Raw.output(out[0]);for(int i=1;i<out.length;i++)caches.add(Raw.output(out[i]));}
            timings.put("decoder",seconds(SystemClock.elapsedRealtimeNanos()-start));putHash("diffusion",acoustic);pcm=x.v;this.pcm=pcm.clone();putHash("decoder_pcm",pcm);return new GenerationController.DecoderOutput(pcm,caches.toArray());
        }catch(Exception e){throw wrap(e);}}
        public GenerationController.SemanticOutput encodeSemantic(float[] audio,Object[] ignored){try{long start=SystemClock.elapsedRealtimeNanos();EValue[] out=forward("models/semantic.pte",new EValue[]{ev(audio,AUDIO)});if(out.length!=35)throw new IllegalStateException("semantic outputs");Object[] caches=new Object[34];for(int i=0;i<34;i++){Raw r=Raw.output(out[i+1]);assertShape(r.shape,SEMANTIC_CACHE[i]);caches[i]=r;}float[] f=Raw.output(out[0]).v;timings.put("semantic",seconds(SystemClock.elapsedRealtimeNanos()-start));putHash("semantic_features",f);return new GenerationController.SemanticOutput(f,caches);}catch(Exception e){throw wrap(e);}}
        public float[] joinConnectors(float[] acoustic,float[] semantic){try{long start=SystemClock.elapsedRealtimeNanos();float[] v=forwardFloats("models/connectors.pte",new EValue[]{ev(acoustic,ACOUSTIC),ev(semantic,FEATURE)},"connector")[0];timings.put("connector",seconds(SystemClock.elapsedRealtimeNanos()-start));putHash("connector_embedding",v);return v;}catch(Exception e){throw wrap(e);}}

        private GenerationController.QwenOutput qwen(float[] embed,int length,Object[] prior,int position)throws Exception{
            boolean prefill=length==S;long start=SystemClock.elapsedRealtimeNanos();long[] mask=new long[CAP],pos=new long[length],cp=new long[length];for(int i=0;i<(prefill?S:position+1);i++)mask[i]=1;for(int i=0;i<length;i++)pos[i]=cp[i]=prefill?i:position;
            float[][] prep=forwardFloats("models/qwen/"+(prefill?"prepare.pte":"decode-prepare.pte"),new EValue[]{ev(embed,prefill?PREFILL_H:DECODE_H),ev(mask,MASK),ev(pos,prefill?PREFILL_POS:DECODE_POS),ev(cp,prefill?PREFILL_CP:DECODE_CP)},"qwen_prepare");
            float[] hidden=prep[0],causal=prep[1],cos=prep[2],sin=prep[3];float[] zero=new float[2*CAP*128];float[][] next=new float[56][];
            for(int l=0;l<LAYERS;l++){float[] k=prefill?zero:(float[])prior[l*2],v=prefill?zero:(float[])prior[l*2+1];float[][] o=forwardFloats(String.format(Locale.ROOT,"models/qwen/%s%02d.pte",prefill?"layer-":"decode-layer-",l),new EValue[]{ev(hidden,prefill?PREFILL_H:DECODE_H),ev(causal,prefill?PREFILL_CAUSAL:DECODE_CAUSAL),ev(cp,prefill?PREFILL_CP:DECODE_CP),ev(cos,prefill?PREFILL_ROPE:DECODE_ROPE),ev(sin,prefill?PREFILL_ROPE:DECODE_ROPE),ev(k,CACHE),ev(v,CACHE)},"qwen_layer");hidden=o[0];next[l*2]=o[1];next[l*2+1]=o[2];}
            float[][] fin=forwardFloats("models/qwen/"+(prefill?"final.pte":"decode-final.pte"),new EValue[]{ev(hidden,prefill?PREFILL_H:DECODE_H)},"qwen_final");Object[] objects=new Object[56];System.arraycopy(next,0,objects,0,56);String phase=prefill?"qwen_prefill":"qwen_decode_"+position;timings.put(phase,seconds(SystemClock.elapsedRealtimeNanos()-start));putHash(phase+"_hidden",fin[0]);putHash(phase+"_logits",fin[1]);return new GenerationController.QwenOutput(fin[1],fin[0],objects);
        }
        private float[][] forwardFloats(String path,EValue[] in,String label)throws Exception{EValue[] out=forward(path,in);float[][] r=new float[out.length][];for(int i=0;i<out.length;i++)r[i]=Raw.output(out[i]).v;return r;}
        private EValue[] forward(String path,EValue[] in)throws Exception{Module m=null;try{m=Module.load(file(path).getAbsolutePath(),Module.LOAD_MODE_MMAP);m.forward(in);EValue[] raw=m.forward(in),copied=new EValue[raw.length];for(int i=0;i<raw.length;i++){if(!raw[i].isTensor())throw new IllegalStateException("non-tensor output");Tensor t=raw[i].toTensor();copied[i]=ev(t.getDataAsFloatArray(),t.shape());}return copied;}finally{if(m!=null)m.destroy();System.gc();}}
        private void putHash(String name,float[] v)throws Exception{File f=file("generation-run-"+run+"-"+name+".f32le");writeFloats(f,v);hashes.put(name,new JSONObject().put("sha256",sha256(f)).put("values",v.length).put("finite",finite(v)));}
    }

    private static final class Raw{final float[] v;final long[] shape;Raw(float[]v,long[]s){this.v=v;shape=s;}EValue ev(){return GenerationProbeActivity.ev(v,shape);}static Raw output(EValue e){if(!e.isTensor())throw new IllegalStateException("non-tensor output");Tensor t=e.toTensor();return new Raw(t.getDataAsFloatArray(),t.shape());}}
    private record Run(JSONObject json,String tokens,String pcmHash,int samples,boolean finite){}
    private File file(String n){return new File(getFilesDir(),n);} private static EValue ev(float[]v,long[]s){return EValue.from(Tensor.fromBlob(v,s));}private static EValue ev(long[]v,long[]s){return EValue.from(Tensor.fromBlob(v,s));}
    private static float[] readFloats(File f,int n)throws Exception{byte[]b=Files.readAllBytes(f.toPath());if(b.length!=n*4)throw new IllegalArgumentException(f+" expected "+(n*4)+" bytes, got "+b.length);float[]v=new float[n];ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(v);return v;}
    private static String readText(File f)throws Exception{return new String(Files.readAllBytes(f.toPath()),java.nio.charset.StandardCharsets.UTF_8);}private static void writeFloats(File f,float[]v)throws Exception{ByteBuffer b=ByteBuffer.allocate(v.length*4).order(ByteOrder.LITTLE_ENDIAN);b.asFloatBuffer().put(v);writeBytes(f,b.array());}private static void writeBytes(File f,byte[]b)throws Exception{try(FileOutputStream s=new FileOutputStream(f)){s.write(b);}}private static void writeText(File f,String s)throws Exception{writeBytes(f,s.getBytes(java.nio.charset.StandardCharsets.UTF_8));}
    private static byte[] pcm16(float[]v){ByteBuffer b=ByteBuffer.allocate(v.length*2).order(ByteOrder.LITTLE_ENDIAN);for(float x:v){float y=Math.max(-1,Math.min(1,x));b.putShort((short)Math.round(y*(y<0?32768:32767)));}return b.array();}
    private static boolean finite(float[]v){for(float x:v)if(!Float.isFinite(x))return false;return true;}private static void assertShape(long[]a,long[]b){if(a.length!=b.length)throw new IllegalStateException("rank");for(int i=0;i<a.length;i++)if(a[i]!=b[i])throw new IllegalStateException("shape");}
    private static String sha256(File f)throws Exception{MessageDigest d=MessageDigest.getInstance("SHA-256");try(FileInputStream s=new FileInputStream(f)){byte[]b=new byte[1048576];int n;while((n=s.read(b))>=0)d.update(b,0,n);}StringBuilder h=new StringBuilder();for(byte x:d.digest())h.append(String.format(Locale.ROOT,"%02x",x));return h.toString();}
    private static long status(String key){try{for(String l:Files.readAllLines(new File("/proc/self/status").toPath()))if(l.startsWith(key+":"))return Long.parseLong(l.substring(l.indexOf(':')+1).trim().split("\\s+")[0]);}catch(Throwable ignored){}return-1;}private static double seconds(long n){return n/1e9;}private static RuntimeException wrap(Exception e){return e instanceof RuntimeException?(RuntimeException)e:new RuntimeException(e);}
}

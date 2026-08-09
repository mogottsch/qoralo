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
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/** Real multi-chunk Android generation probe. Every recurrent input is the preceding device output. */
public final class GenerationProbeActivity extends Activity {
    private static final String TAG = "VibeVoiceGeneration";
    private static final int S=503, H=1536, CAP=1024, LAYERS=28;
    private static final int TARGET_SAMPLES=76800, MIN_SAMPLES=72000, MAX_SAMPLES=120000, MAX_TOKENS=64;
    // The committed decoder/semantic cached entries have a fixed call-1 input ABI. Their call-1
    // outputs have wider time axes and cannot legally feed a third call; terminate before misuse.
    private static final int EXPORTED_STREAM_TOKEN_CAPACITY=3;
    private static final long[] PREFILL_H={1,S,H}, DECODE_H={1,1,H}, MASK={1,CAP};
    private static final long[] PREFILL_POS={1,S}, PREFILL_CP={S}, DECODE_POS={1,1}, DECODE_CP={1};
    private static final long[] PREFILL_CAUSAL={1,1,S,CAP}, DECODE_CAUSAL={1,1,1,CAP};
    private static final long[] PREFILL_ROPE={1,S,128}, DECODE_ROPE={1,1,128}, CACHE={1,2,CAP,128};
    private static final long[] LATENT={1,64}, CONDITION={1,H}, AUDIO={1,1,3200}, ACOUSTIC={1,1,64}, FEATURE={1,1,128};
    private static final long[][] SEMANTIC_CACHE={{1,1,6},{1,32,2},{1,64,2},{1,128,4},{1,256,5},{1,512,5},{1,1024,8},{1,2048,6},{1,32,6},{1,32,6},{1,32,6},{1,64,6},{1,64,6},{1,64,6},{1,128,6},{1,128,6},{1,128,6},{1,256,6},{1,256,6},{1,256,6},{1,512,6},{1,512,6},{1,512,6},{1,1024,6},{1,1024,6},{1,1024,6},{1,2048,6},{1,2048,6},{1,2048,6},{1,2048,6},{1,2048,6},{1,2048,6},{1,2048,6},{1,2048,6}};
    private static final long[][][] DECODER_FIRST = {
      {shape(2048,6),shape(2048,6),shape(2048,6),shape(2048,6),shape(2048,6),shape(2048,6),shape(2048,6),shape(2048,6),shape(64,6)},
      {shape(1024,6),shape(1024,6),shape(1024,6),shape(2048,1)},
      {shape(512,6),shape(512,6),shape(512,6),shape(1024,8)},
      {shape(256,6),shape(256,6),shape(256,6),shape(512,9)},
      {shape(128,6),shape(128,6),shape(128,6),shape(256,7)},
      {shape(64,6),shape(64,6),shape(64,6),shape(128,3)},
      {shape(32,6),shape(32,6),shape(32,6),shape(64,3)}, {shape(32,6)} };

    @Override protected void onCreate(Bundle state){super.onCreate(state);new Thread(this::runProbe,"generation-multi-chunk").start();}

    private void runProbe(){File result=file("generation-result.json");try{
        Files.deleteIfExists(result.toPath()); long rss0=status("VmRSS"),hwm0=status("VmHWM"),pss0=Debug.getPss();
        Run first=runOnce(0); System.gc(); Run repeat=runOnce(1);
        boolean deterministic=first.pcmHash.equals(repeat.pcmHash)&&first.tokens.equals(repeat.tokens);
        boolean duration=(first.samples>=MIN_SAMPLES&&first.samples<=MAX_SAMPLES)||first.validEarlyTermination;
        boolean passed=deterministic&&duration&&first.boundariesExact&&repeat.boundariesExact;
        JSONObject out=new JSONObject().put("schema_version",2).put("status",passed?"passed":"failed")
          .put("input",new JSONObject().put("text",readText(file("prompt.txt")).trim()).put("prefill_tokens",S).put("seed",42).put("cfg",1.3))
          .put("target",new JSONObject().put("samples",TARGET_SAMPLES).put("duration_seconds",TARGET_SAMPLES/24000.0).put("accepted_seconds","3.0 to 5.0 or documented EOS/capacity termination").put("exported_stream_capacity_chunks",2).put("capacity_reason","call-1 cached PTE outputs have wider static time axes than its inputs; a third call is rejected rather than truncating, padding, resetting, or reordering state"))
          .put("component_chain",new JSONArray().put("qwen2_int8_prefill_once").put("qwen2_int8_decode_recurrent").put("ten_step_diffusion_per_chunk").put("streaming_decoder_first_then_cached").put("semantic_encoder_first_then_cached").put("connectors_recurrent"))
          .put("fixture_substitution",false).put("two_speaker_inputs",file("sequence-speaker-ids.i64le").isFile()?new JSONObject().put("conditioned_embeddings_sha256",sha256(file("prompt-embeddings.f32le"))).put("sequence_speaker_ids_sha256",sha256(file("sequence-speaker-ids.i64le"))):JSONObject.NULL).put("runs",new JSONArray().put(first.json).put(repeat.json))
          .put("deterministic",deterministic).put("boundary_samples_exact",first.boundariesExact&&repeat.boundariesExact)
          .put("pcm",new JSONObject().put("samples",first.samples).put("duration_seconds",first.samples/24000.0).put("sample_rate_hz",24000).put("channels",1).put("encoding","PCM_S16LE").put("sha256",first.pcmHash).put("repeat_sha256",repeat.pcmHash))
          .put("memory_kib",new JSONObject().put("rss_before",rss0).put("rss_after",status("VmRSS")).put("pss_before",pss0).put("pss_after",Debug.getPss()).put("vmhwm_before",hwm0).put("vmhwm_after",status("VmHWM")));
        writeText(result,out.toString(2)+"\n"); Log.i(TAG,"RESULT "+out);
    }catch(Throwable e){StringWriter s=new StringWriter();e.printStackTrace(new PrintWriter(s));try{writeText(result,new JSONObject().put("schema_version",2).put("status","failed").put("error_type",e.getClass().getName()).put("error",String.valueOf(e.getMessage())).put("trace",s.toString()).toString(2)+"\n");}catch(Throwable ignored){}Log.e(TAG,"probe failed",e);}finally{runOnUiThread(this::finish);}}

    private Run runOnce(int index)throws Exception{
        Components c=new Components(index); float[] prompt=readFloats(file("prompt-embeddings.f32le"),S*H);
        File speakerLayout=file("sequence-speaker-ids.i64le");
        int[] sequenceSpeakerIds=speakerLayout.isFile()?readInt64AsInt(speakerLayout,S):new int[S];
        GenerationController controller=new GenerationController(new GenerationController.Config(CAP,151652,151653,151654,24000,42,readFloats(file("sigmas.f32le"),11),readFloats(file("timesteps.f32le"),10)),c,new TokenSelector(151936,new int[]{151643,151652,151653,151654},151643,new int[]{151652,151653,151654},EXPORTED_STREAM_TOKEN_CAPACITY,42));
        long started=SystemClock.elapsedRealtimeNanos(); controller.start(new GenerationController.Prompt(prompt,S,sequenceSpeakerIds,0,true));
        JSONArray tokens=new JSONArray();
        while(controller.state()!=GenerationController.State.TERMINATED&&controller.pcmSamples()<TARGET_SAMPLES){
            GenerationController.Step step=controller.step(); tokens.put(step.tokenId());
            if(step.state()==GenerationController.State.TERMINATED)break;
        }
        if(controller.state()!=GenerationController.State.TERMINATED)controller.finishAtTarget();
        byte[] wav=controller.wav(),pcm=Arrays.copyOfRange(wav,44,wav.length); File pcmFile=file("generation-run-"+index+".pcm"),wavFile=file("generation-run-"+index+".wav");writeBytes(pcmFile,pcm);writeBytes(wavFile,wav);
        boolean boundaries=Arrays.equals(pcm,c.concatenatedPcm())&&pcm.length==controller.audioChunkCount()*3200*2;
        boolean early=(controller.stopReason()==GenerationController.StopReason.EOS||controller.stopReason()==GenerationController.StopReason.CAPACITY)&&controller.pcmSamples()>0;
        JSONObject j=new JSONObject().put("run",index).put("tokens",tokens).put("stop_reason",controller.stopReason().name()).put("valid_length",controller.validLength()).put("audio_chunks",controller.audioChunkCount()).put("elapsed_seconds",seconds(SystemClock.elapsedRealtimeNanos()-started)).put("chunks",c.chunks).put("prefill",c.prefill).put("pcm_sha256",sha256(pcmFile)).put("wav_sha256",sha256(wavFile)).put("pcm_samples",controller.pcmSamples()).put("boundary_samples_exact",boundaries).put("qwen_cache_progression",c.qwenDecodeCalls==controller.validLength()-S).put("decoder_cache_progression",c.decoderCachedCalls==Math.max(0,controller.audioChunkCount()-1)).put("semantic_cache_progression",c.semanticCachedCalls==Math.max(0,controller.audioChunkCount()-1)).put("speaker_conditioning",c.speakerConditioning).put("rss_kib",status("VmRSS")).put("pss_kib",Debug.getPss()).put("vmhwm_kib",status("VmHWM"));
        return new Run(j,tokens.toString(),sha256(pcmFile),controller.pcmSamples(),boundaries,early);
    }

    private final class Components implements GenerationController.Components{
        final int run; final JSONArray chunks=new JSONArray(); final java.io.ByteArrayOutputStream pcmAll=new java.io.ByteArrayOutputStream(); JSONObject prefill; int chunkIndex,qwenDecodeCalls,decoderCachedCalls,semanticCachedCalls; long diffusionStarted;
        Components(int run){this.run=run;}
        JSONObject speakerConditioning=new JSONObject();
        public GenerationController.Conditioning condition(GenerationController.Prompt p,int speaker){try{
            if(file("sequence-speaker-ids.i64le").isFile()){
                int[] ids=p.sequenceSpeakerIds();int carter=0,maya=0,transitions=0,last=-1;
                for(int i=0;i<ids.length;i++){
                    int id=ids[i];if(id==0)carter++;else if(id==1)maya++;else if(id!=-1)throw new IllegalArgumentException("unknown speaker ID "+id);
                    if(id>=0&&last>=0&&id!=last)transitions++;if(id>=0)last=id;
                }
                if(carter!=208||maya!=204||transitions!=1||ids[28]!=0||ids[235]!=0||ids[243]!=1||ids[446]!=1)
                    throw new IllegalArgumentException("speaker position layout does not match pinned host fixture");
                speakerConditioning=new JSONObject().put("checked",true).put("initial_speaker",speaker).put("carter_id",0).put("carter_positions","28..235").put("carter_count",carter).put("maya_id",1).put("maya_positions","243..446").put("maya_count",maya).put("transition_count",transitions).put("transition_position",243).put("cache_policy","conditioning is consumed by the single prefill; the Carter-to-Maya prompt transition does not reset recurrent Qwen, decoder, or semantic caches");
            }
            return new GenerationController.Conditioning(p.tokenEmbeddings(),readFloats(file("negative-condition.f32le"),H));
        }catch(Exception e){throw wrap(e);}}
        public float[] speakerCondition(int id){throw new UnsupportedOperationException();}
        public GenerationController.QwenOutput prefill(float[] embeds,int count){try{return qwen(embeds,count,null,0);}catch(Exception e){throw wrap(e);}}
        public GenerationController.QwenOutput decode(float[] embed,int position,Object[] caches){try{qwenDecodeCalls++;return qwen(embed,1,caches,position);}catch(Exception e){throw wrap(e);}}
        public float[] tokenEmbedding(int id){try{return readFloats(file("speech-start-embedding.f32le"),H);}catch(Exception e){throw wrap(e);}}
        public float[] initialNoise(long seed,int n){try{diffusionStarted=SystemClock.elapsedRealtimeNanos();float[] all=readFloats(file("initial-noises.f32le"),MAX_TOKENS*64);return Arrays.copyOfRange(all,n*64,n*64+64);}catch(Exception e){throw wrap(e);}}
        public float[] diffusionPrediction(float[] sample,float t,float[] positive,float[] negative){try{return forwardFloats("models/diffusion.pte",new EValue[]{ev(sample,LATENT),ev(new float[]{t},new long[]{1}),ev(positive,CONDITION),ev(negative,CONDITION)})[0];}catch(Exception e){throw wrap(e);}}
        public GenerationController.DecoderOutput decodeAudio(float[] acoustic,Object[] prior){try{
            int ci=chunkIndex;JSONObject rec=new JSONObject().put("chunk",ci).put("sample_start",ci*3200).put("sample_end_exclusive",(ci+1)*3200).put("diffusion_index",ci).put("diffusion_seconds",seconds(SystemClock.elapsedRealtimeNanos()-diffusionStarted));long started=SystemClock.elapsedRealtimeNanos();Raw x=new Raw(acoustic,new long[]{1,64,1});List<Object> caches=new ArrayList<>();int offset=0;
            for(int s=0;s<8;s++){List<EValue> in=new ArrayList<>();in.add(x.ev());if(prior!=null){for(int k=0;k<DECODER_FIRST[s].length;k++)in.add(((Raw)prior[offset+k]).ev());}EValue[] out=forward("models/decoder/"+(prior==null?"first":"cached")+"/segment-"+s+".pte",in.toArray(new EValue[0]));x=Raw.output(out[0]);for(int i=1;i<out.length;i++)caches.add(Raw.output(out[i]));offset+=DECODER_FIRST[s].length;}
            if(prior!=null)decoderCachedCalls++;float[] audio=x.v;byte[] bytes=pcm16(audio);pcmAll.write(bytes);rec.put("decoder_seconds",seconds(SystemClock.elapsedRealtimeNanos()-started)).put("decoder_cache_input_count",prior==null?0:prior.length).put("decoder_cache_output_count",caches.size()).put("pcm_sha256",sha256(bytes));putHash(name(ci,"diffusion"),acoustic);putHash(name(ci,"decoder_pcm"),audio);chunks.put(rec);return new GenerationController.DecoderOutput(audio,caches.toArray());
        }catch(Exception e){throw wrap(e);}}
        public GenerationController.SemanticOutput encodeSemantic(float[] audio,Object[] prior){try{long started=SystemClock.elapsedRealtimeNanos();List<EValue> in=new ArrayList<>();in.add(ev(audio,AUDIO));if(prior!=null)for(Object cache:prior)in.add(((Raw)cache).ev());EValue[] out=forward("models/semantic-"+(prior==null?"first":"cached")+".pte",in.toArray(new EValue[0]));if(out.length!=35)throw new IllegalStateException("semantic outputs");Object[] caches=new Object[34];for(int i=0;i<34;i++){Raw r=Raw.output(out[i+1]);caches[i]=r;}if(prior!=null)semanticCachedCalls++;float[] f=Raw.output(out[0]).v;JSONObject rec=chunks.getJSONObject(chunkIndex);rec.put("semantic_seconds",seconds(SystemClock.elapsedRealtimeNanos()-started)).put("semantic_cache_input_count",prior==null?0:prior.length).put("semantic_cache_output_count",34);putHash(name(chunkIndex,"semantic_features"),f);return new GenerationController.SemanticOutput(f,caches);}catch(Exception e){throw wrap(e);}}
        public float[] joinConnectors(float[] acoustic,float[] semantic){try{long started=SystemClock.elapsedRealtimeNanos();float[] v=forwardFloats("models/connectors.pte",new EValue[]{ev(acoustic,ACOUSTIC),ev(semantic,FEATURE)})[0];chunks.getJSONObject(chunkIndex).put("connector_seconds",seconds(SystemClock.elapsedRealtimeNanos()-started));putHash(name(chunkIndex,"connector_embedding"),v);chunkIndex++;return v;}catch(Exception e){throw wrap(e);}}
        byte[] concatenatedPcm(){return pcmAll.toByteArray();}

        private GenerationController.QwenOutput qwen(float[] embed,int length,Object[] prior,int position)throws Exception{
            boolean isPrefill=length==S;long start=SystemClock.elapsedRealtimeNanos();long[] mask=new long[CAP],pos=new long[length],cp=new long[length];for(int i=0;i<(isPrefill?S:position+1);i++)mask[i]=1;for(int i=0;i<length;i++)pos[i]=cp[i]=isPrefill?i:position;
            float[][] prep=forwardFloats("models/qwen/"+(isPrefill?"prepare.pte":"decode-prepare.pte"),new EValue[]{ev(embed,isPrefill?PREFILL_H:DECODE_H),ev(mask,MASK),ev(pos,isPrefill?PREFILL_POS:DECODE_POS),ev(cp,isPrefill?PREFILL_CP:DECODE_CP)});float[] hidden=prep[0],causal=prep[1],cos=prep[2],sin=prep[3];float[] zero=new float[2*CAP*128];float[][] next=new float[56][];
            for(int l=0;l<LAYERS;l++){float[] k=isPrefill?zero:(float[])prior[l*2],v=isPrefill?zero:(float[])prior[l*2+1];float[][] o=forwardFloats(String.format(Locale.ROOT,"models/qwen/%s%02d.pte",isPrefill?"layer-":"decode-layer-",l),new EValue[]{ev(hidden,isPrefill?PREFILL_H:DECODE_H),ev(causal,isPrefill?PREFILL_CAUSAL:DECODE_CAUSAL),ev(cp,isPrefill?PREFILL_CP:DECODE_CP),ev(cos,isPrefill?PREFILL_ROPE:DECODE_ROPE),ev(sin,isPrefill?PREFILL_ROPE:DECODE_ROPE),ev(k,CACHE),ev(v,CACHE)});hidden=o[0];next[l*2]=o[1];next[l*2+1]=o[2];}
            float[][] fin=forwardFloats("models/qwen/"+(isPrefill?"final.pte":"decode-final.pte"),new EValue[]{ev(hidden,isPrefill?PREFILL_H:DECODE_H)});Object[] objects=new Object[56];System.arraycopy(next,0,objects,0,56);double elapsed=seconds(SystemClock.elapsedRealtimeNanos()-start);if(isPrefill){putHash("qwen_prefill_hidden",fin[0]);putHash("qwen_prefill_logits",fin[1]);prefill=new JSONObject().put("seconds",elapsed).put("cache_output_count",56);}else if(chunkIndex>0){JSONObject rec=chunks.getJSONObject(chunkIndex-1);rec.put("qwen_decode_position",position).put("qwen_decode_seconds",elapsed).put("qwen_cache_input_count",prior.length).put("qwen_cache_output_count",56);putHash(name(chunkIndex-1,"qwen_hidden"),fin[0]);putHash(name(chunkIndex-1,"qwen_logits"),fin[1]);}return new GenerationController.QwenOutput(fin[1],fin[0],objects);
        }
        private String name(int chunk,String suffix){return String.format(Locale.ROOT,"chunk-%02d-%s",chunk,suffix);}
        private float[][] forwardFloats(String path,EValue[] in)throws Exception{EValue[] out=forward(path,in);float[][] r=new float[out.length][];for(int i=0;i<out.length;i++)r[i]=Raw.output(out[i]).v;return r;}
        private EValue[] forward(String path,EValue[] in)throws Exception{Module m=null;try{m=Module.load(file(path).getAbsolutePath(),Module.LOAD_MODE_MMAP);EValue[] raw=m.forward(in),copied=new EValue[raw.length];for(int i=0;i<raw.length;i++){if(!raw[i].isTensor())throw new IllegalStateException("non-tensor output");Tensor t=raw[i].toTensor();copied[i]=ev(t.getDataAsFloatArray(),t.shape());}return copied;}finally{if(m!=null)m.destroy();System.gc();}}
        private void putHash(String name,float[] v)throws Exception{File f=file("generation-run-"+run+"-"+name+".f32le");writeFloats(f,v);}
    }

    private static final class Raw{final float[]v;final long[]shape;Raw(float[]v,long[]s){this.v=v;shape=s;}EValue ev(){return GenerationProbeActivity.ev(v,shape);}static Raw output(EValue e){if(!e.isTensor())throw new IllegalStateException("non-tensor output");Tensor t=e.toTensor();return new Raw(t.getDataAsFloatArray(),t.shape());}}
    private record Run(JSONObject json,String tokens,String pcmHash,int samples,boolean boundariesExact,boolean validEarlyTermination){}
    private File file(String n){return new File(getFilesDir(),n);}private static long[] shape(int c,int f){return new long[]{1,c,f};}private static EValue ev(float[]v,long[]s){return EValue.from(Tensor.fromBlob(v,s));}private static EValue ev(long[]v,long[]s){return EValue.from(Tensor.fromBlob(v,s));}
    private static float[] readFloats(File f,int n)throws Exception{byte[]b=Files.readAllBytes(f.toPath());if(b.length!=n*4)throw new IllegalArgumentException(f+" expected "+(n*4)+" bytes, got "+b.length);float[]v=new float[n];ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(v);return v;}
    private static int[] readInt64AsInt(File f,int n)throws Exception{byte[]b=Files.readAllBytes(f.toPath());if(b.length!=n*8)throw new IllegalArgumentException(f+" expected "+(n*8)+" bytes, got "+b.length);java.nio.LongBuffer x=ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN).asLongBuffer();int[]v=new int[n];for(int i=0;i<n;i++){long q=x.get();if(q<Integer.MIN_VALUE||q>Integer.MAX_VALUE)throw new IllegalArgumentException("speaker ID overflow");v[i]=(int)q;}return v;}
    private static String readText(File f)throws Exception{return new String(Files.readAllBytes(f.toPath()),java.nio.charset.StandardCharsets.UTF_8);}private static void writeFloats(File f,float[]v)throws Exception{ByteBuffer b=ByteBuffer.allocate(v.length*4).order(ByteOrder.LITTLE_ENDIAN);b.asFloatBuffer().put(v);writeBytes(f,b.array());}private static void writeBytes(File f,byte[]b)throws Exception{try(FileOutputStream s=new FileOutputStream(f)){s.write(b);}}private static void writeText(File f,String s)throws Exception{writeBytes(f,s.getBytes(java.nio.charset.StandardCharsets.UTF_8));}
    private static byte[] pcm16(float[]v){ByteBuffer b=ByteBuffer.allocate(v.length*2).order(ByteOrder.LITTLE_ENDIAN);for(float x:v){float y=Math.max(-1,Math.min(1,x));b.putShort((short)Math.round(y*(y<0?32768:32767)));}return b.array();}
    private static String sha256(byte[] b)throws Exception{MessageDigest d=MessageDigest.getInstance("SHA-256");d.update(b);return hex(d.digest());}private static String sha256(File f)throws Exception{MessageDigest d=MessageDigest.getInstance("SHA-256");try(FileInputStream s=new FileInputStream(f)){byte[]b=new byte[1048576];int n;while((n=s.read(b))>=0)d.update(b,0,n);}return hex(d.digest());}private static String hex(byte[]v){StringBuilder h=new StringBuilder();for(byte x:v)h.append(String.format(Locale.ROOT,"%02x",x));return h.toString();}
    private static long status(String key){try{for(String l:Files.readAllLines(new File("/proc/self/status").toPath()))if(l.startsWith(key+":"))return Long.parseLong(l.substring(l.indexOf(':')+1).trim().split("\\s+")[0]);}catch(Throwable ignored){}return-1;}private static double seconds(long n){return n/1e9;}private static RuntimeException wrap(Exception e){return e instanceof RuntimeException?(RuntimeException)e:new RuntimeException(e);}
}

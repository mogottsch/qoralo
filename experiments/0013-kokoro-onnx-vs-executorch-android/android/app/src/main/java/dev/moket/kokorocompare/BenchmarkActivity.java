package dev.moket.kokorocompare;

import ai.onnxruntime.*;
import android.app.Activity;
import android.os.Bundle;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.json.*;

/** Headless, filesystem-backed, CPU-only fixed-contract benchmark. It never plays audio. */
public final class BenchmarkActivity extends Activity {
    private static final int SAMPLE_RATE=24_000, RUNS=6;
    private static final String MODEL_SHA="d11a0dd7c4eb768e1f0ef03090c69b6761f55e37b9f196749349591c40be232b";
    private static final String VOICE_SHA="d583ccff3cdca2f7fae535cb998ac07e9fcb90f09737b9a41fa2734ec44a8f0b";
    private static final String TOKENS_SHA="6ebb6bb288f20f3ae8d004d3c2ca27697da27c037d75e81a60e2a6a663f95425";
    private static final String LEXICON_SHA="7daaab53a181be9885b853a8582bf1838186317e5dadacbcef9c426d6fa0da14";
    private static final String TEXT_SHA="bec8bf482f4d816f0c95471c289a2607a7a169e33389b8b13e525214ec639461";
    private static final String POLICY_SHA="22c7f2dd5c3596acf66107c3712c886b827f4a332d13dca981d183f6efc40ad7";
    private static final String TOKEN_VALUE_SHA="35ebb50fb1ba0cca3862c880cf0571c9a51623c5243a9f2307b4bb4a6dcd2078";
    private static final String STYLE_VALUE_SHA="b5c2627313e7e45bbb50470307ef66730b5510ebc7e92671cf7aad0449cdf899";
    private static final String DURATION_SHA="7977e82d5304abba333a0b1caa0f0ef39b265b11205ff217c5979255cc44b80e";

    @Override public void onCreate(Bundle state){super.onCreate(state);new Thread(this::execute,"kokoro-benchmark").start();}

    private void execute(){
        File external=getExternalFilesDir(null);String campaign=getIntent().getStringExtra("campaign_id");String route=getIntent().getStringExtra("route");File output=null;
        try{
            if(external==null)throw new IOException("external files directory unavailable");
            if(campaign==null||!campaign.matches("[A-Za-z0-9._-]+"))throw new IOException("invalid campaign id");
            if(!"onnx".equals(route))throw new IOException("only the host-eligible ONNX route is packaged");
            File input=new File(external,"input");output=new File(external,"results/"+campaign);if(output.exists())throw new IOException("campaign output already exists");if(!output.mkdirs())throw new IOException("cannot create output directory");
            JSONObject result=run(input,output,campaign);writeJsonAtomic(new File(output,"result.json"),result);
        }catch(Throwable failure){
            try{if(output==null&&external!=null&&campaign!=null){output=new File(external,"results/"+campaign);output.mkdirs();}if(output!=null)writeJsonAtomic(new File(output,"failure.json"),new JSONObject().put("status","failed").put("exception_type",failure.getClass().getName()).put("message",String.valueOf(failure.getMessage())));}catch(Exception ignored){}
        }finally{runOnUiThread(this::finishAndRemoveTask);}
    }

    private JSONObject run(File input,File output,String campaign)throws Exception{
        long benchmarkStart=System.nanoTime();double batteryStart=batteryTemperatureC();
        long verifyStart=System.nanoTime();
        Hashing.verifyRegularPinnedFile(input,"model.onnx",332_038_651L,MODEL_SHA);
        Hashing.verifyRegularPinnedFile(input,"af_heart.f32",522_240L,VOICE_SHA);
        Hashing.verifyRegularPinnedFile(input,"tokens.txt",687L,TOKENS_SHA);
        Hashing.verifyRegularPinnedFile(input,"lexicon-us-en.txt",5_956_885L,LEXICON_SHA);
        Hashing.verifyRegularPinnedFile(input,"transcript.txt",116L,TEXT_SHA);
        Hashing.verifyRegularPinnedFile(input,"deployment-fidelity-policy.json",6_965L,POLICY_SHA);
        long verifyNanos=System.nanoTime()-verifyStart;
        String text=new String(Files.readAllBytes(new File(input,"transcript.txt").toPath()),StandardCharsets.UTF_8);
        long frontendLoadStart=System.nanoTime();KokoroFrontend frontend=KokoroFrontend.load(new File(input,"tokens.txt"),new File(input,"lexicon-us-en.txt"),new File(input,"af_heart.f32"),text);long frontendLoadNanos=System.nanoTime()-frontendLoadStart;
        MemorySnapshot afterAssets=MemorySnapshot.read("after_verified_assets_and_frontend_load");

        long envStart=System.nanoTime();OrtEnvironment env=OrtEnvironment.getEnvironment(OrtLoggingLevel.ORT_LOGGING_LEVEL_WARNING,"kokoro-exp0013-cpu");long envNanos=System.nanoTime()-envStart;
        JSONArray runs=new JSONArray();float[] firstAudio=null;String profilePath;JSONObject inputInfo=new JSONObject(),outputInfo=new JSONObject();long sessionNanos;MemorySnapshot afterSession;
        try(OrtSession.SessionOptions options=new OrtSession.SessionOptions()){
            options.setIntraOpNumThreads(1);options.setInterOpNumThreads(1);options.setExecutionMode(OrtSession.SessionOptions.ExecutionMode.SEQUENTIAL);options.setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT);options.addCPU(true);options.enableProfiling(new File(output,"ort-profile").getAbsolutePath());
            long sessionStart=System.nanoTime();
            try(OrtSession session=env.createSession(new File(input,"model.onnx").getAbsolutePath(),options)){
                sessionNanos=System.nanoTime()-sessionStart;afterSession=MemorySnapshot.read("after_onnxruntime_session_creation");
                for(var entry:session.getInputInfo().entrySet())inputInfo.put(entry.getKey(),String.valueOf(entry.getValue().getInfo()));
                for(var entry:session.getOutputInfo().entrySet())outputInfo.put(entry.getKey(),String.valueOf(entry.getValue().getInfo()));
                for(int index=0;index<RUNS;index++){
                    long totalStart=System.nanoTime();long frontStart=System.nanoTime();KokoroFrontend.Result prepared=frontend.convert(text);String tokenHash=Hashing.littleEndianLongSha256(prepared.tokenIds());String styleHash=Hashing.littleEndianFloatSha256(prepared.style());if(!TOKEN_VALUE_SHA.equals(tokenHash)||!STYLE_VALUE_SHA.equals(styleHash))throw new IOException("runtime frontend tensor hash drift");long frontNanos=System.nanoTime()-frontStart;
                    long tensorStart=System.nanoTime();float[] speed={1.0f};float[] audio;long[] duration;
                    try(OnnxTensor tokensTensor=OnnxTensor.createTensor(env,new long[][]{prepared.tokenIds()});OnnxTensor styleTensor=OnnxTensor.createTensor(env,new float[][]{prepared.style()});OnnxTensor speedTensor=OnnxTensor.createTensor(env,speed)){
                        long tensorNanos=System.nanoTime()-tensorStart;Map<String,OnnxTensor> feed=Map.of("tokens",tokensTensor,"style",styleTensor,"speed",speedTensor);long inferenceStart=System.nanoTime();
                        try(OrtSession.Result values=session.run(feed)){
                            long inferenceNanos=System.nanoTime()-inferenceStart;long extractStart=System.nanoTime();audio=((float[])values.get("audio").orElseThrow().getValue()).clone();duration=((long[])values.get("pred_dur").orElseThrow().getValue()).clone();long extractNanos=System.nanoTime()-extractStart;
                            JSONObject validation=validate(audio,duration);String audioHash=Hashing.littleEndianFloatSha256(audio);long totalNanos=System.nanoTime()-totalStart;if(index==0)firstAudio=audio.clone();
                            runs.put(new JSONObject().put("index",index).put("state",index==0?"first":"warm").put("total_generation_nanos",totalNanos).put("frontend_nanos",frontNanos).put("tensor_creation_nanos",tensorNanos).put("inference_nanos",inferenceNanos).put("output_extraction_and_validation_nanos",extractNanos).put("rtf",totalNanos/1e9/(audio.length/(double)SAMPLE_RATE)).put("token_shape",new JSONArray(new int[]{1,prepared.tokenIds().length})).put("style_shape",new JSONArray(new int[]{1,prepared.style().length})).put("speed_shape",new JSONArray(new int[]{1})).put("audio_shape",new JSONArray(new int[]{audio.length})).put("duration_shape",new JSONArray(new int[]{duration.length})).put("token_sha256",tokenHash).put("style_sha256",styleHash).put("audio_float32_sha256",audioHash).put("duration_int64_sha256",Hashing.littleEndianLongSha256(duration)).put("validation",validation).put("memory",MemorySnapshot.read(index==0?"after_first_generation":"after_warm_generation_"+index).json()));
                        }
                    }
                }
                profilePath=session.endProfiling();
            }
        }
        if(firstAudio==null)throw new IOException("no audio produced");
        long wavStart=System.nanoTime();File wav=new File(output,"kokoro-af-heart-onnxruntime-cpu.wav");File raw=new File(output,"kokoro-af-heart-onnxruntime-cpu.f32");WavWriter.writePcm16Mono(wav,firstAudio,SAMPLE_RATE);WavWriter.writeFloat32(raw,firstAudio);long wavNanos=System.nanoTime()-wavStart;
        JSONArray warmTotals=new JSONArray();long[] warm=new long[RUNS-1];for(int i=1;i<RUNS;i++){warm[i-1]=runs.getJSONObject(i).getLong("total_generation_nanos");warmTotals.put(warm[i-1]);}Arrays.sort(warm);long median=warm[warm.length/2];
        return new JSONObject().put("schema_version",1).put("status","passed").put("campaign_id",campaign).put("route","exact_source_derived_fp32_onnxruntime_cpu_fixed_contract").put("claim_boundary","not waveform-identical official eager; not sherpa disable_complex graph; no arbitrary text; no accelerator").put("runtime",new JSONObject().put("onnxruntime_version",env.getVersion()).put("available_providers",OrtEnvironment.getAvailableProviders().toString()).put("configured_provider","explicit CPU via SessionOptions.addCPU(true)").put("threads",1).put("execution_mode","SEQUENTIAL").put("graph_optimization","ALL_OPT").put("qnn_configured",false)).put("asset_verification_nanos",verifyNanos).put("frontend_asset_load_nanos",frontendLoadNanos).put("ort_environment_init_nanos",envNanos).put("session_creation_nanos",sessionNanos).put("wav_and_float_encoding_nanos",wavNanos).put("input_info",inputInfo).put("output_info",outputInfo).put("runs",runs).put("warm_total_generation_nanos",warmTotals).put("warm_median_total_generation_nanos",median).put("warm_min_total_generation_nanos",warm[0]).put("warm_max_total_generation_nanos",warm[warm.length-1]).put("first_wav",new JSONObject().put("relative_path","results/"+campaign+"/"+wav.getName()).put("bytes",wav.length()).put("sha256",Hashing.fileSha256(wav))).put("first_float32",new JSONObject().put("relative_path","results/"+campaign+"/"+raw.getName()).put("bytes",raw.length()).put("sha256",Hashing.fileSha256(raw))).put("profile_path",profilePath).put("memory_after_assets",afterAssets.json()).put("memory_after_session",afterSession.json()).put("battery_temperature_c_start",jsonNumberOrNull(batteryStart)).put("battery_temperature_c_end",jsonNumberOrNull(batteryTemperatureC())).put("total_activity_nanos_before_result_write",System.nanoTime()-benchmarkStart);
    }

    private static JSONObject validate(float[] audio,long[] duration)throws Exception{
        if(audio.length!=182_400)throw new IOException("audio shape drift: "+audio.length);if(duration.length!=125)throw new IOException("duration shape drift: "+duration.length);long sum=0;for(long value:duration)sum+=value;if(sum!=304)throw new IOException("duration sum drift: "+sum);String hash=Hashing.littleEndianLongSha256(duration);if(!DURATION_SHA.equals(hash))throw new IOException("duration values drift");double sumSquares=0,peak=0;int nonFinite=0,clipped=0;for(float sample:audio){if(!Float.isFinite(sample)){nonFinite++;continue;}double a=Math.abs(sample);peak=Math.max(peak,a);sumSquares+=(double)sample*sample;if(a>=1.0)clipped++;}double rms=Math.sqrt(sumSquares/audio.length);if(nonFinite!=0||peak<0.0001||peak>=1.0||rms<0.00001||clipped!=0)throw new IOException("audio validity gate failed");return new JSONObject().put("all_finite",true).put("sample_count",audio.length).put("sample_rate_hz",SAMPLE_RATE).put("duration_seconds",audio.length/(double)SAMPLE_RATE).put("absolute_peak",peak).put("rms",rms).put("clipped_float_samples",clipped).put("pred_duration_sum",sum);
    }

    private static double batteryTemperatureC(){try{String value=new String(Files.readAllBytes(new File("/sys/class/power_supply/battery/temp").toPath()),StandardCharsets.US_ASCII).trim();return Double.parseDouble(value)/10.0;}catch(Exception ignored){return Double.NaN;}}
    private static Object jsonNumberOrNull(double value){return Double.isFinite(value)?value:JSONObject.NULL;}
    private static void writeJsonAtomic(File target,JSONObject value)throws Exception{target.getParentFile().mkdirs();File temporary=new File(target.getParentFile(),target.getName()+".tmp");Files.write(temporary.toPath(),(value.toString(2)+"\n").getBytes(StandardCharsets.UTF_8),StandardOpenOption.CREATE_NEW);try{Files.move(temporary.toPath(),target.toPath(),StandardCopyOption.ATOMIC_MOVE);}catch(AtomicMoveNotSupportedException e){Files.move(temporary.toPath(),target.toPath());}}
}

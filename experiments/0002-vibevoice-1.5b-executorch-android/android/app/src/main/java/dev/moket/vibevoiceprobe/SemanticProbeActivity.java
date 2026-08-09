package dev.moket.vibevoiceprobe;

import android.app.Activity;
import android.os.Bundle;
import android.os.Debug;
import android.os.SystemClock;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;
import org.pytorch.executorch.DType;
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

/** Executes first -> device caches -> cached semantic encoding, followed by the accepted connector. */
public final class SemanticProbeActivity extends Activity {
    private static final String TAG = "VibeVoiceSemantic";
    private static final int RUN_COUNT = 2;
    private static final long[] AUDIO_SHAPE = {1, 1, 3200};
    private static final long[] ACOUSTIC_SHAPE = {1, 1, 64};
    private static final long[] FEATURE_SHAPE = {1, 1, 128};
    private static final long[] EMBEDDING_SHAPE = {1, 1, 1536};
    private static final long[][] CACHE_SHAPES = {
            {1,1,6}, {1,32,2}, {1,64,2}, {1,128,4}, {1,256,5}, {1,512,5},
            {1,1024,8}, {1,2048,6}, {1,32,6}, {1,32,6}, {1,32,6}, {1,64,6},
            {1,64,6}, {1,64,6}, {1,128,6}, {1,128,6}, {1,128,6}, {1,256,6},
            {1,256,6}, {1,256,6}, {1,512,6}, {1,512,6}, {1,512,6}, {1,1024,6},
            {1,1024,6}, {1,1024,6}, {1,2048,6}, {1,2048,6}, {1,2048,6},
            {1,2048,6}, {1,2048,6}, {1,2048,6}, {1,2048,6}, {1,2048,6}
    };

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        new Thread(this::runProbe, "semantic-probe").start();
    }

    private void runProbe() {
        File resultFile = new File(getFilesDir(), "semantic-result.json");
        try {
            Files.deleteIfExists(resultFile.toPath());
            File modelRoot = new File(getFilesDir(), "semantic-models");
            File inputRoot = new File(getFilesDir(), "semantic-input");
            File firstModel = requireFile(modelRoot, "semantic-encoder-first-xnnpack.pte");
            File cachedModel = requireFile(modelRoot, "semantic-encoder-cached-xnnpack.pte");
            File connectorModel = requireFile(modelRoot, "connectors-xnnpack.pte");
            RawTensor[] audio = {
                    readTensor(new File(inputRoot, "call-0-audio.f32le"), AUDIO_SHAPE),
                    readTensor(new File(inputRoot, "call-1-audio.f32le"), AUDIO_SHAPE)
            };
            RawTensor acoustic = readTensor(new File(inputRoot, "acoustic.f32le"), ACOUSTIC_SHAPE);
            long rssBefore = readStatusKiB("VmRSS");
            long hwmBefore = readStatusKiB("VmHWM");
            long pssBefore = Debug.getPss();
            JSONArray runs = new JSONArray();
            for (int run = 0; run < RUN_COUNT; run++) {
                JSONObject runJson = executeRun(run, firstModel, cachedModel, connectorModel, audio, acoustic);
                runs.put(runJson);
                System.gc();
            }
            JSONObject memory = new JSONObject();
            memory.put("rss_before", rssBefore);
            memory.put("rss_after", readStatusKiB("VmRSS"));
            memory.put("pss_before", pssBefore);
            memory.put("pss_after", Debug.getPss());
            memory.put("process_hwm_before", hwmBefore);
            memory.put("process_hwm_peak", readStatusKiB("VmHWM"));
            JSONObject artifacts = new JSONObject();
            artifacts.put("semantic_first", artifact(firstModel));
            artifacts.put("semantic_cached", artifact(cachedModel));
            artifacts.put("connector", artifact(connectorModel));
            JSONObject result = new JSONObject();
            result.put("schema_version", 1);
            result.put("status", "passed");
            result.put("call_count", 2);
            result.put("run_count", RUN_COUNT);
            result.put("cache_tensor_count", CACHE_SHAPES.length);
            result.put("cache_transport", "call 2 receives the in-memory Tensor data produced by device call 1; no host cache is read");
            result.put("runs", runs);
            result.put("memory_kib", memory);
            result.put("artifacts", artifacts);
            writeText(resultFile, result.toString(2) + "\n");
            Log.i(TAG, "RESULT " + result);
        } catch (Throwable error) {
            StringWriter trace = new StringWriter();
            error.printStackTrace(new PrintWriter(trace));
            try {
                JSONObject result = new JSONObject();
                result.put("schema_version", 1);
                result.put("status", "failed");
                result.put("error_type", error.getClass().getName());
                result.put("error", String.valueOf(error.getMessage()));
                result.put("trace", trace.toString());
                writeText(resultFile, result.toString(2) + "\n");
            } catch (Throwable writeError) {
                Log.e(TAG, "Could not write failure result", writeError);
            }
            Log.e(TAG, "Semantic probe failed", error);
        } finally {
            runOnUiThread(this::finish);
        }
    }

    private JSONObject executeRun(int run, File firstModel, File cachedModel, File connectorModel,
                                  RawTensor[] audio, RawTensor acoustic) throws Exception {
        JSONObject runJson = new JSONObject();
        runJson.put("run", run);
        runJson.put("temperature", run == 0 ? "cold" : "warm_page_cache");
        RawTensor[] caches = null;
        for (int call = 0; call < 2; call++) {
            File model = call == 0 ? firstModel : cachedModel;
            List<EValue> inputs = new ArrayList<>();
            inputs.add(audio[call].toEValue());
            if (call == 1) {
                if (caches == null || caches.length != 34) throw new IllegalStateException("Missing call-one caches");
                for (RawTensor cache : caches) inputs.add(cache.toEValue());
            }
            TimedOutputs semantic = forward(model, inputs);
            if (semantic.outputs.length != 35) throw new IllegalStateException("Expected 35 semantic outputs");
            RawTensor features = output(semantic.outputs[0], FEATURE_SHAPE, "features");
            RawTensor[] nextCaches = new RawTensor[34];
            JSONArray cacheHashes = new JSONArray();
            for (int index = 0; index < 34; index++) {
                nextCaches[index] = output(semantic.outputs[index + 1], CACHE_SHAPES[index], "cache " + index);
                File cacheFile = outputFile(run, call, String.format(Locale.ROOT, "cache-%02d", index));
                writeTensor(cacheFile, nextCaches[index]);
                cacheHashes.put(sha256(cacheFile));
            }
            caches = nextCaches;
            File featureFile = outputFile(run, call, "features");
            writeTensor(featureFile, features);
            List<EValue> connectorInputs = new ArrayList<>();
            connectorInputs.add(acoustic.toEValue());
            connectorInputs.add(features.toEValue());
            TimedOutputs connector = forward(connectorModel, connectorInputs);
            if (connector.outputs.length != 1) throw new IllegalStateException("Expected one connector output");
            RawTensor embedding = output(connector.outputs[0], EMBEDDING_SHAPE, "embedding");
            File embeddingFile = outputFile(run, call, "embedding");
            writeTensor(embeddingFile, embedding);
            JSONObject callJson = new JSONObject();
            callJson.put("call", call);
            callJson.put("entry", call == 0 ? "first" : "cached");
            callJson.put("input_count", inputs.size());
            callJson.put("semantic_load_seconds", semantic.loadSeconds);
            callJson.put("semantic_inference_seconds", semantic.inferenceSeconds);
            callJson.put("connector_load_seconds", connector.loadSeconds);
            callJson.put("connector_inference_seconds", connector.inferenceSeconds);
            callJson.put("features_sha256", sha256(featureFile));
            callJson.put("cache_sha256", cacheHashes);
            callJson.put("embedding_sha256", sha256(embeddingFile));
            callJson.put("rss_kib", readStatusKiB("VmRSS"));
            callJson.put("pss_kib", Debug.getPss());
            callJson.put("process_hwm_kib", readStatusKiB("VmHWM"));
            runJson.put("call_" + call, callJson);
        }
        return runJson;
    }

    private TimedOutputs forward(File model, List<EValue> inputs) throws Exception {
        Module module = null;
        long loadStart = SystemClock.elapsedRealtimeNanos();
        try {
            module = Module.load(model.getAbsolutePath(), Module.LOAD_MODE_MMAP);
            long loadNanos = SystemClock.elapsedRealtimeNanos() - loadStart;
            long inferenceStart = SystemClock.elapsedRealtimeNanos();
            EValue[] outputs = module.forward(inputs.toArray(new EValue[0]));
            long inferenceNanos = SystemClock.elapsedRealtimeNanos() - inferenceStart;
            return new TimedOutputs(outputs, seconds(loadNanos), seconds(inferenceNanos));
        } finally {
            if (module != null) module.destroy();
        }
    }

    private File outputFile(int run, int call, String kind) {
        return new File(getFilesDir(), "run-" + run + "-call-" + call + "-" + kind + ".f32le");
    }

    private static RawTensor output(EValue value, long[] shape, String label) {
        if (!value.isTensor()) throw new IllegalStateException(label + " is not a tensor");
        Tensor tensor = value.toTensor();
        if (tensor.dtype() != DType.FLOAT) throw new IllegalStateException(label + " is not float32");
        assertShape(tensor.shape(), shape, label);
        return new RawTensor(tensor.getDataAsFloatArray(), shape);
    }

    private static File requireFile(File root, String name) {
        File file = new File(root, name);
        if (!file.isFile() || file.length() == 0) throw new IllegalStateException("Missing " + file);
        return file;
    }

    private static RawTensor readTensor(File file, long[] shape) throws Exception {
        byte[] bytes;
        try (FileInputStream stream = new FileInputStream(file)) { bytes = stream.readAllBytes(); }
        int count = numel(shape);
        if (bytes.length != count * Float.BYTES) throw new IllegalArgumentException("Wrong byte count for " + file);
        float[] values = new float[count];
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(values);
        return new RawTensor(values, shape);
    }

    private static void writeTensor(File file, RawTensor tensor) throws Exception {
        ByteBuffer bytes = ByteBuffer.allocate(tensor.values.length * Float.BYTES).order(ByteOrder.LITTLE_ENDIAN);
        bytes.asFloatBuffer().put(tensor.values);
        try (FileOutputStream stream = new FileOutputStream(file)) { stream.write(bytes.array()); }
    }

    private static JSONObject artifact(File file) throws Exception {
        JSONObject result = new JSONObject();
        result.put("path", file.getName()); result.put("bytes", file.length()); result.put("sha256", sha256(file));
        return result;
    }

    private static int numel(long[] shape) {
        long count = 1; for (long value : shape) count *= value;
        if (count > Integer.MAX_VALUE) throw new IllegalArgumentException("Tensor too large");
        return (int) count;
    }

    private static void assertShape(long[] actual, long[] expected, String label) {
        if (actual.length != expected.length) throw new IllegalStateException(label + " rank mismatch");
        for (int i = 0; i < actual.length; i++) if (actual[i] != expected[i]) throw new IllegalStateException(label + " shape mismatch");
    }

    private static long readStatusKiB(String field) {
        try {
            for (String line : Files.readAllLines(new File("/proc/self/status").toPath()))
                if (line.startsWith(field + ":")) return Long.parseLong(line.substring(line.indexOf(':') + 1).trim().split("\\s+")[0]);
        } catch (Throwable ignored) { }
        return -1;
    }

    private static String sha256(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (FileInputStream stream = new FileInputStream(file)) {
            byte[] chunk = new byte[1024 * 1024]; int read;
            while ((read = stream.read(chunk)) >= 0) digest.update(chunk, 0, read);
        }
        StringBuilder result = new StringBuilder();
        for (byte value : digest.digest()) result.append(String.format(Locale.ROOT, "%02x", value));
        return result.toString();
    }

    private static void writeText(File file, String text) throws Exception {
        try (FileOutputStream stream = new FileOutputStream(file)) { stream.write(text.getBytes(java.nio.charset.StandardCharsets.UTF_8)); }
    }
    private static double seconds(long nanos) { return nanos / 1_000_000_000.0; }

    private static final class RawTensor {
        final float[] values; final long[] shape;
        RawTensor(float[] values, long[] shape) { this.values = values; this.shape = shape; }
        EValue toEValue() { return EValue.from(Tensor.fromBlob(values, shape)); }
    }
    private static final class TimedOutputs {
        final EValue[] outputs; final double loadSeconds; final double inferenceSeconds;
        TimedOutputs(EValue[] outputs, double loadSeconds, double inferenceSeconds) {
            this.outputs = outputs; this.loadSeconds = loadSeconds; this.inferenceSeconds = inferenceSeconds;
        }
    }
}

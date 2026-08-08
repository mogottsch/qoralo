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

/** Runs two cold/warm repetitions of call 0 -> actual device caches -> call 1. */
public final class StreamingProbeActivity extends Activity {
    private static final String TAG = "VibeVoiceStreaming";
    private static final File MODEL_ROOT = new File("/data/local/tmp/vibevoice-streaming-decoder");
    private static final long[] LATENT_SHAPE = {1, 64, 1};
    private static final int RUN_COUNT = 2;
    private static final long[][][] FIRST_CACHE_SHAPES = {
            {shape(2048, 6), shape(2048, 6), shape(2048, 6), shape(2048, 6),
                    shape(2048, 6), shape(2048, 6), shape(2048, 6), shape(2048, 6), shape(64, 6)},
            {shape(1024, 6), shape(1024, 6), shape(1024, 6), shape(2048, 1)},
            {shape(512, 6), shape(512, 6), shape(512, 6), shape(1024, 8)},
            {shape(256, 6), shape(256, 6), shape(256, 6), shape(512, 9)},
            {shape(128, 6), shape(128, 6), shape(128, 6), shape(256, 7)},
            {shape(64, 6), shape(64, 6), shape(64, 6), shape(128, 3)},
            {shape(32, 6), shape(32, 6), shape(32, 6), shape(64, 3)},
            {shape(32, 6)}
    };
    private static final long[][][] CACHED_CACHE_SHAPES = {
            FIRST_CACHE_SHAPES[0],
            {shape(1024, 6), shape(1024, 6), shape(1024, 6), shape(2048, 2)},
            {shape(512, 6), shape(512, 6), shape(512, 6), shape(1024, 9)},
            FIRST_CACHE_SHAPES[3], FIRST_CACHE_SHAPES[4], FIRST_CACHE_SHAPES[5],
            FIRST_CACHE_SHAPES[6], FIRST_CACHE_SHAPES[7]
    };

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        new Thread(this::runProbe, "vibevoice-streaming-probe").start();
    }

    private void runProbe() {
        File resultFile = new File(getFilesDir(), "streaming-result.json");
        File outputRoot = new File(getFilesDir(), "streaming-output");
        try {
            Files.deleteIfExists(resultFile.toPath());
            deleteRecursively(outputRoot);
            if (!outputRoot.mkdirs()) throw new IllegalStateException("Could not create " + outputRoot);
            requireModels();

            File inputRoot = new File(getFilesDir(), "streaming-input");
            FloatTensor call0Input = readTensor(new File(inputRoot, "call-0.f32le"), LATENT_SHAPE);
            FloatTensor call1Input = readTensor(new File(inputRoot, "call-1.f32le"), LATENT_SHAPE);
            long rssBeforeKiB = readStatusKiB("VmRSS");
            long hwmBeforeKiB = readStatusKiB("VmHWM");
            long pssBeforeKiB = Debug.getPss();
            JSONArray runs = new JSONArray();
            for (int run = 0; run < RUN_COUNT; run++) {
                File runRoot = new File(outputRoot, "run-" + run);
                if (!runRoot.mkdirs()) throw new IllegalStateException("Could not create " + runRoot);
                JSONObject runJson = new JSONObject();
                runJson.put("run", run);
                runJson.put("temperature", run == 0 ? "cold" : "warm_page_cache");
                JSONObject first = executeCall("first", 0, call0Input, null, runRoot);
                JSONObject cached = executeCall("cached", 1, call1Input, runRoot, runRoot);
                runJson.put("call_0", first);
                runJson.put("call_1", cached);
                runJson.put("total_load_seconds", first.getDouble("total_load_seconds") + cached.getDouble("total_load_seconds"));
                runJson.put("total_inference_seconds", first.getDouble("total_inference_seconds") + cached.getDouble("total_inference_seconds"));
                runs.put(runJson);
            }

            JSONObject memory = new JSONObject();
            memory.put("rss_before", rssBeforeKiB);
            memory.put("rss_after", readStatusKiB("VmRSS"));
            memory.put("process_hwm_before", hwmBeforeKiB);
            memory.put("process_hwm_peak", readStatusKiB("VmHWM"));
            memory.put("pss_before", pssBeforeKiB);
            memory.put("pss_after", Debug.getPss());

            JSONObject result = new JSONObject();
            result.put("schema_version", 1);
            result.put("status", "passed");
            result.put("segment_count", 8);
            result.put("cache_tensor_count", 34);
            result.put("run_count", RUN_COUNT);
            result.put("load_mode", "mmap");
            result.put("model_root", MODEL_ROOT.getAbsolutePath());
            result.put("cache_transport", "device-produced call-0 tensors serialized in app-private storage and reloaded for call 1");
            result.put("module_lifetime", "one segment resident at a time; destroy after output extraction");
            result.put("runs", runs);
            result.put("memory_kib", memory);
            writeText(resultFile, result.toString(2) + "\n");
            Log.i(TAG, "RESULT " + result.toString());
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
            Log.e(TAG, "Streaming probe failed", error);
        } finally {
            runOnUiThread(this::finish);
        }
    }

    private JSONObject executeCall(
            String entry, int call, FloatTensor latent, File cacheInputRoot, File outputRoot
    ) throws Exception {
        FloatTensor activation = latent;
        JSONArray segments = new JSONArray();
        double totalLoadSeconds = 0.0;
        double totalInferenceSeconds = 0.0;
        for (int segment = 0; segment < 8; segment++) {
            File modelFile = new File(new File(MODEL_ROOT, entry), "segment-" + segment + ".pte");
            List<EValue> inputValues = new ArrayList<>();
            inputValues.add(EValue.from(Tensor.fromBlob(activation.values, activation.shape)));
            if (call == 1) {
                for (int cache = 0; cache < FIRST_CACHE_SHAPES[segment].length; cache++) {
                    File cacheFile = cacheFile(cacheInputRoot, 0, segment, cache);
                    FloatTensor value = readTensor(cacheFile, FIRST_CACHE_SHAPES[segment][cache]);
                    inputValues.add(EValue.from(Tensor.fromBlob(value.values, value.shape)));
                }
            }

            long rssBeforeKiB = readStatusKiB("VmRSS");
            long pssBeforeKiB = Debug.getPss();
            Module module = null;
            long loadStarted = SystemClock.elapsedRealtimeNanos();
            try {
                module = Module.load(modelFile.getAbsolutePath(), Module.LOAD_MODE_MMAP);
                long loadNanos = SystemClock.elapsedRealtimeNanos() - loadStarted;
                long inferenceStarted = SystemClock.elapsedRealtimeNanos();
                EValue[] outputs = module.forward(inputValues.toArray(new EValue[0]));
                long inferenceNanos = SystemClock.elapsedRealtimeNanos() - inferenceStarted;
                long[][] outputCacheShapes = call == 0
                        ? FIRST_CACHE_SHAPES[segment] : CACHED_CACHE_SHAPES[segment];
                int expectedOutputs = 1 + outputCacheShapes.length;
                if (outputs.length != expectedOutputs) {
                    throw new IllegalStateException(entry + " segment " + segment + ": expected "
                            + expectedOutputs + " outputs, got " + outputs.length);
                }
                for (EValue output : outputs) {
                    if (!output.isTensor()) throw new IllegalStateException("Non-tensor output");
                }
                Tensor activationTensor = outputs[0].toTensor();
                activation = new FloatTensor(
                        activationTensor.getDataAsFloatArray(), activationTensor.shape());
                for (int cache = 0; cache < outputCacheShapes.length; cache++) {
                    Tensor cacheTensor = outputs[cache + 1].toTensor();
                    assertShape(cacheTensor.shape(), outputCacheShapes[cache],
                            entry + " segment " + segment + " cache " + cache);
                    writeFloat32(cacheFile(outputRoot, call, segment, cache),
                            cacheTensor.getDataAsFloatArray());
                }
                double loadSeconds = seconds(loadNanos);
                double inferenceSeconds = seconds(inferenceNanos);
                totalLoadSeconds += loadSeconds;
                totalInferenceSeconds += inferenceSeconds;
                JSONObject record = new JSONObject();
                record.put("segment", segment);
                record.put("model_bytes", modelFile.length());
                record.put("input_count", inputValues.size());
                record.put("output_count", outputs.length);
                record.put("activation_shape", longArrayJson(activation.shape));
                record.put("load_seconds", loadSeconds);
                record.put("inference_seconds", inferenceSeconds);
                record.put("rss_before_kib", rssBeforeKiB);
                record.put("rss_after_inference_kib", readStatusKiB("VmRSS"));
                record.put("pss_before_kib", pssBeforeKiB);
                record.put("pss_after_inference_kib", Debug.getPss());
                record.put("process_hwm_kib", readStatusKiB("VmHWM"));
                segments.put(record);
            } finally {
                if (module != null) module.destroy();
            }
            System.gc();
        }
        File pcmFile = new File(outputRoot, "call-" + call + "-pcm.f32le");
        writeFloat32(pcmFile, activation.values);
        JSONObject result = new JSONObject();
        result.put("entry", entry);
        result.put("segments", segments);
        result.put("total_load_seconds", totalLoadSeconds);
        result.put("total_inference_seconds", totalInferenceSeconds);
        result.put("pcm_shape", longArrayJson(activation.shape));
        result.put("pcm_sha256", sha256(pcmFile));
        return result;
    }

    private static File cacheFile(File root, int call, int segment, int cache) {
        return new File(root, "call-" + call + "-segment-" + segment + "-cache-" + cache + ".f32le");
    }

    private static void requireModels() {
        for (String entry : new String[]{"first", "cached"}) {
            for (int segment = 0; segment < 8; segment++) {
                File file = new File(new File(MODEL_ROOT, entry), "segment-" + segment + ".pte");
                if (!file.isFile() || file.length() == 0) {
                    throw new IllegalStateException("Missing model " + file);
                }
            }
        }
    }

    private static long[] shape(int channels, int frames) {
        return new long[]{1, channels, frames};
    }

    private static int numel(long[] shape) {
        long result = 1;
        for (long value : shape) result *= value;
        if (result > Integer.MAX_VALUE) throw new IllegalArgumentException("Tensor too large");
        return (int) result;
    }

    private static FloatTensor readTensor(File file, long[] shape) throws Exception {
        byte[] bytes;
        try (FileInputStream stream = new FileInputStream(file)) {
            bytes = stream.readAllBytes();
        }
        int count = numel(shape);
        if (bytes.length != count * Float.BYTES) {
            throw new IllegalArgumentException("Expected " + (count * Float.BYTES)
                    + " bytes for " + file + ", got " + bytes.length);
        }
        float[] values = new float[count];
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(values);
        return new FloatTensor(values, shape);
    }

    private static void writeFloat32(File file, float[] values) throws Exception {
        ByteBuffer buffer = ByteBuffer.allocate(values.length * Float.BYTES).order(ByteOrder.LITTLE_ENDIAN);
        buffer.asFloatBuffer().put(values);
        try (FileOutputStream stream = new FileOutputStream(file)) {
            stream.write(buffer.array());
        }
    }

    private static void assertShape(long[] actual, long[] expected, String label) {
        if (actual.length != expected.length) throw new IllegalStateException(label + ": rank mismatch");
        for (int index = 0; index < actual.length; index++) {
            if (actual[index] != expected[index]) {
                throw new IllegalStateException(label + ": shape mismatch");
            }
        }
    }

    private static void deleteRecursively(File file) throws Exception {
        if (!file.exists()) return;
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) for (File child : children) deleteRecursively(child);
        }
        if (!file.delete()) throw new IllegalStateException("Could not delete " + file);
    }

    private static void writeText(File file, String value) throws Exception {
        try (FileOutputStream stream = new FileOutputStream(file)) {
            stream.write(value.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }
    }

    private static long readStatusKiB(String field) {
        try {
            for (String line : Files.readAllLines(new File("/proc/self/status").toPath())) {
                if (line.startsWith(field + ":")) {
                    return Long.parseLong(line.substring(line.indexOf(':') + 1).trim().split("\\s+")[0]);
                }
            }
        } catch (Throwable ignored) {
            // A missing diagnostic must not invalidate inference.
        }
        return -1;
    }

    private static String sha256(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (FileInputStream stream = new FileInputStream(file)) {
            byte[] chunk = new byte[8192];
            int read;
            while ((read = stream.read(chunk)) >= 0) digest.update(chunk, 0, read);
        }
        StringBuilder hex = new StringBuilder();
        for (byte value : digest.digest()) hex.append(String.format(Locale.ROOT, "%02x", value));
        return hex.toString();
    }

    private static JSONArray longArrayJson(long[] values) {
        JSONArray result = new JSONArray();
        for (long value : values) result.put(value);
        return result;
    }

    private static double seconds(long nanos) {
        return nanos / 1_000_000_000.0;
    }

    private static final class FloatTensor {
        final float[] values;
        final long[] shape;

        FloatTensor(float[] values, long[] shape) {
            this.values = values;
            this.shape = shape;
        }
    }
}

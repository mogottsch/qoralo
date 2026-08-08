package dev.moket.vibevoiceprobe;

import android.app.Activity;
import android.os.Bundle;
import android.os.Debug;
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

public final class ProbeActivity extends Activity {
    private static final String TAG = "VibeVoiceProbe";
    private static final String MODEL_NAME = "decoder.pte";
    private static final String INPUT_NAME = "input.f32le";
    private static final String OUTPUT_NAME = "output.f32le";
    private static final String RESULT_NAME = "result.json";
    private static final long[] INPUT_SHAPE = {1, 64, 1};

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        new Thread(this::runProbe, "vibevoice-probe").start();
    }

    private void runProbe() {
        Module module = null;
        File resultFile = new File(getFilesDir(), RESULT_NAME);
        try {
            Files.deleteIfExists(resultFile.toPath());
            Files.deleteIfExists(new File(getFilesDir(), OUTPUT_NAME).toPath());
            File modelFile = new File(getFilesDir(), MODEL_NAME);
            File inputFile = new File(getFilesDir(), INPUT_NAME);
            float[] input = readFloat32(inputFile, 64);

            long rssBeforeKiB = readStatusKiB("VmRSS");
            long hwmBeforeKiB = readStatusKiB("VmHWM");
            long pssBeforeKiB = Debug.getPss();

            long loadStarted = SystemClock.elapsedRealtimeNanos();
            module = Module.load(modelFile.getAbsolutePath(), Module.LOAD_MODE_MMAP);
            long loadNanos = SystemClock.elapsedRealtimeNanos() - loadStarted;

            long rssAfterLoadKiB = readStatusKiB("VmRSS");
            long hwmAfterLoadKiB = readStatusKiB("VmHWM");
            long pssAfterLoadKiB = Debug.getPss();

            Tensor inputTensor = Tensor.fromBlob(input, INPUT_SHAPE);
            long inferenceStarted = SystemClock.elapsedRealtimeNanos();
            EValue[] values = module.forward(EValue.from(inputTensor));
            long inferenceNanos = SystemClock.elapsedRealtimeNanos() - inferenceStarted;
            if (values.length != 1 || !values[0].isTensor()) {
                throw new IllegalStateException("Expected exactly one tensor output");
            }
            Tensor outputTensor = values[0].toTensor();
            float[] output = outputTensor.getDataAsFloatArray();
            File outputFile = new File(getFilesDir(), OUTPUT_NAME);
            writeFloat32(outputFile, output);

            long rssAfterInferenceKiB = readStatusKiB("VmRSS");
            long hwmAfterInferenceKiB = readStatusKiB("VmHWM");
            long pssAfterInferenceKiB = Debug.getPss();
            long peakHwmKiB = Math.max(hwmBeforeKiB, Math.max(hwmAfterLoadKiB, hwmAfterInferenceKiB));
            long peakObservedPssKiB = Math.max(pssBeforeKiB, Math.max(pssAfterLoadKiB, pssAfterInferenceKiB));

            String json = "{\n" +
                    "  \"schema_version\": 1,\n" +
                    "  \"status\": \"passed\",\n" +
                    "  \"model_bytes\": " + modelFile.length() + ",\n" +
                    "  \"load_mode\": \"mmap\",\n" +
                    "  \"load_seconds\": " + seconds(loadNanos) + ",\n" +
                    "  \"inference_seconds\": " + seconds(inferenceNanos) + ",\n" +
                    "  \"input_shape\": [1, 64, 1],\n" +
                    "  \"output_shape\": " + longArrayJson(outputTensor.shape()) + ",\n" +
                    "  \"output_numel\": " + output.length + ",\n" +
                    "  \"output_sha256\": \"" + sha256(outputFile) + "\",\n" +
                    "  \"memory_kib\": {\n" +
                    "    \"rss_before\": " + rssBeforeKiB + ",\n" +
                    "    \"rss_after_load\": " + rssAfterLoadKiB + ",\n" +
                    "    \"rss_after_inference\": " + rssAfterInferenceKiB + ",\n" +
                    "    \"process_hwm_peak\": " + peakHwmKiB + ",\n" +
                    "    \"pss_before\": " + pssBeforeKiB + ",\n" +
                    "    \"pss_after_load\": " + pssAfterLoadKiB + ",\n" +
                    "    \"pss_after_inference\": " + pssAfterInferenceKiB + ",\n" +
                    "    \"pss_peak_observed\": " + peakObservedPssKiB + "\n" +
                    "  }\n" +
                    "}\n";
            writeText(resultFile, json);
            Log.i(TAG, "RESULT " + json.replace('\n', ' '));
        } catch (Throwable error) {
            StringWriter trace = new StringWriter();
            error.printStackTrace(new PrintWriter(trace));
            String json = "{\n  \"schema_version\": 1,\n  \"status\": \"failed\",\n" +
                    "  \"error_type\": \"" + escape(error.getClass().getName()) + "\",\n" +
                    "  \"error\": \"" + escape(String.valueOf(error.getMessage())) + "\",\n" +
                    "  \"trace\": \"" + escape(trace.toString()) + "\"\n}\n";
            try {
                writeText(resultFile, json);
            } catch (Throwable writeError) {
                Log.e(TAG, "Could not write failure result", writeError);
            }
            Log.e(TAG, "Probe failed", error);
        } finally {
            if (module != null) {
                module.destroy();
            }
            runOnUiThread(this::finish);
        }
    }

    private static float[] readFloat32(File file, int count) throws Exception {
        byte[] bytes;
        try (FileInputStream stream = new FileInputStream(file)) {
            bytes = stream.readAllBytes();
        }
        if (bytes.length != count * Float.BYTES) {
            throw new IllegalArgumentException("Expected " + (count * Float.BYTES) + " input bytes, got " + bytes.length);
        }
        ByteBuffer buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
        float[] values = new float[count];
        buffer.asFloatBuffer().get(values);
        return values;
    }

    private static void writeFloat32(File file, float[] values) throws Exception {
        ByteBuffer buffer = ByteBuffer.allocate(values.length * Float.BYTES).order(ByteOrder.LITTLE_ENDIAN);
        buffer.asFloatBuffer().put(values);
        try (FileOutputStream stream = new FileOutputStream(file)) {
            stream.write(buffer.array());
        }
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
            while ((read = stream.read(chunk)) >= 0) {
                digest.update(chunk, 0, read);
            }
        }
        StringBuilder hex = new StringBuilder();
        for (byte value : digest.digest()) {
            hex.append(String.format(Locale.ROOT, "%02x", value));
        }
        return hex.toString();
    }

    private static String longArrayJson(long[] values) {
        StringBuilder result = new StringBuilder("[");
        for (int index = 0; index < values.length; index++) {
            if (index > 0) result.append(", ");
            result.append(values[index]);
        }
        return result.append(']').toString();
    }

    private static double seconds(long nanos) {
        return nanos / 1_000_000_000.0;
    }

    private static String escape(String value) {
        return value.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}

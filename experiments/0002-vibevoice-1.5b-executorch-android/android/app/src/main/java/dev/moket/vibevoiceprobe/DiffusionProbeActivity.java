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

/** Runs the real diffusion PTE and keeps DPM scheduler orchestration outside the graph. */
public final class DiffusionProbeActivity extends Activity {
    private static final String TAG = "VibeVoiceDiffusion";
    private static final long[] LATENT_SHAPE = {1, 64};
    private static final long[] CONDITION_SHAPE = {1, 1536};

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        new Thread(this::runProbe, "vibevoice-diffusion").start();
    }

    private void runProbe() {
        Module module = null;
        File resultFile = file("diffusion-result.json");
        try {
            Files.deleteIfExists(resultFile.toPath());
            Files.deleteIfExists(file("one-step-output.f32le").toPath());
            Files.deleteIfExists(file("loop-output.f32le").toPath());
            float[] initial = readFloat32(file("latent.f32le"), 64);
            float[] positive = readFloat32(file("positive-condition.f32le"), 1536);
            float[] negative = readFloat32(file("negative-condition.f32le"), 1536);
            float[] timesteps = readFloat32(file("timesteps.f32le"), 10);
            float[] sigmas = readFloat32(file("sigmas.f32le"), 11);

            long rssBefore = readStatusKiB("VmRSS");
            long hwmBefore = readStatusKiB("VmHWM");
            long pssBefore = Debug.getPss();
            long loadStarted = SystemClock.elapsedRealtimeNanos();
            module = Module.load(file("diffusion.pte").getAbsolutePath(), Module.LOAD_MODE_MMAP);
            long loadNanos = SystemClock.elapsedRealtimeNanos() - loadStarted;
            long rssAfterLoad = readStatusKiB("VmRSS");
            long pssAfterLoad = Debug.getPss();

            Tensor positiveTensor = Tensor.fromBlob(positive, CONDITION_SHAPE);
            Tensor negativeTensor = Tensor.fromBlob(negative, CONDITION_SHAPE);
            long[] oneStepNanos = new long[3];
            float[] oneStepOutput = null;
            for (int iteration = 0; iteration < oneStepNanos.length; iteration++) {
                long started = SystemClock.elapsedRealtimeNanos();
                oneStepOutput = forward(module, initial, timesteps[0], positiveTensor, negativeTensor);
                oneStepNanos[iteration] = SystemClock.elapsedRealtimeNanos() - started;
            }
            writeFloat32(file("one-step-output.f32le"), oneStepOutput);

            long[] loopNanos = new long[2];
            float[] loopOutput = null;
            for (int iteration = 0; iteration < loopNanos.length; iteration++) {
                float[] latent = initial.clone();
                DpmSolverMultistepScheduler scheduler = new DpmSolverMultistepScheduler(sigmas);
                long started = SystemClock.elapsedRealtimeNanos();
                for (float timestep : timesteps) {
                    float[] prediction = forward(module, latent, timestep, positiveTensor, negativeTensor);
                    latent = scheduler.step(prediction, latent);
                }
                loopNanos[iteration] = SystemClock.elapsedRealtimeNanos() - started;
                loopOutput = latent;
            }
            writeFloat32(file("loop-output.f32le"), loopOutput);

            long rssAfterInference = readStatusKiB("VmRSS");
            long hwmAfterInference = readStatusKiB("VmHWM");
            long pssAfterInference = Debug.getPss();
            long peakHwm = Math.max(hwmBefore, hwmAfterInference);
            long peakPss = Math.max(pssBefore, Math.max(pssAfterLoad, pssAfterInference));
            String json = "{\n" +
                    "  \"schema_version\": 1,\n" +
                    "  \"status\": \"passed\",\n" +
                    "  \"model_bytes\": " + file("diffusion.pte").length() + ",\n" +
                    "  \"load_mode\": \"mmap\",\n" +
                    "  \"load_seconds\": " + seconds(loadNanos) + ",\n" +
                    "  \"one_step_seconds\": " + secondsJson(oneStepNanos) + ",\n" +
                    "  \"loop_seconds\": " + secondsJson(loopNanos) + ",\n" +
                    "  \"loop_steps\": 10,\n" +
                    "  \"one_step_output_sha256\": \"" + sha256(file("one-step-output.f32le")) + "\",\n" +
                    "  \"loop_output_sha256\": \"" + sha256(file("loop-output.f32le")) + "\",\n" +
                    "  \"memory_kib\": {\n" +
                    "    \"rss_before\": " + rssBefore + ",\n" +
                    "    \"rss_after_load\": " + rssAfterLoad + ",\n" +
                    "    \"rss_after_inference\": " + rssAfterInference + ",\n" +
                    "    \"process_hwm_peak\": " + peakHwm + ",\n" +
                    "    \"pss_before\": " + pssBefore + ",\n" +
                    "    \"pss_after_load\": " + pssAfterLoad + ",\n" +
                    "    \"pss_after_inference\": " + pssAfterInference + ",\n" +
                    "    \"pss_peak_observed\": " + peakPss + "\n" +
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
            try { writeText(resultFile, json); } catch (Throwable ignored) { }
            Log.e(TAG, "Diffusion probe failed", error);
        } finally {
            if (module != null) module.destroy();
            runOnUiThread(this::finish);
        }
    }

    private File file(String name) { return new File(getFilesDir(), name); }

    private static float[] forward(Module module, float[] latent, float timestep,
                                   Tensor positive, Tensor negative) {
        EValue[] outputs = module.forward(
                EValue.from(Tensor.fromBlob(latent, LATENT_SHAPE)),
                EValue.from(Tensor.fromBlob(new float[]{timestep}, new long[]{1})),
                EValue.from(positive), EValue.from(negative));
        if (outputs.length != 1 || !outputs[0].isTensor()) {
            throw new IllegalStateException("Expected one diffusion tensor output");
        }
        Tensor output = outputs[0].toTensor();
        float[] values = output.getDataAsFloatArray();
        if (values.length != 64) throw new IllegalStateException("Expected 64 output values");
        return values;
    }

    private static float[] readFloat32(File file, int count) throws Exception {
        byte[] bytes;
        try (FileInputStream stream = new FileInputStream(file)) { bytes = stream.readAllBytes(); }
        if (bytes.length != count * Float.BYTES) {
            throw new IllegalArgumentException("Expected " + count + " floats in " + file.getName());
        }
        float[] values = new float[count];
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(values);
        return values;
    }

    private static void writeFloat32(File file, float[] values) throws Exception {
        ByteBuffer bytes = ByteBuffer.allocate(values.length * Float.BYTES).order(ByteOrder.LITTLE_ENDIAN);
        bytes.asFloatBuffer().put(values);
        try (FileOutputStream stream = new FileOutputStream(file)) { stream.write(bytes.array()); }
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
        } catch (Throwable ignored) { }
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

    private static String secondsJson(long[] nanos) {
        StringBuilder result = new StringBuilder("[");
        for (int index = 0; index < nanos.length; index++) {
            if (index > 0) result.append(", ");
            result.append(seconds(nanos[index]));
        }
        return result.append(']').toString();
    }

    private static double seconds(long nanos) { return nanos / 1_000_000_000.0; }
    private static String escape(String value) {
        return value.replace("\\", "\\\\").replace("\"", "\\\"")
                .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t");
    }
}

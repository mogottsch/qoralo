package dev.moket.vibevoiceprobe;

import android.app.Activity;
import android.os.Bundle;
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
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/** Runs the frozen acoustic_decode -> semantic_encode ABI for calls 0..3. */
public final class StreamingProbeActivity extends Activity {
    private static final String TAG = "VibeVoiceFourCall";
    private static final String MODEL = "/data/local/tmp/vibevoice-four-call/audio.pte";

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        new Thread(this::runProbe, "vibevoice-four-call-probe").start();
    }

    private void runProbe() {
        File inputRoot = new File(getFilesDir(), "four-call-input");
        File outputRoot = new File(getFilesDir(), "four-call-output");
        File resultFile = new File(getFilesDir(), "four-call-result.json");
        Module module = null;
        try {
            deleteRecursively(outputRoot);
            require(outputRoot.mkdirs(), "could not create output directory");
            JSONObject manifest = readJson(new File(inputRoot, "manifest.json"));
            validateManifest(manifest, inputRoot);
            JSONObject abiJson = readJson(new File(inputRoot,
                    manifest.getJSONObject("abi").getString("file")));
            FourCallMetadata abi = new FourCallMetadata(abiJson);
            File modelFile = new File(MODEL);
            require(modelFile.isFile() && modelFile.length() > 0, "missing audio PTE: " + MODEL);
            long loadStart = SystemClock.elapsedRealtimeNanos();
            module = Module.load(modelFile.getAbsolutePath(), Module.LOAD_MODE_MMAP);
            double loadSeconds = seconds(SystemClock.elapsedRealtimeNanos() - loadStart);
            Set<String> methods = new HashSet<>(Arrays.asList(module.getMethods()));
            require(methods.equals(Set.of(abi.decoder.name, abi.semantic.name)),
                    "PTE method mismatch: " + methods);

            CacheState decoderState = CacheState.reset(abi.decoder);
            CacheState semanticState = CacheState.reset(abi.semantic);
            int phase = 0;
            JSONArray callResults = new JSONArray();
            JSONArray calls = manifest.getJSONArray("calls");
            for (int call = 0; call < FourCallMetadata.CALL_COUNT; call++) {
                FourCallMetadata.Transition transition = abi.transitions[call];
                require(phase == transition.phase, "controller phase mismatch at call " + call);
                require(Arrays.equals(decoderState.lengths, transition.decoderPre),
                        "decoder pre lengths mismatch at call " + call);
                require(Arrays.equals(semanticState.lengths, transition.semanticPre),
                        "semantic pre lengths mismatch at call " + call);
                JSONObject latentRecord = calls.getJSONObject(call).getJSONObject("decoder_latent");
                RawFloatTensor latent = readFloatTensor(new File(inputRoot, latentRecord.getString("file")),
                        FourCallMetadata.longs(latentRecord.getJSONArray("shape")));
                File callRoot = new File(outputRoot, "call-" + call);
                require(callRoot.mkdirs(), "could not create " + callRoot);
                long started = SystemClock.elapsedRealtimeNanos();
                Invocation decoder = invoke(module, abi.decoder, latent, phase, decoderState,
                        transition.decoderPost, "call " + call + " decoder");
                Invocation semantic = invoke(module, abi.semantic, decoder.primary, phase, semanticState,
                        transition.semanticPost, "call " + call + " semantic");
                double inferenceSeconds = seconds(SystemClock.elapsedRealtimeNanos() - started);

                // Commit is intentionally after both invocations and all validation have succeeded.
                decoderState = decoder.nextState;
                semanticState = semantic.nextState;
                phase = transition.nextPhase;
                JSONArray outputs = new JSONArray();
                addOutput(outputs, callRoot, outputRoot, "pcm", decoder.primary, 0);
                addOutput(outputs, callRoot, outputRoot, "semantic_output", semantic.primary, 1);
                int order = 2;
                for (int i = 0; i < FourCallMetadata.CACHE_COUNT; i++)
                    addOutput(outputs, callRoot, outputRoot, "decoder_cache_" + FourCallMetadata.twoDigits(i),
                            decoderState.caches[i], order++);
                for (int i = 0; i < FourCallMetadata.CACHE_COUNT; i++)
                    addOutput(outputs, callRoot, outputRoot, "semantic_cache_" + FourCallMetadata.twoDigits(i),
                            semanticState.caches[i], order++);
                JSONObject record = new JSONObject();
                record.put("call", call); record.put("phase", transition.phase);
                record.put("next_phase", phase); record.put("decoder_pre_valid_lengths", intsJson(transition.decoderPre));
                record.put("decoder_post_valid_lengths", intsJson(decoderState.lengths));
                record.put("semantic_pre_valid_lengths", intsJson(transition.semanticPre));
                record.put("semantic_post_valid_lengths", intsJson(semanticState.lengths));
                record.put("inference_seconds", inferenceSeconds); record.put("outputs", outputs);
                callResults.put(record);
            }
            JSONObject result = new JSONObject();
            result.put("schema_version", 1); result.put("abi_id", FourCallMetadata.ABI_ID);
            result.put("status", "passed"); result.put("artifact", MODEL);
            result.put("method_dispatch", new JSONArray().put("acoustic_decode").put("semantic_encode"));
            result.put("load_seconds", loadSeconds); result.put("calls", callResults);
            writeText(resultFile, result.toString(2) + "\n");
            Log.i(TAG, "RESULT " + result);
        } catch (Throwable error) {
            writeFailure(resultFile, error);
            Log.e(TAG, "Four-call probe failed", error);
        } finally {
            if (module != null) module.destroy();
            runOnUiThread(this::finish);
        }
    }

    private static Invocation invoke(Module module, FourCallMetadata.MethodSpec method,
            RawFloatTensor primary, int phase, CacheState state, int[] expectedLengths, String label) {
        assertTensor(primary, method.inputs.get(0), label + " primary input");
        List<EValue> values = new ArrayList<>();
        values.add(primary.toEValue());
        values.add(EValue.from(Tensor.fromBlob(new int[]{phase}, new long[]{})));
        values.add(EValue.from(Tensor.fromBlob(state.lengths, new long[]{FourCallMetadata.CACHE_COUNT})));
        int[] inputHashes = new int[FourCallMetadata.CACHE_COUNT];
        for (int index = 0; index < state.caches.length; index++) {
            assertTensor(state.caches[index], method.inputs.get(index + 3), label + " cache " + index);
            inputHashes[index] = Arrays.hashCode(state.caches[index].values);
            values.add(state.caches[index].toEValue());
        }
        int lengthHash = Arrays.hashCode(state.lengths);
        EValue[] raw = module.execute(method.name, values.toArray(new EValue[0]));
        require(raw.length == method.outputs.size(), label + ": output count mismatch");
        require(Arrays.hashCode(state.lengths) == lengthHash, label + ": input lengths mutated");
        for (int index = 0; index < state.caches.length; index++)
            require(Arrays.hashCode(state.caches[index].values) == inputHashes[index],
                    label + ": input cache mutated at " + index);
        for (EValue value : raw) require(value.isTensor(), label + ": non-tensor output");
        RawFloatTensor output = RawFloatTensor.from(raw[0].toTensor(), method.outputs.get(0), label);
        Tensor lengthsTensor = raw[1].toTensor();
        require(lengthsTensor.dtype() == DType.INT32, label + ": length dtype mismatch");
        assertShape(lengthsTensor.shape(), new long[]{FourCallMetadata.CACHE_COUNT}, label + " lengths");
        int[] nextLengths = lengthsTensor.getDataAsIntArray();
        require(Arrays.equals(nextLengths, expectedLengths), label + ": next lengths mismatch");
        RawFloatTensor[] caches = new RawFloatTensor[FourCallMetadata.CACHE_COUNT];
        for (int index = 0; index < caches.length; index++) {
            caches[index] = RawFloatTensor.from(raw[index + 2].toTensor(), method.outputs.get(index + 2), label);
            validateCache(caches[index], nextLengths[index], method.capacityAxes[index], label + " cache " + index);
            require(caches[index].values != state.caches[index].values, label + ": cache storage aliased");
        }
        return new Invocation(output, new CacheState(nextLengths.clone(), caches));
    }

    private static void validateManifest(JSONObject manifest, File root) throws Exception {
        require(manifest.getInt("schema_version") == 1, "unsupported manifest version");
        require(FourCallMetadata.ABI_ID.equals(manifest.getString("abi_id")), "manifest ABI mismatch");
        JSONObject abi = manifest.getJSONObject("abi");
        File abiFile = new File(root, abi.getString("file"));
        require(abiFile.isFile() && sha256(abiFile).equals(abi.getString("sha256")), "ABI hash mismatch");
        JSONArray methods = manifest.getJSONObject("artifact").getJSONArray("methods");
        require(methods.length() == 2 && "acoustic_decode".equals(methods.getString(0))
                && "semantic_encode".equals(methods.getString(1)), "manifest method ordering mismatch");
        JSONArray calls = manifest.getJSONArray("calls");
        require(calls.length() == FourCallMetadata.CALL_COUNT, "manifest call count mismatch");
        for (int call = 0; call < calls.length(); call++) {
            JSONObject value = calls.getJSONObject(call);
            require(value.getInt("call") == call && value.getInt("required_phase") == call,
                    "manifest call ordering mismatch");
            JSONObject tensor = value.getJSONObject("decoder_latent");
            require("float32".equals(tensor.getString("dtype"))
                    && Arrays.equals(FourCallMetadata.longs(tensor.getJSONArray("shape")), new long[]{1, 1, 64}),
                    "latent metadata mismatch at call " + call);
            File file = new File(root, tensor.getString("file"));
            require(file.isFile() && file.length() == 256 && tensor.getLong("byte_count") == 256,
                    "latent bytes mismatch at call " + call);
            require(sha256(file).equals(tensor.getString("sha256")), "latent hash mismatch at call " + call);
        }
    }

    private static void validateCache(RawFloatTensor tensor, int validLength, int axis, String label) {
        require(axis == tensor.shape.length - 1, label + ": capacity axis mismatch");
        int capacity = (int) tensor.shape[axis];
        require(validLength >= 0 && validLength <= capacity, label + ": invalid valid length");
        for (int index = 0; index < tensor.values.length; index++) {
            float value = tensor.values[index];
            require(Float.isFinite(value), label + ": non-finite value");
            if (index % capacity >= validLength)
                require(Float.floatToRawIntBits(value) == 0, label + ": non-zero padding");
        }
    }

    private static void addOutput(JSONArray outputs, File callRoot, File outputRoot, String name,
            RawFloatTensor tensor, int order) throws Exception {
        File file = new File(callRoot, name + ".f32le"); writeTensor(file, tensor);
        JSONObject record = new JSONObject(); record.put("order", order); record.put("name", name);
        record.put("file", outputRoot.toPath().relativize(file.toPath()).toString().replace(File.separatorChar, '/'));
        record.put("shape", longsJson(tensor.shape)); record.put("dtype", "float32");
        record.put("byte_count", file.length()); record.put("sha256", sha256(file)); outputs.put(record);
    }

    private static final class Invocation {
        final RawFloatTensor primary; final CacheState nextState;
        Invocation(RawFloatTensor primary, CacheState nextState) { this.primary = primary; this.nextState = nextState; }
    }
    private static final class CacheState {
        final int[] lengths; final RawFloatTensor[] caches;
        CacheState(int[] lengths, RawFloatTensor[] caches) { this.lengths = lengths; this.caches = caches; }
        static CacheState reset(FourCallMetadata.MethodSpec method) {
            RawFloatTensor[] caches = new RawFloatTensor[FourCallMetadata.CACHE_COUNT];
            for (int index = 0; index < caches.length; index++) {
                long[] shape = method.inputs.get(index + 3).shape;
                caches[index] = new RawFloatTensor(new float[numel(shape)], shape.clone());
            }
            return new CacheState(new int[FourCallMetadata.CACHE_COUNT], caches);
        }
    }
    private static final class RawFloatTensor {
        final float[] values; final long[] shape;
        RawFloatTensor(float[] values, long[] shape) { this.values = values; this.shape = shape; }
        EValue toEValue() { return EValue.from(Tensor.fromBlob(values, shape)); }
        static RawFloatTensor from(Tensor tensor, FourCallMetadata.TensorSpec spec, String label) {
            require(tensor.dtype() == DType.FLOAT, label + ": expected FLOAT, got " + tensor.dtype());
            assertShape(tensor.shape(), spec.shape, label + " " + spec.name);
            float[] values = tensor.getDataAsFloatArray();
            for (float value : values) require(Float.isFinite(value), label + ": non-finite output");
            return new RawFloatTensor(values, tensor.shape().clone());
        }
    }

    private static RawFloatTensor readFloatTensor(File file, long[] shape) throws Exception {
        byte[] bytes; try (FileInputStream stream = new FileInputStream(file)) { bytes = stream.readAllBytes(); }
        require(bytes.length == numel(shape) * Float.BYTES, "tensor byte count mismatch: " + file);
        float[] values = new float[numel(shape)]; ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(values);
        return new RawFloatTensor(values, shape.clone());
    }
    private static void writeTensor(File file, RawFloatTensor tensor) throws Exception {
        ByteBuffer bytes = ByteBuffer.allocate(tensor.values.length * Float.BYTES).order(ByteOrder.LITTLE_ENDIAN);
        bytes.asFloatBuffer().put(tensor.values); try (FileOutputStream stream = new FileOutputStream(file)) { stream.write(bytes.array()); }
    }
    private static int numel(long[] shape) {
        long count = 1; for (long value : shape) { require(value > 0, "invalid tensor dimension"); count *= value; }
        require(count <= Integer.MAX_VALUE, "tensor too large"); return (int) count;
    }
    private static void assertTensor(RawFloatTensor actual, FourCallMetadata.TensorSpec expected, String label) {
        require("float32".equals(expected.dtype), label + ": spec dtype mismatch"); assertShape(actual.shape, expected.shape, label);
    }
    private static void assertShape(long[] actual, long[] expected, String label) {
        require(Arrays.equals(actual, expected), label + ": shape mismatch " + Arrays.toString(actual));
    }
    private static JSONObject readJson(File file) throws Exception {
        try (FileInputStream stream = new FileInputStream(file)) {
            return new JSONObject(new String(stream.readAllBytes(), StandardCharsets.UTF_8));
        }
    }
    private static void writeText(File file, String value) throws Exception {
        try (FileOutputStream stream = new FileOutputStream(file)) { stream.write(value.getBytes(StandardCharsets.UTF_8)); }
    }
    private static String sha256(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (FileInputStream stream = new FileInputStream(file)) { byte[] block = new byte[8192]; int n; while ((n = stream.read(block)) >= 0) digest.update(block, 0, n); }
        StringBuilder result = new StringBuilder(); for (byte value : digest.digest()) result.append(String.format(Locale.ROOT, "%02x", value)); return result.toString();
    }
    private static JSONArray intsJson(int[] values) { JSONArray result = new JSONArray(); for (int value : values) result.put(value); return result; }
    private static JSONArray longsJson(long[] values) { JSONArray result = new JSONArray(); for (long value : values) result.put(value); return result; }
    private static double seconds(long nanos) { return nanos / 1_000_000_000.0; }
    private static void require(boolean condition, String message) { if (!condition) throw new IllegalStateException(message); }
    private static void deleteRecursively(File file) throws Exception {
        if (!file.exists()) return; if (file.isDirectory()) { File[] children = file.listFiles(); if (children != null) for (File child : children) deleteRecursively(child); }
        if (!file.delete()) throw new IllegalStateException("could not delete " + file);
    }
    private static void writeFailure(File resultFile, Throwable error) {
        try { StringWriter trace = new StringWriter(); error.printStackTrace(new PrintWriter(trace)); JSONObject result = new JSONObject();
            result.put("schema_version", 1); result.put("abi_id", FourCallMetadata.ABI_ID); result.put("status", "failed");
            result.put("error_type", error.getClass().getName()); result.put("error", String.valueOf(error.getMessage())); result.put("trace", trace.toString());
            writeText(resultFile, result.toString(2) + "\n"); } catch (Throwable ignored) { Log.e(TAG, "Could not write failure result", ignored); }
    }
}

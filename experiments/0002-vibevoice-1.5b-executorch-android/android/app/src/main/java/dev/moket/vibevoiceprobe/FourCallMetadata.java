package dev.moket.vibevoiceprobe;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** Strict parser for the frozen four-call cache ABI. */
final class FourCallMetadata {
    static final String ABI_ID = "vibevoice-1.5b-four-call-cache-abi-v1";
    static final int CACHE_COUNT = 34;
    static final int CALL_COUNT = 4;

    static final class TensorSpec {
        final int order;
        final String name;
        final long[] shape;
        final String dtype;
        TensorSpec(int order, String name, long[] shape, String dtype) {
            this.order = order; this.name = name; this.shape = shape; this.dtype = dtype;
        }
    }

    static final class MethodSpec {
        final String name;
        final List<TensorSpec> inputs;
        final List<TensorSpec> outputs;
        final int[] capacityAxes;
        MethodSpec(String name, List<TensorSpec> inputs, List<TensorSpec> outputs, int[] capacityAxes) {
            this.name = name; this.inputs = inputs; this.outputs = outputs; this.capacityAxes = capacityAxes;
        }
    }

    static final class Transition {
        final int call, phase, nextPhase;
        final int[] decoderPre, decoderPost, semanticPre, semanticPost;
        Transition(JSONObject value, int expectedCall) throws JSONException {
            call = value.getInt("call"); phase = value.getInt("required_phase");
            nextPhase = value.getInt("next_phase");
            require(call == expectedCall, "transition call ordering mismatch");
            require(phase == expectedCall && nextPhase == expectedCall + 1, "transition phase mismatch");
            decoderPre = ints(value.getJSONArray("decoder_pre_valid_lengths"));
            decoderPost = ints(value.getJSONArray("decoder_post_valid_lengths"));
            semanticPre = ints(value.getJSONArray("semantic_pre_valid_lengths"));
            semanticPost = ints(value.getJSONArray("semantic_post_valid_lengths"));
            require(decoderPre.length == CACHE_COUNT && decoderPost.length == CACHE_COUNT
                    && semanticPre.length == CACHE_COUNT && semanticPost.length == CACHE_COUNT,
                    "transition valid-length shape mismatch");
            JSONArray range = value.getJSONArray("pcm_sample_range");
            require(range.length() == 2 && range.getInt(0) == call * 3200
                    && range.getInt(1) == (call + 1) * 3200, "PCM range mismatch");
        }
    }

    final MethodSpec decoder;
    final MethodSpec semantic;
    final Transition[] transitions;

    FourCallMetadata(JSONObject root) throws JSONException {
        require(root.getInt("schema_version") == 1, "unsupported ABI schema_version");
        require(ABI_ID.equals(root.getString("abi_id")), "unsupported abi_id");
        require("frozen_pre_export".equals(root.getString("status")), "ABI is not frozen");
        JSONObject methods = root.getJSONObject("methods");
        require(methods.length() == 2, "method count mismatch");
        decoder = parseMethod(methods.getJSONObject("acoustic_decode"), "acoustic_decode", 0,
                "decoder", "decoder_latent", new long[]{1, 1, 64}, "pcm", new long[]{1, 1, 3200});
        semantic = parseMethod(methods.getJSONObject("semantic_encode"), "semantic_encode", 1,
                "semantic", "pcm", new long[]{1, 1, 3200}, "semantic_output", new long[]{1, 1, 128});
        JSONArray calls = root.getJSONArray("call_transitions");
        require(calls.length() == CALL_COUNT, "call transition count mismatch");
        transitions = new Transition[CALL_COUNT];
        for (int call = 0; call < CALL_COUNT; call++) {
            transitions[call] = new Transition(calls.getJSONObject(call), call);
            if (call > 0) {
                require(Arrays.equals(transitions[call - 1].decoderPost, transitions[call].decoderPre),
                        "disconnected decoder transition");
                require(Arrays.equals(transitions[call - 1].semanticPost, transitions[call].semanticPre),
                        "disconnected semantic transition");
            }
        }
    }

    private static MethodSpec parseMethod(JSONObject value, String methodName, int methodOrder,
            String domain, String primaryName, long[] primaryShape, String outputName, long[] outputShape)
            throws JSONException {
        require(value.getInt("method_order") == methodOrder, methodName + " method order mismatch");
        JSONArray caches = value.getJSONArray("caches");
        require(caches.length() == CACHE_COUNT, methodName + " cache count mismatch");
        List<TensorSpec> expectedInputs = new ArrayList<>();
        List<TensorSpec> expectedOutputs = new ArrayList<>();
        expectedInputs.add(new TensorSpec(0, primaryName, primaryShape, "float32"));
        expectedInputs.add(new TensorSpec(1, "phase", new long[]{}, "int32"));
        expectedInputs.add(new TensorSpec(2, domain + "_valid_lengths", new long[]{CACHE_COUNT}, "int32"));
        expectedOutputs.add(new TensorSpec(0, outputName, outputShape, "float32"));
        expectedOutputs.add(new TensorSpec(1, domain + "_next_valid_lengths", new long[]{CACHE_COUNT}, "int32"));
        int[] axes = new int[CACHE_COUNT];
        for (int index = 0; index < CACHE_COUNT; index++) {
            JSONObject cache = caches.getJSONObject(index);
            require(cache.getInt("order") == index, methodName + " cache order mismatch");
            require((domain + "_cache_" + twoDigits(index)).equals(cache.getString("tensor_name")),
                    methodName + " cache name mismatch");
            require("float32".equals(cache.getString("dtype")), methodName + " cache dtype mismatch");
            long[] shape = longs(cache.getJSONArray("capacity_shape"));
            axes[index] = cache.getInt("capacity_axis");
            require(shape.length > 0 && axes[index] == shape.length - 1,
                    methodName + " cache capacity axis mismatch");
            expectedInputs.add(new TensorSpec(index + 3, domain + "_cache_" + twoDigits(index), shape, "float32"));
            expectedOutputs.add(new TensorSpec(index + 2, "next_" + domain + "_cache_" + twoDigits(index), shape, "float32"));
        }
        verifyTensorList(value.getJSONArray("inputs"), expectedInputs, methodName + " inputs");
        verifyTensorList(value.getJSONArray("outputs"), expectedOutputs, methodName + " outputs");
        return new MethodSpec(methodName, expectedInputs, expectedOutputs, axes);
    }

    private static void verifyTensorList(JSONArray actual, List<TensorSpec> expected, String label)
            throws JSONException {
        require(actual.length() == expected.size(), label + " tensor count mismatch");
        for (int index = 0; index < expected.size(); index++) {
            JSONObject item = actual.getJSONObject(index); TensorSpec spec = expected.get(index);
            require(item.getInt("order") == index && spec.name.equals(item.getString("name")),
                    label + " ordering mismatch at " + index);
            require(spec.dtype.equals(item.getString("dtype")), label + " dtype mismatch for " + spec.name);
            require(Arrays.equals(spec.shape, longs(item.getJSONArray("shape"))),
                    label + " shape mismatch for " + spec.name);
        }
    }

    static void require(boolean condition, String message) {
        if (!condition) throw new IllegalArgumentException(message);
    }
    static String twoDigits(int value) { return value < 10 ? "0" + value : String.valueOf(value); }
    static long[] longs(JSONArray array) throws JSONException {
        long[] values = new long[array.length()];
        for (int i = 0; i < values.length; i++) values[i] = array.getLong(i);
        return values;
    }
    static int[] ints(JSONArray array) throws JSONException {
        int[] values = new int[array.length()];
        for (int i = 0; i < values.length; i++) { values[i] = array.getInt(i); require(values[i] >= 0, "negative valid length"); }
        return values;
    }
}

package dev.moket.vibevoiceprobe;

import java.util.Arrays;

public final class TokenSelectorTest {
    private static final int VOCAB = 8;
    private static final int[] ALLOWED = {2, 4, 6, 7};

    private static TokenSelector selector(int capacity) {
        return new TokenSelector(VOCAB, ALLOWED, 7, new int[] {2, 4, 6}, capacity, 42);
    }

    private static float[] logits(float fill) {
        float[] result = new float[VOCAB];
        Arrays.fill(result, fill);
        return result;
    }

    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static void expect(Class<? extends Throwable> type, Runnable action) {
        try {
            action.run();
        } catch (Throwable error) {
            if (type.isInstance(error)) return;
            throw new AssertionError("expected " + type + ", got " + error, error);
        }
        throw new AssertionError("expected " + type);
    }

    private static void tiesMaskingAndUnderflow() {
        float[] tied = logits(-10f);
        tied[1] = 1_000_000f; // masked/disallowed
        tied[2] = 5f;
        tied[4] = 5f;
        var result = selector(4).select(tied);
        check(result.tokenId() == 2, "tie must choose lowest vocabulary ID");
        check(result.controlToken(), "speech token must be classified as control");

        float[] tiny = logits(-1f);
        tiny[2] = -Float.MIN_VALUE;
        tiny[4] = Float.MIN_VALUE;
        check(selector(4).select(tiny).tokenId() == 4, "subnormal FP32 scores must not underflow in selection");
    }

    private static void nonFiniteAndMaskedAllowedTokens() {
        float[] nan = logits(0f);
        nan[0] = Float.NaN;
        expect(IllegalArgumentException.class, () -> selector(2).select(nan));
        float[] positiveInf = logits(0f);
        positiveInf[4] = Float.POSITIVE_INFINITY;
        expect(IllegalArgumentException.class, () -> selector(2).select(positiveInf));
        float[] partiallyMasked = logits(Float.NEGATIVE_INFINITY);
        partiallyMasked[6] = -3f;
        check(selector(2).select(partiallyMasked).tokenId() == 6, "-Inf mask must be supported");
        expect(IllegalArgumentException.class, () -> selector(2).select(logits(Float.NEGATIVE_INFINITY)));
    }

    private static void terminationCapacityAndReset() {
        float[] eos = logits(-3f);
        eos[7] = 2f;
        TokenSelector eosSelector = selector(3);
        var eosResult = eosSelector.select(eos);
        check(eosResult.termination() == TokenSelector.Termination.EOS, "EOS must terminate");
        check(!eosResult.controlToken(), "EOS is a termination token, not a speech control token");
        expect(IllegalStateException.class, () -> eosSelector.select(eos));

        float[] ordinary = logits(-3f);
        ordinary[6] = 2f;
        TokenSelector capacity = selector(2);
        check(capacity.select(ordinary).termination() == TokenSelector.Termination.NONE, "capacity too early");
        check(capacity.select(ordinary).termination() == TokenSelector.Termination.CAPACITY, "capacity must terminate");
        capacity.reset(99);
        check(capacity.seed() == 99 && capacity.generatedCount() == 0, "reset must restore deterministic state");
        check(capacity.select(ordinary).tokenId() == 6, "seed reset must preserve greedy decision");
    }

    private static void lockedPyTorchSequence() {
        int[] allowed = {151643, 151652, 151653, 151654};
        int[] expected = {151652, 151654, 151654, 151653, 151643};
        TokenSelector nativeSelector = new TokenSelector(
                151936, allowed, 151643, new int[] {151652, 151653, 151654}, 8, 42);
        for (int step = 0; step < expected.length; step++) {
            float[] scores = new float[151936];
            Arrays.fill(scores, -1000f);
            scores[7] = 1_000_000f;
            scores[expected[step]] = 5f;
            if (step == 0) scores[151653] = 5f;
            if (step == 2) {
                scores[151654] = -103f;
                scores[151643] = -104f;
            }
            check(nativeSelector.select(scores).tokenId() == expected[step],
                    "native decision differs from captured PyTorch step " + step);
        }
        check(nativeSelector.termination() == TokenSelector.Termination.EOS, "locked sequence must end at EOS");
    }

    private static void invalidIdsShapesAndCapacity() {
        expect(IllegalArgumentException.class, () -> new TokenSelector(8, new int[] {2, 2, 7}, 7, null, 2, 42));
        expect(IllegalArgumentException.class, () -> new TokenSelector(8, new int[] {-1, 7}, 7, null, 2, 42));
        expect(IllegalArgumentException.class, () -> new TokenSelector(8, new int[] {2, 8}, 2, null, 2, 42));
        expect(IllegalArgumentException.class, () -> new TokenSelector(8, new int[] {2, 4}, 7, null, 2, 42));
        expect(IllegalArgumentException.class, () -> new TokenSelector(8, new int[] {2, 7}, 7, new int[] {4}, 2, 42));
        expect(IllegalArgumentException.class, () -> new TokenSelector(8, new int[] {2, 7}, 7, null, 0, 42));
        expect(IllegalArgumentException.class, () -> selector(2).select(new float[7]));
    }

    public static void main(String[] args) {
        tiesMaskingAndUnderflow();
        nonFiniteAndMaskedAllowedTokens();
        terminationCapacityAndReset();
        lockedPyTorchSequence();
        invalidIdsShapesAndCapacity();
        System.out.println("TokenSelectorTest: passed");
    }
}

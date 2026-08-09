package dev.moket.vibevoiceprobe;

import java.util.Arrays;

/**
 * Deterministic greedy token selection for the VibeVoice Qwen2 FP32 logits ABI.
 *
 * <p>The pinned model masks every ID except its four speech/control IDs and then
 * uses {@code torch.argmax}. Consequently sampling and RNG consumption are
 * deliberately absent. Equal scores select the lowest vocabulary ID, matching
 * PyTorch's first-index rule.</p>
 */
public final class TokenSelector {
    public enum Termination { NONE, EOS, CAPACITY }

    public record Selection(int tokenId, boolean controlToken, Termination termination) {}

    private final int vocabularySize;
    private final int[] allowedIds;
    private final boolean[] controlIds;
    private final int eosId;
    private final int capacity;
    private long seed;
    private int generatedCount;
    private Termination termination;

    public TokenSelector(
            int vocabularySize,
            int[] allowedIds,
            int eosId,
            int[] controlIds,
            int capacity,
            long seed) {
        if (vocabularySize <= 0) {
            throw new IllegalArgumentException("vocabularySize must be positive");
        }
        if (allowedIds == null || allowedIds.length == 0) {
            throw new IllegalArgumentException("allowedIds must not be empty");
        }
        if (capacity <= 0) {
            throw new IllegalArgumentException("capacity must be positive");
        }
        this.vocabularySize = vocabularySize;
        this.allowedIds = validatedSet(allowedIds, vocabularySize, "allowedIds");
        if (Arrays.binarySearch(this.allowedIds, eosId) < 0) {
            throw new IllegalArgumentException("eosId must be allowed");
        }
        this.eosId = eosId;
        this.controlIds = new boolean[vocabularySize];
        if (controlIds != null) {
            for (int id : validatedSet(controlIds, vocabularySize, "controlIds")) {
                if (Arrays.binarySearch(this.allowedIds, id) < 0) {
                    throw new IllegalArgumentException("control ID must be allowed: " + id);
                }
                this.controlIds[id] = true;
            }
        }
        this.capacity = capacity;
        reset(seed);
    }

    private static int[] validatedSet(int[] values, int upperBound, String name) {
        int[] result = values.clone();
        Arrays.sort(result);
        for (int index = 0; index < result.length; index++) {
            int id = result[index];
            if (id < 0 || id >= upperBound) {
                throw new IllegalArgumentException(name + " contains invalid ID: " + id);
            }
            if (index > 0 && result[index - 1] == id) {
                throw new IllegalArgumentException(name + " contains duplicate ID: " + id);
            }
        }
        return result;
    }

    /** Reset utterance-local termination state. The seed is retained for ABI provenance only. */
    public void reset(long seed) {
        this.seed = seed;
        this.generatedCount = 0;
        this.termination = Termination.NONE;
    }

    public Selection select(float[] logits) {
        if (termination != Termination.NONE) {
            throw new IllegalStateException("selection already terminated: " + termination);
        }
        if (logits == null || logits.length != vocabularySize) {
            throw new IllegalArgumentException(
                    "expected " + vocabularySize + " FP32 logits, got "
                            + (logits == null ? "null" : logits.length));
        }
        for (int id = 0; id < logits.length; id++) {
            float score = logits[id];
            if (Float.isNaN(score) || score == Float.POSITIVE_INFINITY) {
                throw new IllegalArgumentException("logits must not contain NaN or +Inf (ID " + id + ")");
            }
        }

        int selected = -1;
        float best = Float.NEGATIVE_INFINITY;
        for (int id : allowedIds) {
            float score = logits[id];
            if (selected < 0 || score > best) {
                selected = id;
                best = score;
            }
        }
        if (best == Float.NEGATIVE_INFINITY) {
            throw new IllegalArgumentException("all allowed token logits are masked (-Inf)");
        }

        generatedCount++;
        if (selected == eosId) {
            termination = Termination.EOS;
        } else if (generatedCount >= capacity) {
            termination = Termination.CAPACITY;
        }
        return new Selection(selected, controlIds[selected], termination);
    }

    public long seed() { return seed; }
    public int generatedCount() { return generatedCount; }
    public Termination termination() { return termination; }
    public int[] allowedIds() { return allowedIds.clone(); }
}

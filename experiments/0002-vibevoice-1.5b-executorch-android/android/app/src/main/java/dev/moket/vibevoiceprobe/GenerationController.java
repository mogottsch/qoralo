package dev.moket.vibevoiceprobe;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Objects;

/**
 * Native-owned, single-utterance VibeVoice generation state machine.
 *
 * <p>ExecuTorch adapters implement {@link Components}; this class deliberately has no Python,
 * Hugging Face cache, or mutable model state. It owns cache replacement, positions, diffusion
 * history, termination, streaming PCM, and reset/failure semantics.</p>
 */
public final class GenerationController {
    public enum State { IDLE, READY, GENERATING, TERMINATED, FAILED }
    public enum StopReason { NONE, EOS, CAPACITY, TARGET_DURATION, FAILURE }

    public record Config(
            int cacheCapacity,
            int speechStartId,
            int speechEndId,
            int speechDiffusionId,
            int sampleRate,
            long seed,
            float[] sigmas,
            float[] timesteps) {
        public Config {
            if (cacheCapacity <= 0 || sampleRate <= 0) throw new IllegalArgumentException("capacities must be positive");
            if (sigmas == null || sigmas.length != 11 || sigmas[10] != 0f) throw new IllegalArgumentException("expected 11 sigmas ending in zero");
            if (timesteps == null || timesteps.length != 10) throw new IllegalArgumentException("expected 10 timesteps");
            sigmas = sigmas.clone();
            timesteps = timesteps.clone();
        }
        @Override public float[] sigmas() { return sigmas.clone(); }
        @Override public float[] timesteps() { return timesteps.clone(); }
    }

    public record Prompt(float[] tokenEmbeddings, int tokenCount, int[] sequenceSpeakerIds, int initialSpeakerId, boolean initiallyInSpeech) {
        public Prompt(float[] tokenEmbeddings, int tokenCount, int[] sequenceSpeakerIds, int initialSpeakerId) {
            this(tokenEmbeddings, tokenCount, sequenceSpeakerIds, initialSpeakerId, false);
        }
        public Prompt {
            if (tokenEmbeddings == null || tokenCount <= 0 || tokenEmbeddings.length != tokenCount * 1536)
                throw new IllegalArgumentException("prompt must be contiguous [1,S,1536]");
            if (sequenceSpeakerIds == null || sequenceSpeakerIds.length != tokenCount)
                throw new IllegalArgumentException("sequence speaker IDs must have S entries");
            requireFinite(tokenEmbeddings, "prompt embeddings");
            tokenEmbeddings = tokenEmbeddings.clone();
            sequenceSpeakerIds = sequenceSpeakerIds.clone();
        }
        @Override public float[] tokenEmbeddings() { return tokenEmbeddings.clone(); }
        @Override public int[] sequenceSpeakerIds() { return sequenceSpeakerIds.clone(); }
    }

    public record Conditioning(float[] promptEmbeddings, float[] negativeCondition) {
        public Conditioning {
            requireSize(promptEmbeddings, -1, "conditioned prompt");
            requireSize(negativeCondition, 1536, "negative condition");
            promptEmbeddings = promptEmbeddings.clone();
            negativeCondition = negativeCondition.clone();
        }
        @Override public float[] promptEmbeddings() { return promptEmbeddings.clone(); }
        @Override public float[] negativeCondition() { return negativeCondition.clone(); }
    }
    public record QwenOutput(float[] logits, float[] hiddenState, Object[] caches) {
        public QwenOutput {
            requireSize(logits, -1, "logits");
            requireSize(hiddenState, 1536, "hidden state");
            validateCaches(caches, 56, "Qwen2");
            logits = logits.clone(); hiddenState = hiddenState.clone(); caches = caches.clone();
        }
        @Override public float[] logits() { return logits.clone(); }
        @Override public float[] hiddenState() { return hiddenState.clone(); }
        @Override public Object[] caches() { return caches.clone(); }
    }
    public record DecoderOutput(float[] pcm, Object[] caches) {
        public DecoderOutput {
            requireSize(pcm, 3200, "decoder PCM");
            validateCaches(caches, 34, "decoder");
            pcm = pcm.clone(); caches = caches.clone();
        }
        @Override public float[] pcm() { return pcm.clone(); }
        @Override public Object[] caches() { return caches.clone(); }
    }
    public record SemanticOutput(float[] features, Object[] caches) {
        public SemanticOutput {
            requireSize(features, 128, "semantic features");
            validateCaches(caches, 34, "semantic encoder");
            features = features.clone(); caches = caches.clone();
        }
        @Override public float[] features() { return features.clone(); }
        @Override public Object[] caches() { return caches.clone(); }
    }

    /** Thin adapters around PTE modules and immutable embedding/speaker tables. */
    public interface Components {
        Conditioning condition(Prompt prompt, int activeSpeakerId);
        float[] speakerCondition(int speakerId);
        QwenOutput prefill(float[] conditionedPrompt, int tokenCount);
        QwenOutput decode(float[] embedding, int position, Object[] qwenCaches);
        float[] tokenEmbedding(int tokenId);
        float[] initialNoise(long seed, int diffusionIndex);
        float[] diffusionPrediction(float[] sample, float timestep, float[] positive, float[] negative);
        DecoderOutput decodeAudio(float[] acousticFeatures, Object[] priorCaches);
        SemanticOutput encodeSemantic(float[] pcm, Object[] priorCaches);
        float[] joinConnectors(float[] acousticFeatures, float[] semanticFeatures);
    }

    public record Step(int tokenId, boolean audioProduced, State state, StopReason stopReason) {}

    private final Config config;
    private final Components components;
    private final TokenSelector selector;
    private final ByteArrayOutputStream pcm = new ByteArrayOutputStream();
    private State state = State.IDLE;
    private StopReason stopReason = StopReason.NONE;
    private QwenOutput qwen;
    private Object[] decoderCaches;
    private Object[] semanticCaches;
    private int validLength;
    private int diffusionIndex;
    private int audioChunkCount;
    private int activeSpeakerId;
    private int speakerTransitions;
    private boolean inSpeech;
    private float[] negativeCondition;
    private RuntimeException failure;

    public GenerationController(Config config, Components components, TokenSelector selector) {
        this.config = Objects.requireNonNull(config);
        this.components = Objects.requireNonNull(components);
        this.selector = Objects.requireNonNull(selector);
    }

    /** Starts a fresh utterance. Call reset before reusing a terminated or failed controller. */
    public void start(Prompt prompt) {
        requireState(State.IDLE);
        if (prompt.tokenCount() >= config.cacheCapacity()) throw new IllegalArgumentException("prompt leaves no decode capacity");
        try {
            activeSpeakerId = prompt.initialSpeakerId();
            inSpeech = prompt.initiallyInSpeech();
            Conditioning conditioning = Objects.requireNonNull(components.condition(prompt, activeSpeakerId));
            if (conditioning.promptEmbeddings().length != prompt.tokenCount() * 1536)
                throw new IllegalArgumentException("conditioned prompt shape mismatch");
            negativeCondition = conditioning.negativeCondition().clone();
            qwen = Objects.requireNonNull(components.prefill(conditioning.promptEmbeddings(), prompt.tokenCount()));
            validLength = prompt.tokenCount();
            state = State.READY;
        } catch (RuntimeException error) {
            fail(error);
            throw error;
        }
    }

    /** Selects one token and advances all required native-owned state. */
    public Step step() {
        if (state != State.READY && state != State.GENERATING) throw new IllegalStateException("step requires READY or GENERATING, was " + state);
        state = State.GENERATING;
        try {
            TokenSelector.Selection selection = selector.select(qwen.logits());
            int token = selection.tokenId();
            boolean audio = false;
            if (selection.termination() != TokenSelector.Termination.NONE) {
                terminate(selection.termination() == TokenSelector.Termination.EOS ? StopReason.EOS : StopReason.CAPACITY);
                return new Step(token, false, state, stopReason);
            }
            float[] nextEmbedding;
            if (token == config.speechStartId()) {
                if (inSpeech) throw new IllegalStateException("nested speech start");
                inSpeech = true;
                nextEmbedding = checkedEmbedding(components.tokenEmbedding(token), "speech-start embedding");
            } else if (token == config.speechEndId()) {
                if (!inSpeech) throw new IllegalStateException("speech end without speech start");
                inSpeech = false;
                nextEmbedding = checkedEmbedding(components.tokenEmbedding(token), "speech-end embedding");
            } else if (token == config.speechDiffusionId()) {
                if (!inSpeech) throw new IllegalStateException("diffusion token outside speech segment");
                float[] acoustic = runDiffusion(qwen.hiddenState());
                DecoderOutput decoded = components.decodeAudio(acoustic, cloneCaches(decoderCaches));
                decoderCaches = decoded.caches().clone();
                appendPcm(decoded.pcm());
                SemanticOutput semantic = components.encodeSemantic(decoded.pcm(), cloneCaches(semanticCaches));
                semanticCaches = semantic.caches().clone();
                nextEmbedding = checkedEmbedding(components.joinConnectors(acoustic, semantic.features()), "connector output");
                audio = true;
            } else {
                nextEmbedding = checkedEmbedding(components.tokenEmbedding(token), "token embedding");
            }
            if (validLength >= config.cacheCapacity()) throw new IllegalStateException("Qwen2 cache capacity exhausted");
            qwen = Objects.requireNonNull(components.decode(nextEmbedding, validLength, qwen.caches().clone()));
            validLength++;
            return new Step(token, audio, state, stopReason);
        } catch (RuntimeException error) {
            fail(error);
            throw error;
        }
    }

    /** Changes the condition used by subsequent diffusion calls; immutable prompt data is retained. */
    public void selectSpeaker(int speakerId) {
        if (state != State.READY && state != State.GENERATING) throw new IllegalStateException("speaker selection requires active generation");
        if (speakerId == activeSpeakerId) return;
        try {
            negativeCondition = checkedEmbedding(components.speakerCondition(speakerId), "speaker condition");
            activeSpeakerId = speakerId;
            speakerTransitions++;
        } catch (RuntimeException error) {
            fail(error);
            throw error;
        }
    }

    /** Terminates an active run after the harness has reached its requested audio duration. */
    public void finishAtTarget() {
        if (state != State.GENERATING || pcm.size() == 0)
            throw new IllegalStateException("target termination requires generated audio");
        terminate(StopReason.TARGET_DURATION);
    }

    public byte[] wav() {
        if (state != State.TERMINATED) throw new IllegalStateException("WAV is available only after termination");
        byte[] data = pcm.toByteArray();
        ByteBuffer out = ByteBuffer.allocate(44 + data.length).order(ByteOrder.LITTLE_ENDIAN);
        out.put(new byte[] {'R','I','F','F'}).putInt(36 + data.length).put(new byte[] {'W','A','V','E'});
        out.put(new byte[] {'f','m','t',' '}).putInt(16).putShort((short) 1).putShort((short) 1);
        out.putInt(config.sampleRate()).putInt(config.sampleRate() * 2).putShort((short) 2).putShort((short) 16);
        out.put(new byte[] {'d','a','t','a'}).putInt(data.length).put(data);
        return out.array();
    }

    public void reset() {
        selector.reset(config.seed());
        pcm.reset();
        state = State.IDLE; stopReason = StopReason.NONE; qwen = null;
        decoderCaches = null; semanticCaches = null; negativeCondition = null;
        validLength = 0; diffusionIndex = 0; audioChunkCount = 0; activeSpeakerId = 0; speakerTransitions = 0;
        inSpeech = false; failure = null;
    }

    private float[] runDiffusion(float[] positive) {
        float[] sample = components.initialNoise(config.seed(), diffusionIndex++);
        requireSize(sample, 64, "initial noise");
        DpmSolverMultistepScheduler scheduler = new DpmSolverMultistepScheduler(config.sigmas());
        float[] times = config.timesteps();
        for (int i = 0; i < times.length; i++) {
            float[] prediction = components.diffusionPrediction(sample, times[i], positive, negativeCondition);
            requireSize(prediction, 64, "diffusion prediction");
            sample = scheduler.step(prediction, sample);
        }
        return sample;
    }

    private void appendPcm(float[] values) {
        for (float value : values) {
            float bounded = Math.max(-1f, Math.min(1f, value));
            short sample = (short) Math.round(bounded * (bounded < 0 ? 32768f : 32767f));
            pcm.write(sample & 0xff); pcm.write((sample >>> 8) & 0xff);
        }
        audioChunkCount++;
    }

    private void terminate(StopReason reason) { state = State.TERMINATED; stopReason = reason; }
    private void fail(RuntimeException error) { state = State.FAILED; stopReason = StopReason.FAILURE; failure = error; }
    private void requireState(State expected) { if (state != expected) throw new IllegalStateException("expected " + expected + ", was " + state); }
    private static Object[] cloneCaches(Object[] caches) { return caches == null ? null : caches.clone(); }
    private static float[] checkedEmbedding(float[] value, String name) { requireSize(value, 1536, name); return value; }
    private static void requireSize(float[] value, int size, String name) {
        if (value == null || (size >= 0 && value.length != size) || (size < 0 && value.length == 0))
            throw new IllegalArgumentException(name + " has wrong shape");
        requireFinite(value, name);
    }
    private static void requireFinite(float[] value, String name) {
        for (float x : value) if (!Float.isFinite(x)) throw new IllegalArgumentException(name + " must be finite");
    }
    private static void validateCaches(Object[] caches, int count, String name) {
        if (caches == null || caches.length != count) throw new IllegalArgumentException(name + " requires exactly " + count + " caches");
        for (Object cache : caches) if (cache == null) throw new IllegalArgumentException(name + " cache must not be null");
    }

    public State state() { return state; }
    public StopReason stopReason() { return stopReason; }
    public int validLength() { return validLength; }
    public int activeSpeakerId() { return activeSpeakerId; }
    public int speakerTransitions() { return speakerTransitions; }
    public boolean inSpeech() { return inSpeech; }
    public int pcmSamples() { return pcm.size() / 2; }
    public int audioChunkCount() { return audioChunkCount; }
    public RuntimeException failure() { return failure; }
}

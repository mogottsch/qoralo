package dev.moket.vibevoiceprobe;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** Captured-component contract test runnable with the host JDK (no Android or model weights). */
public final class GenerationControllerTest {
    private static final int VOCAB = 8;
    private static final int START = 2, DIFFUSION = 3, END = 4, EOS = 7;

    private static final class FakeComponents implements GenerationController.Components {
        final int[] tokens;
        int outputIndex;
        int diffusionCalls, decoderCalls, semanticCalls, connectorCalls, prefillCalls, decodeCalls;
        int lastDecodePosition = -1;
        Object[] lastQwenInput;
        Object[] lastDecoderInput;
        Object[] lastSemanticInput;
        boolean failDiffusion;
        int qwenCacheCount = 56;
        final List<String> events = new ArrayList<>();

        FakeComponents(int... tokens) { this.tokens = tokens; }
        private static Object[] caches(int count, String prefix) {
            Object[] result = new Object[count];
            for (int i = 0; i < count; i++) result[i] = prefix + i;
            return result;
        }
        private GenerationController.QwenOutput output(String prefix) {
            float[] logits = new float[VOCAB]; Arrays.fill(logits, -100f);
            logits[tokens[Math.min(outputIndex++, tokens.length - 1)]] = 10f;
            return new GenerationController.QwenOutput(logits, fill(1536, 0.25f), caches(qwenCacheCount, prefix));
        }
        @Override public GenerationController.Conditioning condition(GenerationController.Prompt prompt, int speaker) {
            events.add("condition:" + speaker);
            return new GenerationController.Conditioning(prompt.tokenEmbeddings(), fill(1536, speaker));
        }
        @Override public float[] speakerCondition(int speaker) { events.add("speaker:" + speaker); return fill(1536, speaker); }
        @Override public GenerationController.QwenOutput prefill(float[] prompt, int count) {
            prefillCalls++; events.add("prefill:" + count); return output("prefill-");
        }
        @Override public GenerationController.QwenOutput decode(float[] embedding, int position, Object[] caches) {
            decodeCalls++; lastDecodePosition = position; lastQwenInput = caches; events.add("decode:" + position); return output("decode" + position + "-");
        }
        @Override public float[] tokenEmbedding(int token) { events.add("embed:" + token); return fill(1536, token); }
        @Override public float[] initialNoise(long seed, int index) { events.add("noise:" + seed + ":" + index); return fill(64, 0.1f); }
        @Override public float[] diffusionPrediction(float[] sample, float timestep, float[] positive, float[] negative) {
            if (failDiffusion) throw new IllegalStateException("captured diffusion failure");
            diffusionCalls++; events.add("diffusion"); return fill(64, 0.01f);
        }
        @Override public GenerationController.DecoderOutput decodeAudio(float[] features, Object[] prior) {
            decoderCalls++; lastDecoderInput = prior; events.add("audio");
            float[] pcm = new float[3200]; pcm[0] = -2f; pcm[1] = 2f;
            return new GenerationController.DecoderOutput(pcm, caches(34, "decoder-" + decoderCalls + "-"));
        }
        @Override public GenerationController.SemanticOutput encodeSemantic(float[] pcm, Object[] prior) {
            semanticCalls++; lastSemanticInput = prior; events.add("semantic");
            return new GenerationController.SemanticOutput(fill(128, 0.2f), caches(34, "semantic-" + semanticCalls + "-"));
        }
        @Override public float[] joinConnectors(float[] acoustic, float[] semantic) {
            connectorCalls++; events.add("connector"); return fill(1536, 0.3f);
        }
    }

    private static float[] fill(int count, float value) { float[] x = new float[count]; Arrays.fill(x, value); return x; }
    private static GenerationController.Config config(int capacity) {
        return new GenerationController.Config(capacity, START, END, DIFFUSION, 24000, 42,
                new float[] {10f,8f,6f,4f,3f,2f,1f,.5f,.2f,.1f,0f},
                new float[] {999f,888f,777f,666f,555f,444f,333f,222f,111f,0f});
    }
    private static TokenSelector selector(int selectionCapacity) {
        return new TokenSelector(VOCAB, new int[] {START, DIFFUSION, END, EOS}, EOS,
                new int[] {START, DIFFUSION, END}, selectionCapacity, 42);
    }
    private static GenerationController.Prompt prompt() {
        return new GenerationController.Prompt(fill(2 * 1536, .1f), 2, new int[] {-1, 0}, 0);
    }
    private static void check(boolean value, String message) { if (!value) throw new AssertionError(message); }
    private static void expect(Class<? extends Throwable> type, Runnable action) {
        try { action.run(); } catch (Throwable error) {
            if (type.isInstance(error)) return;
            throw new AssertionError("expected " + type + ", got " + error, error);
        }
        throw new AssertionError("expected " + type);
    }

    private static void fullControlFlowTransportAndWav() {
        FakeComponents fake = new FakeComponents(START, DIFFUSION, DIFFUSION, END, EOS);
        GenerationController c = new GenerationController(config(16), fake, selector(10));
        c.start(prompt());
        check(c.state() == GenerationController.State.READY && c.validLength() == 2, "prefill state");
        check(c.step().tokenId() == START && c.inSpeech(), "speech start");
        check(c.step().audioProduced(), "first diffusion must produce audio");
        check(fake.lastDecoderInput == null && fake.lastSemanticInput == null, "first streaming calls have no caches");
        c.selectSpeaker(1);
        check(c.activeSpeakerId() == 1 && c.speakerTransitions() == 1, "speaker transition");
        c.selectSpeaker(1);
        check(c.speakerTransitions() == 1, "reselecting active speaker must be a no-op");
        check(c.step().audioProduced(), "second diffusion must produce audio");
        check(fake.lastDecoderInput != null && fake.lastDecoderInput.length == 34, "decoder cache handoff");
        check(fake.lastSemanticInput != null && fake.lastSemanticInput.length == 34, "semantic cache handoff");
        check(c.step().tokenId() == END && !c.inSpeech(), "speech end");
        GenerationController.Step eos = c.step();
        check(eos.state() == GenerationController.State.TERMINATED && eos.stopReason() == GenerationController.StopReason.EOS, "EOS termination");
        check(fake.diffusionCalls == 20 && fake.decoderCalls == 2 && fake.semanticCalls == 2 && fake.connectorCalls == 2, "component call counts");
        check(fake.decodeCalls == 4 && fake.lastDecodePosition == 5 && c.validLength() == 6, "decode positions");
        check(fake.lastQwenInput.length == 56 && String.valueOf(fake.lastQwenInput[0]).startsWith("decode4-"), "replacement Qwen cache transport");
        check(c.pcmSamples() == 6400, "streamed sample count");

        byte[] wav = c.wav();
        check(new String(wav, 0, 4).equals("RIFF") && new String(wav, 8, 4).equals("WAVE"), "WAV magic");
        ByteBuffer h = ByteBuffer.wrap(wav).order(ByteOrder.LITTLE_ENDIAN);
        check(h.getInt(24) == 24000 && h.getShort(22) == 1 && h.getShort(34) == 16, "WAV format");
        check(h.getInt(40) == 12800 && wav.length == 12844, "WAV sizes");
        check(h.getShort(44) == Short.MIN_VALUE && h.getShort(46) == Short.MAX_VALUE, "PCM clipping");
        expect(IllegalStateException.class, c::step);
    }

    private static void invalidOrderCountsAndCapacity() {
        GenerationController idle = new GenerationController(config(4), new FakeComponents(EOS), selector(3));
        expect(IllegalStateException.class, idle::step);
        expect(IllegalStateException.class, idle::wav);
        expect(IllegalArgumentException.class, () -> idle.start(new GenerationController.Prompt(fill(4 * 1536, 0), 4, new int[] {-1,-1,-1,-1}, 0)));

        GenerationController endFirst = new GenerationController(config(8), new FakeComponents(END), selector(3));
        endFirst.start(prompt());
        expect(IllegalStateException.class, endFirst::step);
        check(endFirst.state() == GenerationController.State.FAILED, "bad speech order must fail closed");

        FakeComponents wrongCaches = new FakeComponents(EOS); wrongCaches.qwenCacheCount = 55;
        GenerationController bad = new GenerationController(config(8), wrongCaches, selector(3));
        expect(IllegalArgumentException.class, () -> bad.start(prompt()));
        check(bad.state() == GenerationController.State.FAILED, "cache count failure state");

        GenerationController capacity = new GenerationController(config(3), new FakeComponents(START, DIFFUSION), selector(4));
        capacity.start(prompt()); capacity.step();
        expect(IllegalStateException.class, capacity::step);
        check(capacity.stopReason() == GenerationController.StopReason.FAILURE, "Qwen capacity rejection");
    }

    private static void failuresAndResetAreDeterministic() {
        FakeComponents fake = new FakeComponents(START, DIFFUSION, START, EOS);
        GenerationController c = new GenerationController(config(12), fake, selector(8));
        c.start(prompt()); c.step(); fake.failDiffusion = true;
        expect(IllegalStateException.class, c::step);
        check(c.state() == GenerationController.State.FAILED && c.failure() != null, "component failure propagation");
        c.reset();
        check(c.state() == GenerationController.State.IDLE && c.validLength() == 0 && c.pcmSamples() == 0 && c.failure() == null, "full reset");
        fake.failDiffusion = false;
        c.start(prompt());
        check(c.step().tokenId() == START, "selector and generation reset deterministically");
    }

    private static void selectorCapacityTermination() {
        FakeComponents fake = new FakeComponents(START);
        GenerationController c = new GenerationController(config(8), fake, selector(1));
        c.start(prompt());
        GenerationController.Step result = c.step();
        check(result.stopReason() == GenerationController.StopReason.CAPACITY && fake.decodeCalls == 0, "selector capacity terminates before decode");
    }

    public static void main(String[] args) {
        fullControlFlowTransportAndWav();
        invalidOrderCountsAndCapacity();
        failuresAndResetAreDeterministic();
        selectorCapacityTermination();
        System.out.println("GenerationControllerTest: passed");
    }
}

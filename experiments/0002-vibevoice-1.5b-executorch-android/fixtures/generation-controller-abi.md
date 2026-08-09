# Native generation controller ABI

## Scope and precision

`GenerationController` is the Java control plane for the smallest accepted mobile configuration: the validated dynamic-activation/static per-channel **INT8 Qwen2** prefill/decode package. The rejected INT4 candidate is not selected because its host tensor/cache error exceeds the recorded bounds. Qwen2 logits, hidden state, all connector/semantic/diffusion tensors, scheduler arithmetic, decoder PCM, and caches cross the controller as FP32; masks, positions, and speaker/token IDs remain integer values inside their ExecuTorch adapters. Quantization is therefore confined to Qwen2 linear weights and does not alter this ABI.

The controller contains no Python or Hugging Face state. `Components` is the narrow adapter interface for ExecuTorch modules and immutable embedding/speaker tables. The host test uses captured-shape fakes through that same interface.

## State ownership

| State | Owner | Lifetime / reset |
|---|---|---|
| Qwen2 `validLength` and 56 ordered KV tensors | controller | replaced after every prefill/decode; discarded on reset |
| token-selection count, EOS/capacity state, seed provenance | `TokenSelector`, invoked by controller | reset to seed 42 at utterance reset |
| speech-segment flag and active speaker ID | controller | speech start/end tokens change the flag; `selectSpeaker` changes the diffusion condition |
| diffusion DPM-Solver history | a new scheduler per diffusion token | exactly ten steps, then discarded |
| deterministic noise stream index | controller | increments once per diffusion token; reset to zero |
| streaming decoder 34 tensors | controller | `null` means the `first` entry; subsequent outputs replace all caches |
| semantic encoder 34 tensors | controller | same first/cached rule, independent of decoder caches |
| PCM S16LE byte stream | controller | appended per 3,200-sample chunk; discarded on reset |
| model parameters, prompt features, token embedding table | component adapters | immutable across utterances |

Arrays and cache lists returned in controller records are defensively copied. Tensor objects are opaque adapter handles; the ordered 56/34-element lists, not object names or Python dictionaries, are normative.

## Call protocol

1. Construct the controller in `IDLE` with the locked 11-sigma/10-timestep schedule, sample rate 24,000, seed 42, cache capacity 1,024, and the pinned token IDs.
2. `start(Prompt)` validates contiguous-equivalent flat `[1,S,1536]` embeddings and `S` speaker IDs, calls speaker conditioning, then Qwen2 prefill. It accepts exactly 56 non-null Qwen caches and enters `READY` with `validLength=S`. `S >= capacity` is rejected.
3. `step()` invokes deterministic masked-greedy selection once:
   - speech-start opens a segment and decodes its tied embedding;
   - speech-end requires an open segment, closes it, and decodes its tied embedding;
   - speech-diffusion requires an open segment, runs ten prediction/scheduler steps, streams the resulting 64 floats through the audio decoder, sends the resulting 3,200 FP32 PCM values through the semantic encoder, joins acoustic `[1,1,64]` and semantic `[1,1,128]` features into the next `[1,1,1536]` embedding, then decodes it;
   - other allowed nonterminal tokens use their tied embedding;
   - EOS and selector capacity terminate without another decode.
4. Decode receives the current position and all 56 caches. A successful return replaces all caches and increments the position once. Positions at capacity are rejected, never wrapped or evicted.
5. `selectSpeaker(id)` is allowed only during active generation. A changed ID obtains a validated 1,536-float condition for subsequent diffusion calls and increments the transition count. Selecting the current ID is a no-op.
6. `wav()` is available only in `TERMINATED`. It returns mono 24 kHz PCM S16LE with a canonical 44-byte RIFF/WAVE header. Samples are clipped to `[-1,1]` before conversion.
7. `reset()` discards every utterance-owned field and returns to `IDLE`; immutable component data remains loaded.

## Fail-closed rules

Invalid call order, nested start, unmatched speech end, diffusion outside speech, wrong prompt dimensions, non-finite floats, incorrect 56/34 cache counts, null cache entries, malformed component output, and capacity overflow are rejected. A component exception changes state to `FAILED`, stores the cause, and prevents further generation or WAV finalization. Recovery requires `reset()` followed by a new `start()`.

## Host evidence

The pure-JDK captured/fake test covers call order and positions; exact cache replacement transport; speech start, diffusion, speech end, and EOS; ten diffusion calls per audio chunk; speaker changes; independent decoder and semantic caches; selector and Qwen capacity; component failures; deterministic reset; PCM clipping; and RIFF fields.

```bash
ROOT=experiments/0002-vibevoice-1.5b-executorch-android
OUT=$(mktemp -d)
javac -d "$OUT" \
  "$ROOT/android/app/src/main/java/dev/moket/vibevoiceprobe/TokenSelector.java" \
  "$ROOT/android/app/src/main/java/dev/moket/vibevoiceprobe/DpmSolverMultistepScheduler.java" \
  "$ROOT/android/app/src/main/java/dev/moket/vibevoiceprobe/GenerationController.java" \
  "$ROOT/tests/java/dev/moket/vibevoiceprobe/GenerationControllerTest.java"
java -cp "$OUT" dev.moket.vibevoiceprobe.GenerationControllerTest
rm -rf "$OUT"

export ANDROID_HOME=/home/moritz/Android/Sdk
GRADLE="$PWD/artifacts/tools/gradle-8.10.2/bin/gradle"
cd "$ROOT/android" && "$GRADLE" --offline assembleDebug
```

This step validates native transport and control flow without claiming real end-to-end audio. Loading real PTE adapters and generating the first Android speech chunk remain Step 32.

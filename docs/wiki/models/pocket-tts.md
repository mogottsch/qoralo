---
title: Pocket TTS
aliases:
  - kyutai/pocket-tts-without-voice-cloning
  - Pocket
kind: model
project: vibevoice-android-spike
status: reviewed
last_verified: 2026-08-25
---

# Pocket TTS

> Pocket TTS is a compact recurrent text-to-speech model that matters here because it has complete Android CPU and physical QNN/HTP routes, while also demonstrating why voice inputs, recurrent-cache shapes, and graph identity must be pinned precisely.

## Upstream identities

The source-derived work pins the public `kyutai/pocket-tts-without-voice-cloning` snapshot at revision `d29db7978e464fb90cb3359ee0c69a273b9142cc`:

- <https://huggingface.co/kyutai/pocket-tts-without-voice-cloning/tree/d29db7978e464fb90cb3359ee0c69a273b9142cc>

The registry also contains the distinct archive-backed identity `sherpa-onnx-pocket-tts-int8-2026-01-26`:

- <https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/sherpa-onnx-pocket-tts-int8-2026-01-26.tar.bz2>

The source-derived experiments pin upstream Pocket code revision `d108410d23eef7e01db282f9442891162dbc3db6`. Archive-backed and source-derived routes must not be assumed identical.

## Project routes and status

| Experiments | Route | Committed status |
|---|---|---|
| `0008`, `0009` | Released sherpa-onnx INT8 CPU archive | **Ran.** These are historical, noncanonical transcript routes; their unavailable Android WAVs were not retrospectively reviewed. |
| `0012` | Five-component source-derived FP ONNX CPU and ExecuTorch screen | **ONNX ran; ExecuTorch blocked.** Later evidence showed that the ONNX route had exercised an invalid Bria cloning contract against a no-voice-cloning checkpoint whose relevant Mimi encoder tensors were zero. |
| `0014` | QNN investigation and recovered official fixed-Alba route | **Ran.** Historical invalid voice-input routes remain preserved. Separate fixed-Alba CPU and fallback-disabled QNN/HTP derivatives completed, including distinct canonical-v2 text64/cache512 routes. |
| `0016` | Mixed QNN/HTP plus CPU fallback | **Ran, but remained hybrid.** It changed the output, was slower per generated audio second than the matched 0012 CPU route, and its exact retained sample was rejected. |
| `0024` | Canonical-v2 reconstructed source ONNX versus external contexts | **Ran as a new derivative.** Context loading cut the matched eight-session setup boundary, but the source and context WAVs differ and both exact hashes remain `not_reviewed`. |

The current canonical fixed-voice route combines [Fixed Alba](../concepts/fixed-alba.md), [text64](../concepts/text64.md), and [cache512](../concepts/cache512.md). These names describe one bounded input and graph contract, not the entire Pocket model family.

## Key limitations

- The selected public checkpoint is the **without-voice-cloning** checkpoint. The recovered route supplies a precomputed Alba state; it does not clone arbitrary voices.
- Experiment 0012's source/ONNX agreement validated a broken audio-cloning contract, not useful speech.
- Fixed-cache derivatives, dynamic graphs, archive graphs, text26/cache256 graphs, text64/cache512 graphs, and the reconstructed 0024 graphs are distinct artifacts.
- QNN provider assignment and physical accelerator evidence do not establish numerical equivalence or listening quality.
- Experiment 0024 reconstructed from pinned sources but did not reproduce experiment 0014's graph hashes. Its results and unreviewed output hashes therefore stay separate.
- Accepted or rejected listening verdicts apply only to their exact WAV hashes and routes. Neither kind of verdict generalizes to Pocket TTS as a family.
- The committed routes do not establish arbitrary speakers, arbitrary text lengths, streaming first-audio latency, or production readiness.

See [Evidence boundaries](../methods/evidence-boundaries.md).

## Related experiments

- `experiments/0008-sherpa-onnx-android-tts-benchmark/`
- `experiments/0009-android-tts-optimization/`
- `experiments/0012-pocket-onnx-vs-executorch-android/`
- `experiments/0014-pocket-fp-onnx-qnn-htp/`
- `experiments/0016-pocket-onnx-qnn-hybrid-android/`
- `experiments/0024-pocket-tts-qnn-precompiled-context-startup/`

## Evidence sources

- `docs/android-benchmarks/registry.json`
- `experiments/0008-sherpa-onnx-android-tts-benchmark/README.md`
- `experiments/0012-pocket-onnx-vs-executorch-android/README.md`
- `experiments/0014-pocket-fp-onnx-qnn-htp/README.md`
- `experiments/0014-pocket-fp-onnx-qnn-htp/results/zero-voice-encoder-root-cause.json`
- `experiments/0014-pocket-fp-onnx-qnn-htp/results/canonical-v2-benchmark.json`
- `experiments/0016-pocket-onnx-qnn-hybrid-android/results/hybrid-phone.json`
- `experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/result.json`
- `experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/reconstruction.json`

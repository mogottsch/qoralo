# Results — Pocket TTS with FP ONNX Runtime on Android CPU

## Clear outcome

**Yes, the unquantized floating-point ONNX version worked end to end on the Android phone CPU.**

The successful path performed the complete synthesis pipeline on the authorized Samsung Galaxy S23 Ultra:

```text
text
  → text conditioning
  → recurrent/autoregressive FlowLM
  → flow-matching generation
  → Mimi audio decoding
  → 24 kHz mono WAV
```

It did not substitute neural intermediate fixtures. It used ONNX Runtime's CPU execution provider with one thread. There were no QNN provider events, no HTP execution, and no quantization.

## Most important result: real-time factor

**Warm median RTF: `0.630`**

| Measurement | Generation latency | Audio duration | RTF |
|---|---:|---:|---:|
| First/cold generation | 5.697 s | 6.240 s | **0.913** |
| Warm median, 5 runs | **3.933 s** | 6.240 s | **0.630** |
| Warm range | 3.917–4.095 s | 6.240 s | **0.628–0.656** |

RTF is calculated as:

```text
RTF = generation time / generated audio duration
```

An RTF below 1 means generation is faster than real time. The warm median RTF of `0.630` means the phone generated audio at approximately **1.59× real-time speed** (`1 / 0.630`). The cold result was also faster than real time.

Model/session loading took `1.079 s` and is reported separately from generation.

## Tested configuration

| Item | Value |
|---|---|
| Phone | Samsung Galaxy S23 Ultra (`SM-S918B`) |
| SoC | Snapdragon 8 Gen 2 (`SM8550`) |
| Execution | Android CPU only |
| Threads | 1 |
| Runtime | ONNX Runtime 1.27.1 through sherpa-onnx 1.13.5 |
| Precision | Unquantized floating point |
| Flow steps per generated frame | 1 |
| Generated autoregressive frames | 78 |
| Sample rate | 24,000 Hz, mono |
| Test runs | 1 cold + 5 warm |

The five ONNX graphs total `439,484,422` bytes. The complete deployed model, auxiliary data, runtime libraries, and runner totaled approximately `468 MB`.

## Output audio

Representative WAV:

```text
/home/moritz/vibevoice-android-spike/experiments/0012-pocket-onnx-vs-executorch-android/work/pocket-fp-onnx-android-cpu.wav
```

SHA-256:

```text
40634981606f37c59a91c14d99cecb3ef4cc21b1391882e870940b0716857d22
```

Validation:

- 24 kHz mono PCM16
- 149,760 samples
- 6.24 seconds
- finite and non-silent
- peak PCM16 amplitude: 10,997
- RMS PCM16 amplitude: 757.48
- not clipped
- all six phone runs produced byte-identical WAVs

The WAV is intentionally stored under ignored `work/` rather than committed to Git.

## Model and ONNX provenance

The source was the exact public, ungated Pocket TTS snapshot already pinned by this repository:

- Official code: `kyutai-labs/pocket-tts` at `d108410d23eef7e01db282f9442891162dbc3db6`
- Official weight revision: `kyutai/pocket-tts-without-voice-cloning` at `d29db7978e464fb90cb3359ee0c69a273b9142cc`
- Model SHA-256: `be9c6b4876d3f30740a8225dfcaa2e43dc4aeb753c15272735bee16bbb4abb0a`

The Android files were controlled, derived ONNX exports of those exact weights—not third-party graphs merely assumed to match. The five components were the text conditioner, recurrent FlowLM main graph, stateless flow step, Mimi encoder, and Mimi decoder. Stateful caches were explicit graph inputs and outputs, while the actual autoregressive and flow loops remained in the runtime orchestration.

Component equivalence tests passed. A deterministic source-versus-ONNX end-to-end fidelity check produced equal-length audio with correlation `0.9999999229` and SNR `68.119 dB`. Therefore, this is a faithful derived ONNX deployment, though the ONNX files themselves should not be called the original model weights.

## Memory caveat

The maximum observed process `VmHWM` was `1,586,080 kB` (about 1.51 GiB). This is a cumulative process-lifetime high-water value. It includes mapped runtime and model files, recurrent caches, working buffers, and output audio; it is not isolated weight or tensor memory.

The measurements were sequential and did not use laboratory thermal stabilization or fixed CPU frequencies, so normal phone DVFS and thermal variation remain limitations.

## ExecuTorch status

ExecuTorch did **not** produce a runnable complete model. Two small boundaries exported, but the required recurrent FlowLM and Mimi decoder failed strict `torch.export` because of data-dependent guards in their stateful attention/cache path. That does not affect the successful ONNX result described above.

## Evidence

- Machine-readable measurements: [`results/comparison.json`](results/comparison.json)
- Source/export provenance: [`provenance/source-and-export.json`](provenance/source-and-export.json)
- ExecuTorch blocker: [`provenance/executorch-screen.json`](provenance/executorch-screen.json)
- Predeclared protocol: [`protocol.json`](protocol.json)

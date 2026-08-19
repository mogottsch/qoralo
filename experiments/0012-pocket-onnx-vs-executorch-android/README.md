# 0012 — Pocket TTS: FP ONNX Runtime vs ExecuTorch on Android CPU

> **Working result:** FP ONNX succeeded on Android CPU with a warm median **RTF of 0.630**. See [`RESULTS.md`](RESULTS.md) for the concise result and latency table.

## Purpose

Compare two non-quantized CPU deployment routes for the same repository-pinned Pocket TTS checkpoint on the authorized Samsung S23 Ultra. This experiment stops before HTP, QNN, quantization, or accelerator probing.

## Exact source contract

- Official code: `kyutai-labs/pocket-tts` at `d108410d23eef7e01db282f9442891162dbc3db6` (MIT).
- Official public, ungated weight snapshot: `kyutai/pocket-tts-without-voice-cloning` at `d29db7978e464fb90cb3359ee0c69a273b9142cc` (CC-BY-4.0).
- Model: `languages/english/model.safetensors`, SHA-256 `be9c6b4876d3f30740a8225dfcaa2e43dc4aeb753c15272735bee16bbb4abb0a`.
- Tokenizer: `languages/english/tokenizer.model`, SHA-256 `d461765ae179566678c93091c5fa6f2984c31bbe990bf1aa62d92c64d91bc3f6`.
- Retained official state evidence: `languages/english/embeddings/alba.safetensors`, SHA-256 `e4a323e8e771f14fd669428d83e7af6d83b4d6d0f0e282c30122f04824f17b1c`.
- Matched mobile voice input: packaged Bria reference WAV, SHA-256 `85f46d6f0642f657a6bd689ddaa52d5a5f53e4314715e1032704c80917392181`, from the pinned sherpa archive and attributed there to Kyutai's `delayed-streams-modeling` audio. The requested Alba source WAV became gated and was not accessed; Bria is never labeled Alba.

The snapshot was publicly retrievable without authentication or gate acceptance. The mutable gated `kyutai/pocket-tts` head is not used. Safetensors are original learned weights/state, not an Android-executable graph.

## Routes

### A — ONNX Runtime

Create a controlled unquantized floating-point export of five callable components: text conditioner, FlowLM recurrent/autoregressive main graph with explicit caches, stateless flow step, Mimi decoder with explicit streaming state, and Mimi encoder where the source checkpoint supports it. Keep autoregressive and flow loops in the deterministic host harness. Compare every exported component against its source callable before Android. A third-party ONNX graph is accepted only if its exact tensor/source provenance and numerical equivalence are proven.

### B — ExecuTorch

Use current `torch.export` and ExecuTorch. Screen the same callable component boundaries and explicit states. Narrow wrappers or decompositions are permitted only with source-equivalence tests. Unsupported data-dependent control flow, state mutation, dynamic shape constraints, or required custom kernels are recorded as blockers rather than hidden by model surgery. Deprecated TorchScript/PyTorch Mobile is forbidden.

## Matched generation and benchmark

`protocol.json` is normative and was predeclared before phone output. Both routes use the exact same text, pinned Bria reference, seed 0, temperature 0.3, one flow step, model-derived EOS tail, one CPU thread, 24 kHz mono output, and device identity. The route order is ONNX then ExecuTorch. Measure load/session creation, one cold complete generation, five warm complete generations, component and loop call counts/timing where observable, output duration, RTF, package size, and process memory high-water. Sequential runs carry route-order and thermal/DVFS caveats.

## Android safety

Phone work must hold `artifacts/locks/phone.lock`, close the lock FD in ADB children, use Windows `adb.exe` with `ADB_LIBUSB=1`, fail closed unless the sole device is `R5CW81PR8SY` / `SM-S918B`, stage only under a unique `/data/local/tmp/experiment-0012-*` path, pull experiment evidence, remove the remote staging path, and release the lock. No personal data is read.

## Claim boundary

Success requires complete text → tokenizer/conditioning → recurrent autoregressive and flow loop → Mimi decode → WAV on Android CPU. Neural intermediate fixtures do not count. A derived ONNX or `.pte` file is not called “the original model.” No result from this experiment proves HTP/QNN compatibility or performance.

## Outcome

- **FP ONNX Runtime: succeeded on Android CPU.** Five unquantized FP component graphs were exported from the exact checkpoint. Component tests passed; a deterministic temperature-zero fidelity isolation against the exact source produced equal-length audio with correlation `0.9999999229` and SNR `68.119 dB`. The production phone run retained temperature `0.3`, seed `0`, and one flow step.
- **ExecuTorch: blocked before Android.** The text conditioner and stateless flow step reached `.pte`, but strict current `torch.export` failed for both the recurrent FlowLM main graph and Mimi decoder on a data-dependent `Eq(u9, 0)` guard inside stateful scaled-dot-product attention. Both are essential. Replacing their attention/cache implementation would exceed a narrow decomposition and requires a separate equivalence campaign.

On the S23 Ultra, FP ONNX loaded in `1.079 s`; the first complete generation took `5.697 s` for `6.24 s` audio (`RTF 0.913`). Five warm generations had median `3.933 s` (range `3.917–4.095`) and median RTF `0.630` (range `0.628–0.656`). Cumulative process `VmHWM` reached `1,586,080 kB`. All six outputs were byte-identical, valid 24 kHz mono PCM16, finite, non-silent, and unclipped.

Representative WAV (ignored): `work/pocket-fp-onnx-android-cpu.wav`, SHA-256 `40634981606f37c59a91c14d99cecb3ef4cc21b1391882e870940b0716857d22`.

See `provenance/source-and-export.json`, `provenance/executorch-screen.json`, and `results/comparison.json` for provenance and limitations.

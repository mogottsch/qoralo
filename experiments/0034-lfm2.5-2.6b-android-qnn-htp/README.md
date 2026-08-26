# Experiment 0034: LFM2.5-2.6B Android QNN/HTP

## Status

**Blocked before conversion: neither installed QAIRT 2.49 nor current public Qualcomm artifacts/tooling provide an LFM2 QNN route. No compiled context, Android execution, or QNN/HTP result exists.**

This is a separate accelerator feasibility arm. It preserves `0029` viability evidence and does not touch the combined CPU/GPU work in `0033`.

## Exact support assessment

The official route identity remains the pinned LiquidAI Q4_K_M GGUF already reconstructed by `0029`: 1,674,455,040 bytes, SHA-256 `02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed`, GGUF architecture `lfm2`.

The cheapest possible installed-QAIRT paths both fail at the architecture-support gate:

- the direct GGUF builder supports llama, mistral, phi3, qwen2, qwen3, gemma, gemma2, and gemma3—not `lfm2`;
- the HTP factory has no `Lfm2ForCausalLM` dispatch;
- QAIRT ships no LFM Genie config and its release notes contain no LFM/Liquid support claim;
- Qualcomm's public Hugging Face organization and AI Hub Models v0.61.0 contain no LFM model recipe, quantized ONNX+encodings, or serialized QNN context.

LFM2 is not a Llama-shaped transformer that can safely use a generic fallback. The pinned 2.6B configuration has 22 convolutional state layers and 8 full-attention layers. Correct compilation and execution require model-specific convolutional-state and KV-state conversion, cache geometry, runtime orchestration, and reset proof. Implementing that would be a new converter/runtime project, which is outside current authorization.

Because architecture rejection is known before weights are read, downloading another copy of the already-bound 1.67 GB GGUF would provide no additional evidence and was avoided.

## Bound frontend contract

The pinned tokenizer and native template were independently reconstructed from the authorized `0029` source metadata. Canonical short/medium/long prompts contain 171/600/1922 tokens, each has exactly one BOS, ends at the model-native `<think>` generation continuation, and fits a 4096-token context with the 2048-token ceiling.

Exact hashes and support evidence are in [`protocol/experiment-contract.json`](protocol/experiment-contract.json) and [`results/support-assessment/result.json`](results/support-assessment/result.json).

## Exact unblock action

Moritz must choose one:

1. provide an authorized, provenance-bound LFM2.5-2.6B quantized ONNX+encodings input plus a model-specific QAIRT builder, or a complete SM8550/HTP v73 serialized-context runtime bundle;
2. authorize authenticated Qualcomm AI Hub/engineering support if a non-public LFM QNN route exists; or
3. authorize a separately bound updated QAIRT/toolchain or a new LFM2 converter/runtime implementation with host equivalence, recurrent-state reset, partition, and provider proofs.

No ADB was used. A phone viability gate and canonical campaign remain impossible until a compiled route exists and Pi grants phone priority.

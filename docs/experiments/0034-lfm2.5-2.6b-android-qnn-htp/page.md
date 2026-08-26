---
experiment: 0034-lfm2.5-2.6b-android-qnn-htp
status: blocked
summary: The LFM2.5-2.6B QNN/HTP arm is blocked before conversion because neither installed QAIRT 2.49 nor current public Qualcomm tooling provides an authorized LFM2 route.
benchmark: android-llm
---

# Experiment 0034 — LFM2.5-2.6B Android QNN/HTP

## Experiment description

This experiment asks whether LFM2.5-2.6B can run end to end through Qualcomm QNN on the Galaxy S23 Ultra's HTP. It is an independent accelerator feasibility arm: it preserves the bounded Android CPU viability result in experiment 0029 and does not alter the separate loaded-route CPU/Vulkan work assigned to experiment 0033. The intended result was a model-correct SM8550/HTP v73 compiled context, physical `QnnHtp` provider proof, a bounded phone viability gate, proven request-state isolation on one loaded route, and finally the canonical one-first-plus-five-short/five-medium/five-long campaign.

LFM2 cannot safely be treated as a renamed Llama-like transformer. The pinned 2.6B model has 22 convolutional-state layers and 8 full-attention layers. A credible route must handle both convolutional and KV state, establish the cache layout and reset behavior, and prove that the transformer graph executes on HTP rather than falling back to CPU.

The owning [experiment README](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/README.md), [experiment contract](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/protocol/experiment-contract.json), and [support assessment](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/support-assessment/result.json) bind the negative feasibility result and its exact limits.

## Progress

The route retained the official LiquidAI artifact identity already reconstructed by 0029: `LFM2.5-2.6B-Q4_K_M.gguf`, 1,674,455,040 bytes, SHA-256 `02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed`, with GGUF architecture `lfm2`. The tokenizer and native reasoning template were reconstructed independently. Canonical short/medium/long prompts contain 171/600/1922 tokens, each has one BOS, ends at the native `<think>` continuation, and fits a 4096-token context with the 2048-token ceiling.

The cheapest authorized QAIRT paths both fail at the architecture-support gate. QAIRT 2.49's direct GGUF builder supports several families but not `lfm2`; its HTP factory has no `Lfm2ForCausalLM` dispatch. The installed SDK also has no LFM Genie configuration or LFM/Liquid support statement. Qualcomm's public Hugging Face material and AI Hub Models v0.61.0 provide no LFM model recipe, quantized ONNX+encodings, or serialized QNN context.

Because architecture rejection is known before reading weights and the exact GGUF bytes are already bound, downloading another 1.67 GB copy would add no evidence and was avoided. Writing a generic fallback would actually begin a new model-specific converter and runtime project, including recurrent-state conversion and orchestration, which was not authorized.

## Results

**The route is blocked before conversion.** No authorized LFM2 QNN input, model-specific builder, or compiled SM8550 context exists. No ADB or phone work occurred, and no QNN/HTP execution or provider proof exists. As a result there is no setup, TTFT, prefill, decode, memory, thermal, power, output-sanity, or campaign evidence. The intended end-to-end target and canonical 1+5+5+5 campaign were not reached, so this experiment is not completed and has **no leaderboard row**.

A generic SM8550 compiler target does not prove model support. Mapping `lfm2` to Llama or Qwen, ignoring convolutional recurrent state, or citing CPU/Vulkan output as HTP execution would violate the architecture, isolation, and provider gates.

Continuation requires one explicit authorized input or toolchain decision from Moritz:

1. provide a provenance-bound LFM2.5-2.6B quantized ONNX+encodings input with a model-specific QAIRT builder, or a complete SM8550/HTP v73 serialized-context runtime bundle;
2. authorize authenticated Qualcomm AI Hub or engineering support if a non-public LFM QNN route exists; or
3. authorize a separately bound updated QAIRT/toolchain or a new LFM2 converter/runtime implementation, including host equivalence, convolutional/KV state-reset, partition, fallback, and provider proofs.

Until one of those paths is authorized and succeeds, this page records a durable phone-independent pre-conversion blocker with no context, Android, HTP, or performance claim.

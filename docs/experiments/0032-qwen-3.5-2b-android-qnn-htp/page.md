---
experiment: 0032-qwen-3.5-2b-android-qnn-htp
status: blocked
summary: The Qwen3.5-2B QNN/HTP arm is blocked before conversion because no authorized 2B QNN input exists and installed QAIRT's Qwen3.5 path is not dimension-compatible with this variant.
benchmark: android-llm
---

# Experiment 0032 — Qwen3.5-2B Android QNN/HTP

## Experiment description

This experiment evaluates a distinct QNN/HTP route for Qwen3.5-2B without changing the CPU evidence in experiment 0027. The intended end-to-end target was a provenance-bound SM8550/HTP v73 compiled context, physical `QnnHtp` provider proof on the Galaxy S23 Ultra, a bounded viability request, proven loaded-route isolation, and the canonical one-first-plus-five-short/five-medium/five-long campaign.

The assessment deliberately separates publicly available Qwen deployment artifacts from actual QNN conversion inputs. Qualcomm's public Qwen3.5-2B release currently identifies a GenieX llama.cpp Q4_0 GGUF. A GGUF advertised for that runtime is not automatically an ONNX/QNN graph or an HTP context, and published metrics from another route cannot be relabeled as this repository's provider evidence.

The owning [experiment README](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/README.md), [experiment contract](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/protocol/experiment-contract.json), and [support assessment](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/support-assessment/result.json) bind the exact feasibility finding.

## Progress

The route assessment pinned the official Qwen3.5-2B model revision and its hybrid architecture geometry. It also reconstructed the official tokenizer and template with thinking disabled. The canonical short/medium/long prompts contain 174/597/1926 tokens, fit the 4096-token route context with the 2048-token output ceiling, and have independently bound rendered-prompt and token-ID hashes.

The only unauthenticated public Qualcomm artifact found for this model is `Qwen3.5-2B-Q4_0.gguf`, 1,214,873,856 bytes with published SHA-256 `cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`, for the GenieX llama.cpp route. Installed QAIRT 2.49's direct GGUF builder does not support its `qwen35` architecture. Downloading 1.2 GB could not change that support-table result, so the unnecessary transfer was avoided.

QAIRT does have a separate `Qwen3_5ForConditionalGeneration` HTP factory dispatch, but that path requires a quantized ONNX graph plus encodings. Qualcomm AI Hub Models v0.61.0 publishes no Qwen3.5-2B model, export, or quantization implementation and no ONNX+encodings or serialized context. Moreover, the installed builder hardcodes a 4096-wide split point grouped by 256 while the official 2B geometry uses a 512-wide full-attention KV path and 2048-wide linear-key path. Borrowing the shipped 4B HTP example would therefore be unsupported.

## Results

**The route is blocked before conversion.** No authorized local QNN conversion input or compiled SM8550 context exists. No ADB or phone work occurred, and no QNN/HTP execution or provider proof exists. There is therefore no setup, TTFT, prefill, decode, memory, thermal, power, output-sanity, or campaign evidence. The intended end-to-end target and canonical 1+5+5+5 campaign were not reached, so this experiment is not completed and has **no leaderboard row**.

A GenieX llama.cpp release, the shipped 4B QNN example, or CPU-only text output cannot substitute for a physical 2B QNN/HTP route. Applying the dimension-specific 4B builder to the 2B model would weaken the architecture and provider gates rather than unblock them.

Continuation requires one explicit authorized input or toolchain decision from Moritz:

1. provide a provenance-bound Qwen3.5-2B quantized ONNX+encodings input compatible with installed QAIRT, or a complete serialized SM8550/HTP v73 context and runtime bundle;
2. authorize authenticated Qualcomm AI Hub Workbench use if it exposes a supported Qwen3.5-2B context export; or
3. authorize a separately bound updated QAIRT/toolchain or a 2B-aware converter implementation that adds `qwen35` GGUF support or corrects the ONNX builder dimensions, followed by independent equivalence and provider proof.

Until one of those routes is authorized and succeeds, this page records a durable phone-independent pre-conversion blocker and makes no context, Android, HTP, or performance claim.

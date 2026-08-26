---
experiment: 0031-gemma-4-e2b-it-android-qnn-htp
status: blocked
summary: The Gemma 4 E2B IT QNN/HTP arm is blocked before QNN conversion. Its public w4a16 input is hash-bound, but installed QAIRT 2.49 cannot transform the unchanged graph and no SM8550/HTP context exists.
benchmark: android-llm
---

# Experiment 0031 — Gemma 4 E2B IT Android QNN/HTP

## Experiment description

This experiment asks whether Gemma 4 E2B IT can run end to end through Qualcomm QNN on the Galaxy S23 Ultra's HTP. It is a separate accelerator arm and does not rewrite the CPU or GPU evidence owned by experiment 0025. The intended result was a provenance-bound SM8550/HTP v73 compiled context, physical `QnnHtp` provider proof, a bounded phone viability gate, proven loaded-route request isolation, and finally the canonical one-first-plus-five-short/five-medium/five-long campaign.

There was credible first-party route evidence to assess. Installed QAIRT 2.49.0.260730 includes a Gemma 4 HTP example, an Android Genie runner and QNN libraries, and support for the `chipset:SM8550` compile target. Qualcomm AI Hub Models also identifies a public calibrated w4a16 checkpoint. Those facts justify a conversion assessment, but they do not by themselves prove that this model converted, compiled, reached Android, or executed on HTP.

The owning [experiment README](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/README.md), [experiment contract](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/protocol/experiment-contract.json), and [support assessment](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/support-assessment/result.json) define the route and its proof boundary.

## Progress

The public `gemma_4_e2b_it_w4a16.zip` archive was downloaded under the heavy-RAM lock, passed ZIP integrity checks, and was bound at **2,013,959,998 bytes** with SHA-256 `ed45053c8582f2646fb8dd80e0d8f55a462394199160bade96401615b6ce84a7`. Its 9,119,006,720-byte external model data is fully covered by 724 ONNX initializer ranges. The archive also binds w4a16 encodings, tokenizer, template, and configuration. The selected tokenizer produces 170/594/1929 tokens for the canonical short/medium/long prompts; this arm correctly uses its own token-ID hashes rather than borrowing 0025's counts.

The direct-GGUF shortcut was rejected because QAIRT 2.49's support table includes Gemma through Gemma 3, not the artifact's `gemma4` architecture. A bounded transform-only probe instead targeted the unchanged public ONNX and encodings with AR1+AR128, CL4096, one unsplit graph, and no embedding or LM-head split. The high-level factory warned that Gemma4 was unknown or unsupported and selected its generic builder.

That smallest faithful probe failed during QAIRT ONNX shape inference and constant propagation with `KeyError('value')`, before AR/CL materialization, QNN conversion, or HTP compilation. Post-failure hashes confirm that the ONNX, external data, and encodings remained unchanged. The exact error, inputs, logs, and negative execution flags are bound in the [transform blocker result](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/transform-blocker/result.json) and its [checksum manifest](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/transform-blocker/SHA256SUMS).

## Results

**The route is blocked before QNN conversion.** No compiled SM8550 context was created, no Android or ADB work was performed, and no QNN/HTP execution occurred. Consequently there is no setup, TTFT, prefill, decode, memory, thermal, power, output-sanity, or campaign evidence to report. The intended end-to-end target and canonical 1+5+5+5 campaign were not reached, so this experiment is not completed and has **no leaderboard row**.

The presence of an HTP example, runtime libraries, and a generic SM8550 compiler target is not provider proof for this graph. Neither successful generic-builder construction nor a CPU response would establish transformer execution on HTP. Ad hoc graph rewriting and the unsupported Gemma4 GGUF route are also outside the accepted evidence boundary.

Continuation requires one explicit authorized input or toolchain decision from Moritz:

1. provide a provenance-bound Gemma4 E2B w4a16 serialized QNN context compiled for SM8550/HTP v73, with exact compiler/checkpoint provenance and matching token and per-layer embedding LUTs;
2. authorize authenticated Qualcomm AI Hub Workbench use if it currently offers a supported context export for this checkpoint and target; or
3. authorize a separately bound updated QAIRT/toolchain or architecture-aware converter fix that supports the unchanged public graph.

Until one of those paths is authorized and succeeds, the honest result remains a durable pre-conversion blocker with no context, Android, HTP, or performance claim.

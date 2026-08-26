# Experiment 0031: Gemma 4 E2B IT Android QNN/HTP

## Status

**Blocked before QNN conversion. The public w4a16 checkpoint is fully hash-bound, but installed QAIRT 2.49 cannot transform its Gemma4 graph and no SM8550 compiled context exists. No Android or HTP execution result exists.**

This experiment is a separate HTP arm for the model studied in `0025`. It does not rewrite or relabel the CPU/GPU evidence there.

## Selected route

The already-installed `/home/moritz/opt/qairt/2.49.0.260730` contains unusually strong first-party support evidence:

- its release notes explicitly add the Gemma 4 family;
- it ships a Gemma 4 E2B Genie configuration with `backend.type = QnnHtp`;
- that configuration names one weight-sharing AR128/AR1, CL8192 serialized context and separate embedding/per-layer-embedding LUTs;
- its compiler API explicitly supports `chipset:SM8550` (HTP v73);
- it contains the Android Genie runner and QNN/HTP runtime libraries.

Qualcomm AI Hub Models v0.61.0 identifies a calibrated w4a16 checkpoint archive in its public model-asset store:

```text
https://qaihub-public-assets.s3.us-west-2.amazonaws.com/qai-hub-models/models/gemma_4_e2b_it/v1/gemma_4_e2b_it_w4a16.zip
```

The archive was downloaded and inspected while holding `artifacts/locks/heavy-ram.lock`: 2,013,959,998 bytes, SHA-256 `ed45053c8582f2646fb8dd80e0d8f55a462394199160bade96401615b6ce84a7`. ZIP integrity passed. Its 9,119,006,720-byte `model.data` is exactly covered by 724 external initializer ranges from `model_dynamic.onnx`; the archive also binds w4a16 encodings, tokenizer, template, and configuration. See [`results/checkpoint-analysis/result.json`](results/checkpoint-analysis/result.json).

The selected tokenizer produces 170/594/1929 tokens for short/medium/long. Rendered prompt bytes match the prior Gemma route, but token IDs do not; this experiment binds its own tokenizer hashes and does not reuse 0025 token counts.

## Rejected shortcut

The newer public Google Q4_0 GGUF identifies `general.architecture=gemma4`. QAIRT 2.49's direct GGUF-to-HTP support table contains Gemma, Gemma 2, and Gemma 3 but not Gemma 4. Treating that route as supported would weaken the provider and architecture gates, so it is rejected.

## Exact conversion blocker

A bounded, lock-protected support probe resolved `chipset:SM8550` to HTP v73, but QAIRT's high-level GenAI factory has no `Gemma4ForConditionalGeneration` dispatch and returned its generic builder with an explicit unsupported-architecture warning. With the public checkpoint left unchanged and only a copied encoding file supplied, the smallest faithful transform request—AR1+AR128, CL4096, one unsplit graph, no embedding or LM-head split—failed before QNN conversion:

```text
ShapeInference → ConstantPropagation → visit_node_Constant
→ get_constant_np → producer.attributes["value"]
KeyError: 'value'
```

No conversion or compilation was requested after this exact unsupported-graph failure. Post-failure hashes prove that ONNX, external data, and encodings remained unchanged. See [`results/transform-blocker/result.json`](results/transform-blocker/result.json) and the retained raw logs.

Continuing requires one explicit user decision:

1. provide an authorized, provenance-bound Gemma4 E2B w4a16 serialized context compiled for SM8550/HTP v73 plus token and per-layer embedding LUTs;
2. authorize authenticated Qualcomm AI Hub Workbench use if it currently exposes a supported QNN context export for this checkpoint/target; or
3. authorize a separately bound updated QAIRT/toolchain or architecture-aware converter fix.

Ad hoc graph rewriting, a CPU response, or the unsupported Gemma4 GGUF route is not an acceptable workaround.

## Proof boundary

A text response alone will not count as HTP evidence. Before a phone run, this experiment must bind:

1. public checkpoint and every generated artifact by size and SHA-256;
2. SM8550/HTP compilation metadata for the serialized context;
3. exact tokenizer, model-native template, rendered prompt, and token IDs for all tiers;
4. a runtime `QnnHtp` configuration and physical HTP host/stub/v73 skeleton/profile evidence;
5. a complete transformer-graph acceptance boundary with no QNN CPU backend or undocumented transformer fallback.

Tokenizer/template rendering, LUT lookup or requantization, greedy sampling, detokenization, and host orchestration are expected CPU-side boundaries and will remain explicit.

After a bounded viability gate, a canonical campaign is permitted only with one loaded route and proven request isolation. Phone/ADB work requires Pi's explicit priority handoff and `phone.lock` for the entire lifecycle.

Machine-readable details are in [`protocol/experiment-contract.json`](protocol/experiment-contract.json) and [`results/support-assessment/result.json`](results/support-assessment/result.json).

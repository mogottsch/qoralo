# Experiment 0031: Gemma 4 E2B IT Android QNN/HTP

## Status

**Active after SM8550/HTP v73 compilation and before phone staging. The unchanged public w4a16 checkpoint now yields static AR1 and AR128, CL4096 variants, two HTP-targeted DLCs, and one weight-shared serialized context. Official context metadata binds QNN HTP backend ID 6 and both graphs; embedded compiler markers bind SM8550/architecture 73. No Android loading, physical HTP execution, generated text, or performance result exists yet.**

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

## Historical conversion blocker and active route

A bounded, lock-protected support probe resolved `chipset:SM8550` to HTP v73, but QAIRT's high-level GenAI factory has no `Gemma4ForConditionalGeneration` dispatch and returned its generic builder with an explicit unsupported-architecture warning. With the public checkpoint left unchanged and only a copied encoding file supplied, the smallest faithful transform request—AR1+AR128, CL4096, one unsplit graph, no embedding or LM-head split—failed before QNN conversion:

```text
ShapeInference → ConstantPropagation → visit_node_Constant
→ get_constant_np → producer.attributes["value"]
KeyError: 'value'
```

No conversion or compilation was requested after this exact unsupported-graph failure. Post-failure hashes prove that ONNX, external data, and encodings remained unchanged. See [`results/transform-blocker/result.json`](results/transform-blocker/result.json) and the retained raw logs.

Moritz has now authorized the third route. Qualcomm Package Manager access and the `Qualcomm_AI_Runtime_SDK` license are active; QAIRT 2.49.40 was acquired as a 2,410,405,384-byte QIK with SHA-256 `ef4a63b81c9b3a42b8c23921a322754b2fa15f7ef5737c85911d4c527c1fdb0c` and extracted outside Git. The factory and implicated optimizer sources are byte-identical to 2.49.0, while selected Android Genie/QNN/HTP runtime binaries changed. See [`results/qairt-2.49.40-capability/result.json`](results/qairt-2.49.40-capability/result.json).

The bounded compatibility route now passes. It handles the checkpoint's four standards-valid `Constant(value_ints=...)` nodes, seeds Gemma4-specific axes, materializes exact SWA cache/mask widths, and propagates the shape-preserving `Reciprocal` operation. Under `heavy-ram.lock`, QAIRT emitted two static one-split variants:

- AR1/CL4096 ONNX SHA-256 `9f3077b4a8ccec48781843f6391bb9d77bf4d0c2578a864c108a916b24c9e472`;
- AR128/CL4096 ONNX SHA-256 `d1171990305f50e89076709dcf024056f66393a90d35a79e774dc5612b0e3a9a`.

Both pass the ONNX checker with static graph inputs/outputs, their transformed external data is hash-bound, and source ONNX/data/encodings remain unchanged. See [`results/qairt-2.49.40-transform-compat/result.json`](results/qairt-2.49.40-transform-compat/result.json).

Both transformed variants now pass QNN conversion:

- AR1 DLC: 2,356,831,668 bytes, SHA-256 `02a790601b561a9ebb122c3101b916dfe8e3496435eee08a514237112a57ff68`;
- AR128 DLC: 2,356,851,284 bytes, SHA-256 `5f17ece8a99cd649abdadb61e2e104e5cd569a1d1735e9e6ecb5c297286156ee`.

`qairt-dlc-info` reports `backend=HTP`, 2,280,676,608 parameters, and the intended integer encodings. It also retains an important mixed-precision boundary: the converter reports 15 RmsNorm float fallbacks per variant; AR1 exposes 15 value-cache outputs as Float16 while AR128 exposes all outputs as uFxp16. See [`results/qairt-2.49.40-qnn-conversion/result.json`](results/qairt-2.49.40-qnn-conversion/result.json). This is conversion evidence, not physical provider proof.

Both DLCs now compile together in QAIRT weight-sharing mode. The resulting 1,186,349,056-byte context has SHA-256 `b8c169cedf9a00dde67e2e555805b1a773cb6fd128f5c3912a684c371f4af95a`. `qnn-context-binary-utility` reports build `v2.49.40.260810104044`, QNN HTP backend ID 6, and exactly two graphs (`ar1_cl4096_1_of_1`, `ar128_cl4096_1_of_1`), each with 38 inputs and 31 outputs. The binary also contains `soc_type=SM8550`, `arch=73`, and `native_hmx_a16w4=true`. See [`results/qairt-2.49.40-sm8550-context/result.json`](results/qairt-2.49.40-sm8550-context/result.json).

This is host AOT/context evidence, not physical provider proof. The exact next gate is generating and binding the matching token/per-layer embedding LUTs and Genie `QnnHtp` configuration. Phone staging remains queued behind explicit priority and `phone.lock`. Workbench compile/link remains a separate unapproved cost/terms checkpoint. Ad hoc checkpoint graph rewriting, a CPU response, or the unsupported Gemma4 GGUF route is not acceptable.

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

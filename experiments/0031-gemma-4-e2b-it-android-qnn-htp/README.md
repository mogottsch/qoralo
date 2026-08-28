# Experiment 0031: Gemma 4 E2B IT Android QNN/HTP

## Status

**The canonical physical QNN HTP campaign is complete. One verified SM8550 QnnHtp process loaded the corrected context once and completed one first short plus five warm short, five medium, and five long requests with exact prompts, 2048 ceilings, and 15 source-proven full resets. All 15,275 QnnDsp graph completions returned status 0 with no QNN CPU/runtime-fallback marker. Short and medium outputs pass the narrow sanity check; all long outputs hit 2048 tokens and fail sanity for severe repetition collapse. Performance evidence is valid, but this is not a quality-acceptance claim.**

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

## Conversion history and active route

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

This is host AOT/context evidence, not physical provider proof.

The private runtime bundle is now complete. From the pinned ungated Apache-2.0 QAT checkpoint, the host tooling unpacks Google/Hugging Face's low-bits-first signed INT2 token and INT4 PLE tables, applies their per-row/per-block scales and Gemma architectural embedding scales, then requantizes to the uint8 LUT form consumed by the QAIRT Gemma4 example:

- token LUT: 402,653,184 bytes, SHA-256 `3b55bb6bf947bf6a26056a25bc19a50564047c550b64c0d5f505a478cdb64239`;
- PLE LUT: 2,348,810,240 bytes, SHA-256 `bc5f25db058421efa5ac9cd38f9cd74e250e286ab4f6fe094c134a997dc29fa4`.

Deterministic sampled reconstruction stays within half of one uint8 quantization step. The bundle binds those LUTs, the compiled context, exact tokenizer, QAIRT 2.49.40 Genie/QNN/HTP/v73 libraries, a CL4096 configuration, and greedy 2048-token ceiling. See [`results/gemma4-sm8550-runtime-bundle/result.json`](results/gemma4-sm8550-runtime-bundle/result.json).

## First physical gate and exact blocker

The first authorized 16-token short-prompt gate held `phone.lock`, verified all staged hashes, and cleaned its experiment-specific remote path. It exited 139 during `dialog create`. Raw logs show:

- `QnnHtp` configuration parsed and both AR1/AR128 graphs discovered;
- exact SWA mappings AR1/513 and AR128/640;
- physical SM8550 detected;
- HTP provider, QNN backend/device, v73 stub, and first QNN stub connection initialized;
- backend-extension load failed because `libQnnHtpNetRunExtensions.so` was absent;
- no query, graph execution, generated output, or profile occurred.

See [`results/android-qnn-physical-viability-attempt-01/result.json`](results/android-qnn-physical-viability-attempt-01/result.json). The scoped remote path is verified absent after cleanup.

The missing QAIRT 2.49.40 Android extension is now included (1,091,656 bytes, SHA-256 `e25a816d008b3d342d1e52eaebef6748194f194aea3154049ab3692004f704ae`) and both stage preparation and execution scripts fail closed if any required runtime dependency is absent.

The one authorized corrected retry then loaded the extension, initialized the physical HTP provider/backend/device, and deserialized the weight-shared context. Genie stopped before dialog/query with 30 `Non-identical quantization parameters` errors: the 15 AR1 value-cache outputs are Float16, while the corresponding AR128 value-cache inputs and outputs are uFxp16. An empty profile was retained, no graph execution or output occurred, and scoped cleanup passed. See [`results/android-qnn-physical-viability-attempt-02/result.json`](results/android-qnn-physical-viability-attempt-02/result.json).

The host-side blocker is now corrected without changing the checkpoint or weakening Genie validation. The correction adds a schema-standard ONNX float fork and `QuantizeLinear` boundary at each of the 15 public AR1 value-cache outputs, using the already-bound QAT scale and uint16 zero point 32768 (QNN offset -32768). QNN conversion retains all 2,280,676,608 parameters and all 31 outputs; every output is now uFxp16. The resulting 1,186,369,536-byte weight-shared context has SHA-256 `a1d52d0087a0719d5907a98d99e8bc5996b699c9cf8f3a21b301588b9f51cc44`. `qnn-context-binary-utility` identifies QNN HTP backend ID 6, SM8550/v73 markers, both 38-input/31-output graphs, and 15 value-cache contracts whose AR1 input/output and AR128 input/output datatype, scale, and offset signatures are exactly identical. See [`results/qairt-2.49.40-cache-quantization-correction/result.json`](results/qairt-2.49.40-cache-quantization-correction/result.json).

The boundary is compiled inside the HTP-targeted graph; it is not a host CPU cache conversion. QAIRT still reports float-precision component fallbacks around affected normalization paths, so this is not a uniform-integer claim. More importantly, host compilation does not prove physical context acceptance or execution.

The private runtime bundle and phone stage are now rebuilt around the corrected context. The stage reuses the exact tokenizer, source-derived LUTs, QnnHtp runtime dependencies, canonical short prompt, and 16-token viability ceiling; all manifest hashes, `SHA256SUMS`, required dependencies, and restrictive permissions pass. Stage preparation used no ADB and did not acquire `phone.lock`. See [`results/cache-corrected-phone-stage/result.json`](results/cache-corrected-phone-stage/result.json).

The one authorized cache-corrected physical gate then held `phone.lock` for the full ADB lifecycle and passed device identity, local/remote stage hashes, and runtime completeness. On physical SM8550, the extension loaded, QNN HTP provider/backend/device and v73 stub initialized, and the corrected two-graph context deserialized. The prior 30 `Non-identical quantization parameters` errors were absent, physically confirming that the cache-contract correction cleared that validation blocker.

Genie next reported the context inputs `position_ids_global_cos` and `position_ids_global_sin` as unconnected, searched for missing `position_ids_cos` and `position_ids_sin`, and failed with `Could not find I/O tensors in loaded graphs`. Dialog creation failed; the later scripted query targeted a nonexistent dialog. The retained profile has null components, no output was created, no graph execution occurred, and scoped cleanup verified the remote path absent with no residual process. See [`results/android-qnn-physical-viability-attempt-03/result.json`](results/android-qnn-physical-viability-attempt-03/result.json).

The positional binding is now corrected without numerical graph changes: both transformed variants rename only `position_ids_global_cos/sin` to `position_ids_cos/sin` in graph inputs and their activation-encoding records. The rebuilt full DLCs retain 2,280,676,608 parameters and 31/31 uFxp16 outputs:

- AR1: 2,356,847,508 bytes, SHA-256 `f080cce522588baadcea38444b480038198918cd8a580dee1026591d638aa044`;
- AR128: 2,356,851,164 bytes, SHA-256 `23a27a84529990adeda07b9b81cc0dd7d360b396d48233e37170f4e62a2c0759`.

The resulting 1,186,369,536-byte weight-shared context has SHA-256 `7739ce5278dbe77117c879602f15e1e62460c88a9adf2dbcf10abb47dd61d394`. Official metadata identifies QNN HTP backend ID 6, SM8550/v73, both 38-input/31-output graphs, the exact global and SWA positional names expected by the unchanged Genie configuration, and all 15 four-way value-cache signatures still identical. See [`results/qairt-2.49.40-position-id-binding-correction/result.json`](results/qairt-2.49.40-position-id-binding-correction/result.json).

The private runtime bundle and 16-token stage were rebuilt and fully hash/permission/dependency verified around this context without ADB or `phone.lock`. See [`results/position-id-corrected-phone-stage/result.json`](results/position-id-corrected-phone-stage/result.json).

The one authorized attempt-04 gate then completed under the full `phone.lock` lifecycle. Physical evidence includes QnnHtp-only configuration, SM8550 detection, v73 stub connection, corrected context deserialization, successful graph switching, two `ar128_cl4096_1_of_1` executions and fifteen `ar1_cl4096_1_of_1` executions finishing with result/status 0, and no QNN CPU-backend or runtime-fallback marker. Genie produced 16 tokens and an 82-byte coherent text fragment. The bounded profile reports 1,900,166 µs initialization, 522,527 µs TTFT, 327.332 prompt tokens/s, and 17.572 generated tokens/s; these are viability observations, not canonical campaign metrics. Scoped cleanup verified the remote path absent with no residual process. See [`results/android-qnn-physical-viability-attempt-04/result.json`](results/android-qnn-physical-viability-attempt-04/result.json).

The same run exposed a fatal canonical-input mismatch. The committed route inventory binds a 170-token rendering with one leading BOS, while Genie reports 171 prompt tokens and its truncated token log begins `[2, 2, 105, ...]`; after the extra first token, the logged prefix matches the bound token sequence. This proves one automatic BOS was added at runtime.

The host correction now uses `bos-token: -1`, a supported QAIRT sentinel. Hash-bound QAIRT 2.49.40 source parses negative BOS and the LUT encoder prepends only when the configured value is nonnegative; shipped example/documentation evidence also uses `-1` to suppress the prefix. With that branch disabled, the pinned tokenizer reproduces the committed 170-token file byte-for-byte from unchanged rendered prompt bytes, beginning with exactly one token ID 2. The context, tokenizer, model, workload, and generated artifacts are otherwise unchanged. See [`results/genie-automatic-bos-suppression/result.json`](results/genie-automatic-bos-suppression/result.json).

The private bundle and 17-file 16-token stage were rebuilt and fully hash/permission/dependency verified with `bos-token: -1`; preparation used no ADB or `phone.lock`. See [`results/canonical-bos-corrected-phone-stage/result.json`](results/canonical-bos-corrected-phone-stage/result.json).

The one authorized attempt-05 confirmation then succeeded under the full lock/hash/provider/raw-output/cleanup lifecycle. Genie reports exactly 170 prompt tokens. Its fixed-size verbose line truncates mid-number after 157 complete tokens, but both logged sequences begin `[2, 105, 9731, ...]` and match the committed token IDs through every complete token, with exactly one leading BOS. Physical QnnDsp evidence records two successful AR128 prompt calls and fifteen successful AR1 decode calls, all status 0, with no QNN CPU-backend or runtime-fallback marker. The 16-token coherent output has SHA-256 `70711436da1fba6f0b7d869c319f8d97c0819d36affbd369e119c1c3f04d6357`. The bounded profile reports 2,095,134 µs initialization, 528,217 µs TTFT, 321.854 prompt tokens/s, and 17.703 generated tokens/s. Scoped cleanup verified the remote path absent and no process remained. See [`results/android-qnn-physical-viability-attempt-05/result.json`](results/android-qnn-physical-viability-attempt-05/result.json).

This physically clears the effective-input blocker, but it does not retroactively turn the max16 gate into a canonical request. No 2048-ceiling first/warm campaign, isolation distribution, or registry row exists.

The host-only campaign harness is now prepared. It enables QAIRT's `shared-engine` mode and creates an unqueried keeper dialog so the Registry-backed HTP engine remains alive for the entire process. Each of the 16 logical requests creates a fresh dialog with a source-proven independent `EngineState`, applies that state before query, writes a unique raw output and profile, then frees the dialog while the keeper retains the loaded engine. The fixed order is first short, five warm short, five warm medium, and five warm long, all with exact rendered prompt hashes and 2048 ceilings. A monitor records memory and enforces the 1,800-second per-request timeout by terminating the process without retry; post-run validation will classify every retained request independently. The runner also fail-closes on explicit approval, device identity, `phone.lock`, local/remote hashes, dependencies, and scoped cleanup. See [`results/canonical-campaign-harness-readiness/result.json`](results/canonical-campaign-harness-readiness/result.json).

All private campaign-stage hashes and permissions pass. The initially approved launch nevertheless exited locally with code 126 before the runner body because `run_phone_campaign.sh` was committed as mode `100644`. No lock, ADB, remote root, process, request, output, or profile existed, so this is a host launcher preflight failure rather than a phone/campaign attempt. The runner is now mode `100755`, the readiness analyzer and tests assert executability, and the campaign design/scope remain unchanged. See [`results/canonical-campaign-launch-preflight/result.json`](results/canonical-campaign-launch-preflight/result.json).

After renewed approval, physical campaign attempt 01 passed device identity, local/remote hashes, dependency checks, stage push, and process launch under `phone.lock`. It then failed before HTP provider initialization or context loading. QAIRT's shared-engine extraction moved the full dialog engine object into standalone Engine validation, where `cache-groups` is not accepted. The keeper plus all 16 request dialog creations failed with that exact error; no `GenieDialog_query`, QNN graph execution, or logical request began. The setup profile and all 16 request profiles have null components, no outputs exist, and scoped cleanup verified the remote path absent with no residual process. See [`results/android-qnn-physical-campaign-attempt-01/result.json`](results/android-qnn-physical-campaign-attempt-01/result.json).

No retry was authorized from that failure. Host analysis found that stock standalone Engine schema cannot carry Gemma's two dialog-level cache groups, so the corrected harness uses the protocol's alternative isolation strategy rather than weakening the cache contract: one normal, already-proven QnnHtp dialog/context remains loaded for all requests, and `dialog reset` runs before every request after the first. Hash-bound QAIRT source proves reset zeros past/prompt/generated/decode/query counters, clears last and unprocessed tokens/embeddings, calls HTP engine reset to drop KV and reset model state, resets sampler/grammar/Harmony state, and clears dialog state. The single-dialog configuration retains both `past_` and `swa_` cache groups.

The rebuilt script contains one dialog create/free, 16 exact first+5/5/5 queries, 15 resets, 2048 ceilings, unique raw outputs, and cumulative profile snapshots after each request. Reset durations will be extracted separately from verbose API timestamps; query durations remain in profile events. The timeout/raw/lock/hash/cleanup runner is unchanged. All private stage hashes and modes pass without ADB. See [`results/canonical-campaign-reset-harness-readiness/result.json`](results/canonical-campaign-reset-harness-readiness/result.json).

The authorized reset-isolated campaign then completed successfully under the full `phone.lock`, hash, raw-capture, thermal, and cleanup lifecycle. The context deserialized exactly once; one dialog served all 16 requests; 15 reset API calls completed; all cumulative profile snapshots grew by exactly one query event. Physical logs contain 117 successful AR128 and 15,158 successful AR1 completions, totaling 15,275 status-0 QnnDsp executions, with zero QNN CPU-backend, runtime-fallback, or fatal validation markers.

The first short request produced 474 tokens. All five warm short requests produced 474 tokens and had median TTFT 462,433 µs, prefill 367.647 tokens/s, and decode 19.584 tokens/s. All five medium requests produced 418 tokens and had median TTFT 907,551 µs, prefill 654.879 tokens/s, and decode 18.774 tokens/s. All five long requests reached the 2,048-token ceiling and had median TTFT 2,605,519 µs, prefill 740.741 tokens/s, and decode 17.828 tokens/s. Setup initialization was 2,111,957 µs. Peak sampled process PSS was 344,201 kB and VmHWM was 460,200 kB; HTP-private memory remains unreported.

Every greedy output was byte-identical within its tier. Short and medium exact outputs pass the narrow sensible-text check. The long exact output fails it: it collapses into severe repetition through the max-token ceiling. This is a required disclosed output-sanity failure, not grounds to discard valid execution/performance evidence. Battery moved from 58%/35.7°C to 52%/44.0°C while USB-powered; thermal status moved from 0 to 4, with final skin 49.0°C and AP 57.1°C. Cleanup verified the remote path absent and no process remained.

The original 399,795,157-byte provider log is hash-bound and retained losslessly as a deterministic 7.1 MB gzip alongside all profiles and outputs. See [`results/android-qnn-physical-campaign-attempt-02/result.json`](results/android-qnn-physical-campaign-attempt-02/result.json). After independent review, Kate may normalize registry rows with the long-output sanity failure and thermal/memory limitations preserved. This is execution/performance evidence, not correctness, grounding, usefulness, or quality acceptance. Workbench compile/link remains a separate unapproved cost/terms checkpoint.

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

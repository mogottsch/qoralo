# Plan: Gemma 4 E2B IT QNN/HTP

## Completed

1. Re-read the Android LLM protocol and verified all canonical workload hashes.
2. Kept `0025` immutable and established independent `0031` ownership.
3. Bound the already-installed QAIRT 2.49 SDK manifest, release notes, Gemma4 HTP example, Android Genie runtime, and QNN HTP library hashes.
4. Confirmed first-party Gemma 4 support, `QnnHtp`, serialized-context, CL8192, and SM8550 compile-target evidence.
5. Pinned Qualcomm AI Hub Models v0.61.0 at commit `5975a79b55b40f5cbc61f3ac5e52abe47d9d8bd5`.
6. Located the unauthenticated public 2,013,959,998-byte w4a16 checkpoint archive.
7. Rejected the direct GGUF shortcut because installed GGUF conversion does not support the artifact's `gemma4` architecture.

## Completed artifact and conversion gates

1. Acquired `artifacts/locks/heavy-ram.lock` and held it across the full checkpoint download, integrity test, extraction, and member hashing.
2. Bound the 2,013,959,998-byte archive, its 9.1 GB external data relationship, w4a16 encodings, source revision, tokenizer, template, and canonical 170/594/1929-token prompt inventories.
3. Created an isolated local QAIRT environment without altering system tooling or accepting another license.
4. Ran the smallest faithful QAIRT support probes under `heavy-ram.lock`:
   - the factory resolved SM8550 to HTP v73 but identified Gemma4 as unknown/unsupported and used a generic builder;
   - the transform-only AR1+AR128, CL4096, one-graph probe failed in ONNX ConstantPropagation with `KeyError('value')` before conversion or compilation;
   - post-failure hashes proved that ONNX, external data, and encodings remained unchanged.
5. Stopped at the exact unsupported-graph blocker. No context binary, Android execution, or HTP claim was fabricated.

## Authorized active gate

Moritz selected the updated local-toolchain/source-fix route. Completed authorization work:

1. established durable authenticated Qualcomm AI Hub and QPM catalog access without committing credentials;
2. personally activated the `Qualcomm_AI_Runtime_SDK` license;
3. acquired and privately extracted QAIRT 2.49.40 outside Git; and
4. bound its QIK, SDK manifest, selected converter sources, Gemma4 configuration, Android Genie runtime, QNN HTP host/stub, and v73 skeleton hashes in `results/qairt-2.49.40-capability/`.

QAIRT 2.49.40 did not itself remove the prior failure: the factory and implicated optimizer sources are byte-identical to 2.49.0. The isolated compatibility route now passes the bounded transform-only gate. It binds standards-valid `value_ints` constants, Gemma4 input-axis semantics, exact SWA cache/mask widths, and shape-preserving Reciprocal propagation without changing the checkpoint. AR1 and AR128 CL4096 one-split ONNX+encodings outputs pass static-IO and ONNX checks and are hash-bound in `results/qairt-2.49.40-transform-compat/`.

QNN conversion now passes for both variants, producing hash-bound AR1 and AR128 DLCs. `qairt-dlc-info` binds their HTP converter configuration, 2,280,676,608-parameter graph, operator inventory, I/O encodings, and mixed-precision boundary. The converter reports 15 RmsNorm float fallbacks per variant; AR1 has 15 Float16 value-cache outputs while AR128 outputs remain uFxp16. These are retained facts to validate at compile/runtime, not a CPU-provider claim.

Weight-shared compilation now passes. One hash-bound serialized context contains AR1 and AR128 graphs; official metadata binds QNN HTP backend ID 6 and the exact QAIRT build, while embedded compiler markers bind SM8550, architecture 73, and native HMX a16w4. This remains host AOT evidence only.

The private runtime bundle is now complete. The pinned ungated Apache-2.0 QAT safetensors is hash-bound; its packed INT2 token and INT4 PLE embeddings are unpacked with the authoritative Google/Hugging Face formula, scaled, and block-streamed into uint8 LUTs. Deterministic sampled dequantization is within half a quantization step. The manifest binds both LUTs, context, tokenizer, greedy CL4096 config, Genie binary, and QNN HTP host/stub/v73 skeleton libraries.

The first authorized bounded phone gate held `phone.lock`, verified local/remote stage hashes, and cleaned its scoped remote path. It reached physical SM8550 QNN HTP provider/backend/device initialization, loaded both context graphs and the v73 stub, then failed before query with exit 139 because the stage omitted `libQnnHtpNetRunExtensions.so`. No graph execution/output/profile occurred. Raw evidence is retained in `results/android-qnn-physical-viability-attempt-01/`.

The missing QAIRT 2.49.40 Android extension is now hash-bound in the bundle and stage. Preparation and execution both enforce an explicit required-runtime dependency list. The one authorized corrected retry loaded the extension and fully deserialized the two-graph weight-shared context on physical SM8550 HTP, but Genie model validation rejected 30 cross-variant value-cache entries before dialog/query: 15 AR1 value outputs are Float16 while corresponding AR128 cache inputs/outputs are uFxp16. No graph execution/output occurred; cleanup passed.

The host-side cache correction now passes. A schema-standard ONNX float fork plus `QuantizeLinear` boundary applies the source QAT uint16 scale/zero-point contract to all 15 public AR1 value-cache outputs without modifying checkpoint bytes or adding a host CPU boundary. The corrected DLC retains 2,280,676,608 parameters and 31/31 uFxp16 outputs. The rebuilt weight-shared SM8550/v73 context has QNN HTP backend ID 6, two 38-input/31-output graphs, and exact four-way datatype/scale/offset identity across every AR1-input/AR1-output/AR128-input/AR128-output value-cache contract. QAIRT still reports float-precision component fallbacks, so this is not a uniform-integer or physical-execution claim.

Pi independently reviewed and pushed the host correction. The private runtime bundle and stage are now rebuilt around the corrected context; all file hashes, `SHA256SUMS`, required runtime dependencies, and restrictive permissions pass. This preparation used no ADB and did not acquire `phone.lock`.

The one authorized corrected physical gate ran under the full `phone.lock` lifecycle. It passed identity, local/remote hashes, dependency completeness, QNN HTP provider/backend/device initialization, v73 stub connection, and corrected context deserialization. The prior 30 cache-quantization errors were absent. Genie then failed I/O discovery before dialog creation or graph execution: the context exposes `position_ids_global_cos/sin`, while the unprefixed positional configuration searches for `position_ids_cos/sin`. No output was created; profile components are null; scoped cleanup and process termination passed.

The global positional binding is now corrected host-side by a numerically identity graph-input and activation-encoding symbol rename in both AR variants. Both full DLCs retain 2,280,676,608 parameters and 31 uFxp16 outputs. Official metadata for the rebuilt SM8550/v73 context confirms both graphs expose `position_ids_cos/sin` plus `swa_position_ids_cos/sin`, all 15 cache contracts remain identical, and the unchanged Genie positional configuration's global/SWA name sets now match. The private bundle and 16-token stage are rebuilt and hash/permission/dependency verified without ADB or `phone.lock`.

The one authorized attempt-04 physical gate succeeded under `phone.lock`: verified SM8550 QnnHtp context deserialization, two successful AR128 prompt-graph executions, fifteen successful AR1 decode-graph executions, 16 generated tokens, coherent UTF-8 output, nonempty profile, scoped cleanup, and no QNN CPU-backend/runtime-fallback marker. This proves bounded physical HTP transformer inference but is not yet canonical campaign evidence.

The run revealed a fatal effective-prompt mismatch: the bound rendering has 170 tokens and one BOS, while Genie reports 171 prompt tokens and logs a `[2, 2, ...]` prefix whose tail matches the bound sequence.

The host correction now passes. Hash-bound QAIRT source parses negative `bos-token` and inserts an automatic BOS only for nonnegative values; shipped examples/documentation use `-1` as the suppression sentinel. The rebuilt config sets `bos-token: -1`, and the pinned tokenizer reproduces the exact committed 170-token single-BOS sequence byte-for-byte from unchanged rendered prompt bytes. The private bundle and 17-file stage are rebuilt and hash/permission/dependency verified without ADB or `phone.lock`.

The one authorized attempt-05 physical confirmation succeeded. Genie reports exactly 170 prompt tokens; both truncated runtime token logs begin with one BOS `[2, 105, 9731, ...]` and match the committed sequence through every complete logged token. Two AR128 and fifteen AR1 QnnDsp graph calls completed with status 0, no QNN CPU/runtime-fallback marker appeared, and Genie returned a coherent 16-token output. Cleanup and lock release passed.

The viability path is now proven through exact effective canonical short-input identity, but the run retained the explicitly bounded 16-token ceiling.

The host-only canonical harness is now prepared: one `genie-app` process, one Registry-backed shared HTP engine retained by an unqueried keeper dialog, and a fresh dialog/independent `EngineState` for each first+5/5/5 request. It binds exact prompt hashes, 2048 ceilings, unique per-request outputs/profiles, setup and fresh-dialog timings, per-request timeout monitoring, failure isolation, raw-first capture, memory/thermal evidence, and scoped cleanup. Source and stage hashes/permissions pass; no ADB was used.

The first approved launch exited locally with code 126 before entering the runner because `run_phone_campaign.sh` lacked executable mode. No `phone.lock`, ADB, remote root, Genie process, or logical request occurred; this is not a physical campaign attempt. The runner mode is corrected from `100644` to `100755`, and readiness/tests now assert executability without changing campaign design or scope.

After renewed approval, physical campaign attempt 01 entered the full locked phone lifecycle and passed identity, local/remote hashes, dependency completeness, and process launch. It failed before QNN provider/context/query because shared-engine extraction passed dialog-only `cache-groups` into standalone Engine validation. The keeper and all 16 request dialogs failed; all 17 profiles are null, zero logical requests started, no outputs exist, and cleanup passed.

Host source analysis shows standalone shared-engine schema cannot carry the two Gemma cache groups without the rejected dialog-only key. The corrected harness therefore uses the protocol's allowed full-reset strategy: one normal QnnHtp dialog/context remains loaded, with 15 `GenieDialog_reset` calls between the 16 requests. Hash-bound QAIRT source proves reset clears conversation/prompt/decode counters, last/pending inputs, HTP KV/model state, sampler, and dialog state without remapping. The rebuilt script retains both `past_` and `swa_` cache groups, exact first+5/5/5 order, 2048 ceilings, unique outputs, cumulative per-request profile snapshots, separate reset timestamps, timeouts, raw capture, and cleanup. Stage hashes/modes pass without ADB.

The authorized reset-isolated canonical campaign completed. One QnnHtp process/context/dialog served all 16 exact first+5/5/5 requests with 15 completed resets, cumulative profile growth, 2048 ceilings, and no errors/timeouts/retries. Physical evidence records 117 AR128 plus 15,158 AR1 status-0 QnnDsp completions, one context deserialization, zero QNN CPU/runtime-fallback markers, exact outputs/profiles, memory/thermal telemetry, and successful scoped cleanup.

Short and medium outputs pass the narrow sanity check. All long requests reach 2,048 tokens and produce the same severely repetitive output, so long output sanity is false with a required issue note. This does not erase valid execution/performance evidence and is not a quality verdict.

The active next gate is independent evidence review and Kate-owned registry normalization/publication with the long-output sanity failure and memory/thermal limitations preserved. No additional phone run is needed or authorized. Workbench compile/link remains a separate unapproved cost/terms checkpoint.

## Stop conditions

Stop and report the exact required action if the public checkpoint cannot be downloaded without authentication, local installed QAIRT cannot prepare/compile Gemma4 for SM8550, transformer execution cannot be distinguished from CPU fallback, or phone priority/transport is unavailable. Never substitute a CPU response for HTP evidence.

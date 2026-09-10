---
experiment: 0031-gemma-4-e2b-it-android-qnn-htp
status: completed
summary: The accepted campaign remains complete. The separate global-value FP16 candidate executed the exact long request, but its full output is identical to all five baseline repetitions. This candidate showed no text/repetition benefit; no normalized speed or broader fidelity benefit is established.
benchmark: android-llm
registry: 0031-gemma-4-e2b-it-qnn-htp
---

# Experiment 0031 — Gemma 4 E2B IT Android QNN/HTP

## Experiment description

Gemma 4 E2B IT already has measured Android CPU and GPU routes, but its QNN arm stopped when QAIRT 2.49.0 could not transform the exact public W4A16 graph. The authorized QAIRT 2.49.40 route has since cleared transformation, QNN conversion, weight-shared SM8550/v73 compilation, runtime-bundle preparation, and physical context deserialization. An initial context stopped before dialog/query because AR1 and AR128 disagreed on 15 value-cache quantization boundaries. A host correction made all four AR1-input/output and AR128-input/output signatures identical, and that context physically deserialized without the prior 30 validation errors. Genie then stopped before dialog or graph execution because its positional binding requested tensor names that differed from the context. A numerically identical input-symbol correction aligned both AR variants with the exact Genie names. The rebuilt context completes bounded physical QNN HTP inference, but that run prepended one automatic BOS to the bound single-BOS sequence. A source-proven configuration correction suppresses the automatic prefix without changing workload, model, tokenizer, LUTs, or context. Physical confirmation now reports the exact 170-token single-BOS sequence and coherent bounded output, clearing effective-input identity for this max-16 viability gate.

The intended end-to-end result has not changed: an exact, provenance-bound Gemma 4 E2B context compiled for SM8550/HTP v73, physical `QnnHtp` provider proof on the authorized Galaxy S23 Ultra, a bounded viability request, proven loaded-route state isolation, and only then the canonical one-first-plus-five-short/five-medium/five-long Android campaign. Toolchain acquisition or file presence alone cannot satisfy any of those gates.

The public `gemma_4_e2b_it_w4a16.zip` checkpoint remains the pinned model input. It is hash-bound at 2,013,959,998 bytes and includes the exact ONNX/external data, W4A16 encodings, tokenizer, template, and configuration assessed by the earlier transform probe. The owning [experiment README](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/README.md), [experiment contract](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/protocol/experiment-contract.json), [positive transform result](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-transform-compat/result.json), [QNN conversion result](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-qnn-conversion/result.json), [compiled-context inspection](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-sm8550-context/result.json), [runtime-bundle/LUT result](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/gemma4-sm8550-runtime-bundle/result.json), [first phone attempt](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/android-qnn-physical-viability-attempt-01/result.json), [corrected retry](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/android-qnn-physical-viability-attempt-02/result.json), [cache-quantization correction](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-cache-quantization-correction/result.json), [cache-corrected phone-stage preparation](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/cache-corrected-phone-stage/result.json), and [third physical attempt](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/android-qnn-physical-viability-attempt-03/result.json), [position-ID binding correction](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-position-id-binding-correction/result.json), [position-ID-corrected phone stage](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/position-id-corrected-phone-stage/result.json), and [fourth physical attempt](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/android-qnn-physical-viability-attempt-04/result.json), [automatic-BOS suppression](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/genie-automatic-bos-suppression/result.json), [canonical-BOS-corrected stage](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/canonical-bos-corrected-phone-stage/result.json), and [fifth physical attempt](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/android-qnn-physical-viability-attempt-05/result.json), and [canonical campaign harness readiness](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/canonical-campaign-harness-readiness/result.json), and [campaign launch preflight](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/canonical-campaign-launch-preflight/result.json), and [physical campaign setup attempt](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/android-qnn-physical-campaign-attempt-01/result.json), and [single-dialog reset harness readiness](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/canonical-campaign-reset-harness-readiness/result.json), and [completed canonical campaign](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/android-qnn-physical-campaign-attempt-02/result.json), and [long-collapse improvement baseline](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/results/long-collapse-baseline/result.json) are the evidence authority.

## Progress

The original assessment established credible first-party Gemma 4 route ingredients but no working conversion. QAIRT 2.49.0 resolved SM8550 to HTP v73 and shipped a Gemma 4 HTP example, yet its high-level factory had no `Gemma4ForConditionalGeneration` dispatch. The smallest faithful transform of the unchanged public graph failed during shape inference and constant propagation with `KeyError('value')`, before QNN conversion, context creation, or compilation.

An authorized Qualcomm QPM acquisition has now bound `Qualcomm_AI_Runtime_SDK.2.49.40.260810.Linux-AnyCPU.qik` at 2,410,405,384 bytes and SHA-256 `ef4a63b8…fdb0c`. The package and installed SDK remain outside Git; the committed evidence records no account identity, identifiers, credential contents, or restricted binary. The compared SDK reports QAIRT 2.49.40 premium with the same QNN backend API version as 2.49.0 and retains the Gemma 4 example plus SM8550/v73 runtime components.

The capability inventory compared the exact files implicated by the prior blocker. The Gemma4 builder factory, ONNX utility containing constant handling, shape-inference pass, release notes, and Gemma 4 HTP configuration are byte-identical between QAIRT 2.49.0 and 2.49.40. The new factory still has no Gemma4 dispatch, so the old transform defect should not be expected to disappear merely by changing package versions.

Selected deployment/runtime libraries did change: `libGenie.so`, `libQnnHtp.so`, the Android v73 stub, and the Hexagon v73 skeleton have new hashes, while the compared Genie executables and `libQnnSystem.so` remain identical. Those differences make 2.49.40 a separately bound runtime candidate if a valid context can eventually be produced; they do not prove that the model transforms, compiles, loads, or executes.

The compatibility layer addresses only the observed schema and shape gaps: it reads the checkpoint's four standards-valid `Constant(value_ints=...)` nodes, seeds Gemma4-specific axes, materializes the exact sliding-window cache and attention-mask widths, and propagates the shape-preserving `Reciprocal` operation. It is isolated from the checkpoint and does not rewrite the public source graph, external data, or encodings.

Under `heavy-ram.lock`, QAIRT 2.49.40 completed a transform-only AR1+AR128, CL4096, one-split run. It produced:

- AR1 ONNX SHA-256 `9f3077b4…e472` and encodings SHA-256 `0dbb1aad…e2a8`;
- AR128 ONNX SHA-256 `d1171990…e9a` and encodings SHA-256 `7e264005…a251`;
- shared 9,119,006,720-byte transformed external data at SHA-256 `b9b73b98…a65d`.

Both output graphs pass the ONNX checker, and every graph input and output is static. Post-transform hashes prove that the original ONNX, external data, and encodings remain unchanged. This milestone requested no QNN conversion, HTP compilation, inference, phone access, or paid Workbench job.

Both static variants now pass QAIRT 2.49.40 QNN conversion with `backend=HTP` and the published quantization overrides:

- AR1 DLC: 2,356,831,668 bytes, SHA-256 `02a79060…ff68`;
- AR128 DLC: 2,356,851,284 bytes, SHA-256 `5f17ece8…56ee`.

`qairt-dlc-info` binds each converted graph at 2,280,676,608 parameters and retains its operator and I/O encoding inventory. The conversion is not uniformly integer: the converter reports 15 RmsNorm float fallbacks in each variant. AR1 also exposes 15 value-cache outputs as Float16, while all 31 AR128 outputs are uFxp16. These mixed-precision facts remain visible for compilation and runtime validation; they are not silently described as uniform W4A16 or as CPU-provider fallback.

Both DLCs now compile together in QAIRT weight-sharing mode. The resulting 1,186,349,056-byte serialized context has SHA-256 `b8c169ce…af95a`. Official `qnn-context-binary-utility` inspection reports:

- QAIRT build `v2.49.40.260810104044` and QNN HTP backend ID 6;
- exactly two graphs, `ar1_cl4096_1_of_1` and `ar128_cl4096_1_of_1`;
- 38 inputs and 31 outputs for each graph;
- embedded `soc_type=SM8550`, `arch=73`, and `native_hmx_a16w4=true` markers.

The mixed-precision boundary remains present in compiled metadata: all 31 AR128 outputs are unsigned fixed-point 16, while AR1 retains 15 Float16 value-cache outputs and 16 unsigned fixed-point outputs. This is not a uniform-integer claim.

The private runtime bundle is now prepared from the pinned, ungated Apache-2.0 QAT checkpoint. A pinned Google/Hugging Face formula decodes its low-bits-first signed INT2 token embeddings and INT4 per-layer embeddings, applies per-row/per-block plus architectural embedding scales, and requantizes them into the uint8 LUT format expected by the QAIRT Gemma 4 runtime:

- token LUT: 402,653,184 bytes, SHA-256 `3b55bb6b…4239`;
- per-layer embedding LUT: 2,348,810,240 bytes, SHA-256 `bc5f25db…9fa4`.

Deterministic sampled reconstruction covers selected vocabulary rows and remains within half of one uint8 quantization step for both LUTs. This is a bounded LUT-fidelity check, not full-tensor numerical equivalence or model-output validation.

The bundle manifest binds both LUTs, context SHA-256 `b8c169ce…af95a`, exact tokenizer, QAIRT 2.49.40 Genie plus QNN HTP host/stub/v73 skeleton libraries, and a `QnnHtp` configuration with CL4096, greedy sampling, and the 2,048-token ceiling. All large or restricted artifacts stay outside Git.

The bounded phone tooling required `phone.lock`, exact device and artifact hashes, raw-first evidence capture, a 16-token ceiling, and verified scoped cleanup. The first authorized attempt passed identity and hash checks, parsed the `QnnHtp` configuration, discovered both AR graphs and their sliding-window mappings, detected physical SM8550, and initialized the HTP provider/backend/device, v73 stub, and first QNN stub connection. It then exited 139 during dialog creation because `libQnnHtpNetRunExtensions.so` was absent. No query, graph execution, output, or profile occurred.

The missing QAIRT 2.49.40 Android extension was added at 1,091,656 bytes, SHA-256 `e25a816d…04ae`, and both stage and run tooling now fail closed on an incomplete runtime. The one authorized corrected retry loaded that extension, initialized the physical HTP stack, and fully deserialized the two-graph weight-shared context.

Genie then rejected model validation before dialog/query with exactly 30 non-identical quantization-parameter errors. The 15 AR1 value-cache outputs are Float16, while the corresponding 15 AR128 cache inputs and 15 AR128 cache outputs are unsigned fixed-point 16 with defined scale/offset encodings. This is the mixed-precision boundary already visible in host context metadata, now confirmed as a physical runtime blocker.

Attempt 02 exited 1 with zero graph executions, tokens, or output. Its profile exists but contains no components. Both attempts verified their stage hashes, removed and verified the scoped remote root absent, and released `phone.lock`.

The cache blocker is now corrected without changing the checkpoint or weakening Genie validation. A schema-standard ONNX float fork and `QuantizeLinear` boundary maps each of the 15 public AR1 value-cache outputs to the already-bound source-QAT uint16 zero point 32768, QNN offset -32768, and exact per-cache scale. Internal transformer consumers keep the existing path; this adds no host CPU cache-conversion boundary.

The corrected AR1 DLC is 2,356,847,444 bytes with SHA-256 `7e88facd…c9e1`, retains 2,280,676,608 parameters, and exposes 31/31 outputs as uFxp16. Recompiling it with the unchanged AR128 DLC produced a 1,186,369,536-byte weight-shared SM8550/v73 context at SHA-256 `a1d52d00…cc44`. Official metadata identifies QNN HTP backend ID 6, the exact QAIRT 2.49.40 build, and two 38-input/31-output graphs.

For every one of the 15 value caches, official context inspection verifies that AR1 input, AR1 output, AR128 input, and AR128 output now share identical uFxp16 datatype, scale, and offset signatures. This clears the exact attempt-02 validation mismatch on the host.

The correction is not a uniform-integer execution claim: QAIRT still reports 75 float-precision component fallback operations around affected normalization paths. Host conversion, recompilation, and metadata inspection also do not prove that the phone will accept or execute the revised context.

The private runtime bundle and phone stage are now rebuilt around corrected context SHA-256 `a1d52d00…cc44`. The stage contains 17 manifest entries totaling 4,003,765,361 logical bytes and binds the exact tokenizer, source-derived token/PLE LUTs, Genie/QNN HTP/v73 dependencies, canonical short prompt, and 16-token viability ceiling. The full manifest, `SHA256SUMS`, required-runtime completeness, restrictive file permissions, and dependency checks all pass; the run script fails closed on any corrected-context hash mismatch.

Stage preparation itself was host-only, but Pi subsequently authorized exactly one bounded physical gate. The full `phone.lock` lifecycle covered ADB; the SM-S918B/SM8550 identity, local and remote hashes, and runtime completeness all passed. On the physical phone, the backend extension loaded, QNN HTP provider/backend/device and the v73 stub initialized, and the corrected two-graph weight-shared context deserialized. The prior 30 cache-quantization validation errors were absent, physically clearing that blocker.

Genie then reported `position_ids_global_cos` and `position_ids_global_sin` as unconnected context inputs while searching for `position_ids_cos` and `position_ids_sin`. I/O discovery failed with `Could not find I/O tensors in loaded graphs`; dialog creation failed, and the later scripted query addressed a nonexistent dialog. Attempt 03 exited 1 before graph execution, generated zero tokens, created no output, and retained a profile with null components.

Cleanup verified the experiment-scoped remote root absent and no residual process, then released `phone.lock`.

The positional binding is now corrected on the host with a symbol-only graph-input and activation-encoding rename in both AR variants: `position_ids_global_cos/sin` becomes Genie's exact `position_ids_cos/sin`. Checkpoint weights and graph numerics are unchanged, and the AR1 value-cache quantize/dequantize boundary is preserved. Both rebuilt DLCs retain 2,280,676,608 parameters and 31/31 uFxp16 outputs.

The rebuilt 1,186,369,536-byte weight-shared context has SHA-256 `7739ce52…d394`. Official metadata reports QNN HTP backend ID 6, QAIRT build `v2.49.40.260810104044`, SM8550/v73, and both 38-input/31-output graphs. Both expose unprefixed `position_ids_cos/sin` for global RoPE plus `swa_position_ids_cos/sin` for SWA; the old global names occur zero times. All 15 four-way AR1-input/output and AR128-input/output cache signatures remain identical.

The private 16-token stage is rebuilt around this context. Its 17 files total 4,003,765,361 logical bytes; manifest, `SHA256SUMS`, runtime completeness, dependencies, and restrictive modes all pass. Preparation used no ADB and did not acquire `phone.lock`.

Pi then authorized one bounded physical gate under the full `phone.lock` lifecycle. The verified SM-S918B/SM8550 passed local and remote hashes plus runtime completeness. The corrected context deserialized, dialog creation passed, and the physical QnnHtp/QnnDsp route completed two AR128 prompt graph executions plus fifteen AR1 decode graph executions, all with status `0x0`. Logs contain zero QNN CPU-backend markers and zero runtime-fallback markers.

The max-16 request exited 0 with an 82-byte coherent output at SHA-256 `c7f1bbe3…e44c`:

> The choice between Engine Cedar, Juniper, and Rowan for our next project hinges on

Output sanity is `looks_sensible: true`, `issue_notes: null`, but the fragment is bounded viability output, not a broad quality result. The profile reports initialization 1.900 seconds, TTFT 0.523 seconds, prompt processing 327.332 tokens/s, and token generation 17.572 tokens/s. These are one-run viability observations, not canonical campaign metrics or a statistical performance distribution.

A fatal canonical-input mismatch remains. The experiment binds a 170-token rendered sequence with one leading BOS. Genie reports 171 prompt tokens, and its token log begins `[2, 2, 105, …]`; after the extra first token, the logged prefix matches the bound sequence. This proves one automatic BOS was prepended at runtime. The coherent output therefore cannot qualify this run as the canonical request.

Cleanup verified the scoped remote root and process absent, then released `phone.lock`.

The automatic prefix is now suppressed by changing only Genie's configuration from `bos-token: 2` to `bos-token: -1`. Hash-bound QAIRT 2.49.40 source parses a negative BOS sentinel and prepends only when the configured value is nonnegative; shipped example and documentation material corroborate `-1` as the no-prefix setting. Model, context, LUTs, canonical workload/rendered bytes, and tokenizer remain unchanged.

With the prepend branch disabled, the pinned tokenizer reproduces the committed 170-token file byte-for-byte. The host-effective sequence begins `[2, 105, 9731, …]`, contains exactly one leading BOS, and retains token SHA-256 `31a85f9c…ad78`. This is host proof of the intended effective sequence, not runtime evidence.

The rebuilt private max-16 stage has 17 files totaling 4,003,765,362 logical bytes. It remains bound to context SHA-256 `7739ce52…d394`; manifest, `SHA256SUMS`, dependencies, runtime completeness, and restrictive modes pass. Its preparation used no ADB or `phone.lock`.

Pi then authorized one bounded physical confirmation. Under the full lock lifecycle, the exact stage and verified SM-S918B/SM8550 loaded the context and dialog. The physical QnnHtp/QnnDsp path completed two AR128 and fifteen AR1 graph calls, with starts and successful completions both 17, all status `0x0`. Logs contain zero QNN CPU-backend and zero runtime-fallback markers.

Genie's profile reports exactly 170 prompt tokens. Both fixed-size token-log lines begin `[2, 105, 9731, …]`; all 157 complete logged IDs match the committed sequence before the logger truncates midway through the next number. Exactly one leading BOS appears. This physically clears the automatic-BOS/effective-input blocker for the bounded short gate.

The max-16 request exited 0 with coherent 89-byte output at SHA-256 `70711436…6357`:

> The choice between the Cedar, Juniper, and Rowan inference engines hinges entirely on the

Output sanity is true/null, but the text remains a bounded partial fragment. Profile observations are initialization 2.095 seconds, TTFT 0.528 seconds, prompt processing 321.854 tokens/s, and generation 17.703 tokens/s. They describe one viability run, not a canonical campaign distribution.

Cleanup verified the scoped root and process absent, then released `phone.lock`. The input blocker is cleared, but this max-16 gate is not the canonical 2048-ceiling first/warm campaign and does not establish request-isolation or performance distributions.

A host-only campaign harness now encodes the complete protocol shape in one `genie-app` process. Hash-bound QAIRT source establishes that a Registry-backed QnnHtp engine is reference-counted and created once per key. An unqueried keeper dialog retains that shared engine for the process lifetime; each logical request creates a fresh dialog with a new independent `EngineState`, applies it before query, writes unique raw output and profile files, then frees the dialog while the keeper remains.

The fixed 16-request order is one first short, five additional short, five medium, and five long requests. Each uses the exact tier prompt hashes and 2,048-token ceiling. Setup covers keeper creation through engine readiness; fresh-dialog creation and query timing are recorded separately per request. There is no model remap, accelerator recompile, or engine reload between requests.

A per-request 1,800-second timeout terminates the one process and performs no automatic retry. Every request remains independently classified; missing or partial output/profile evidence never inherits another request's metrics. The complete raw campaign is pulled before validation. The runner also fail-closes on explicit approval, `phone.lock`, device identity, local/remote hashes, dependencies, and scoped cleanup while retaining memory and thermal evidence.

The private 20-file campaign stage totals 4,003,790,569 logical bytes; manifest, `SHA256SUMS`, and permissions pass.

The first approved launcher invocation then failed locally with exit code 126 and `Permission denied`. Empty stdout proves the runner body never began. It acquired no `phone.lock`, invoked no ADB, created no remote root or Genie process, and started zero logical requests. No output, profile, metric, or campaign evidence exists, and no automatic retry occurred. This is a local packaging preflight failure, not a physical campaign attempt.

The only launcher fix changed `tools/run_phone_campaign.sh` from Git mode `100644` to executable mode `100755`; campaign design and scope remained unchanged.

The next authorized invocation entered the full `phone.lock` lifecycle, passed device identity, local and remote stage hashes, dependencies, push, and process startup. Shared-engine extraction then moved the full dialog engine object—including dialog-only `cache-groups`—into standalone Engine configuration. Standalone validation rejected it with `Unknown engine config key: cache-groups`.

The keeper plus all 16 intended request-dialog creations failed at that same schema boundary. Exit code was 1. QNN provider initialization never began; no context deserialized, query ran, graph executed, or logical request started. No output files exist. Setup plus 16 profile files were retained, but all 17 have null components. The observed process VmHWM before failure is not model or campaign memory.

Raw nested evidence is retained; cleanup verified the scoped root and process absent and released `phone.lock`. There was no retry. This is physical setup/configuration failure evidence, not campaign performance or a request distribution.

Host analysis found that stock standalone Engine schema cannot carry Gemma's two dialog-level cache groups. The corrected harness therefore abandons `shared-engine` rather than weakening the cache contract. One normal, already proven QnnHtp dialog and context remain loaded for the full process; the public `GenieDialog_reset` API runs before every request after the first. Both `past_` and `swa_` cache groups remain in the normal dialog configuration.

Hash-bound QAIRT source proves reset clears past/prompt/generated/decode/query counters, last and pending tokens and embeddings, HTP KV and model state via `updateKV(0)`, sampler/grammar/Harmony state, and dialog state without remapping the model. The corrected runner creates and frees one dialog, issues exactly 16 first+5/5/5 queries with 2,048-token ceilings, and performs exactly 15 resets.

Each request writes a unique raw output and cumulative profile snapshot. Validation assigns request N only the newly appended query event and checks exact event-count growth. Reset duration is extracted separately from verbose `GenieDialog_reset` entry/return timestamps; it is not folded into query profile time. The existing 1,800-second timeout, no-retry, raw-first, approval/lock/hash, memory/thermal, and cleanup boundaries remain.

The rebuilt private 20-file stage totals 4,003,786,019 logical bytes; hashes and modes pass.

The corrected campaign then completed under the full lock, hash, raw-capture, thermal, and cleanup lifecycle. One process deserialized one context and created one dialog. All 16 exact requests completed in first-short plus five short, five medium, and five long order, with 15 successful full resets, no timeout, error, or retry, and the 2,048-token ceiling intact. Every cumulative profile added exactly one query event.

Provider logs retain 117 successful AR128 and 15,158 successful AR1 graph completions: 15,275 QnnDsp executions, all status `0x0`, with zero QnnCpu, CPU-backend, runtime-fallback, or fatal validation markers. Setup initialization was 2.112 seconds.

Warm loaded-route medians are:

| Tier | TTFT | Prefill | Genie generation-rate observation | Output |
|---|---:|---:|---:|---|
| Short | 462.433 ms | 367.647 tok/s | 19.584 tok/s | 474 tokens, EOS |
| Medium | 907.551 ms | 654.879 tok/s | 18.774 tok/s | 418 tokens, EOS |
| Long | 2,605.519 ms | 740.741 tok/s | 17.828 tok/s | 2,048 tokens, max ceiling |

Genie does not define whether its generation-rate numerator includes the first token. The experiment retains those authoritative profile observations, while registry-normalized decode throughput is null rather than inventing inclusion semantics.

All greedy outputs are byte-identical within each tier. Short and medium outputs pass the narrow exact-output sanity check. All five long outputs fail it with the exact issue: `Severe repetition collapse in the exact max-token output.` The failure is retained rather than discarded; this is valid execution/performance evidence, not correctness, usefulness, or quality acceptance.

Peak sampled process PSS was 344,201 kB and VmHWM was 460,200 kB. These exclude unreported HTP-private memory, and sparse sampling can miss peaks. Thermal status rose from 0 to 4; skin rose from 35.9°C to 49.0°C and AP from 37.8°C to 57.1°C. Battery moved from 58% at 35.7°C to 52% at 44.0°C while USB-powered. No calibrated external power measurement exists.

The original 399,795,157-byte provider log is hash-bound and retained losslessly as deterministic gzip alongside every output and profile. Cleanup verified the scoped root and process absent and released `phone.lock`.

### Long-collapse improvement track (separate from completed campaign)

After completion, improvement 0001 analyzed the immutable `37a2953` campaign and `e91b3f5` publication; it does not replace, relabel, or rerun them. Commit `f24fd21` established the baseline localization, and corrective commit `1c5b7b6` tightened cross-route decode comparability and the completion-time calculation.

All five QNN long outputs are byte-identical and retokenize to the profiled 2,048 tokens. The first 128-token window whose four-gram unique ratio is at most 0.25 begins at generated token 84, absolute context position 2,012. This is the window's start, not an exact causal onset. An exact nine-token periodic suffix starts at generated token 479, absolute position 2,407, and covers the final 1,570 tokens: 174 complete cycles plus four trailing tokens. The dominant phrase pattern appears 215 times. Generation ends at absolute position 3,977, so crossing the 4,096 context boundary is excluded as the trigger.

Accepted LiteRT GPU and CPU outputs use the same rendered long-prompt bytes, remain coherent, and EOS-stop at 756 tokens without a periodic suffix. They are not numerical controls: QNN and LiteRT use different deployment artifacts, quantization schemes, and route-native tokenizers (1,929 versus 1,930 input tokens), and their text diverges at the first output word. Even LiteRT GPU and CPU emitted-token trajectories diverge at token 6. Text therefore cannot identify a first-logit or internal-state cause.

The leading candidate is an explicit request-level hybrid: accepted QNN HTP for complete short and medium requests, accepted LiteRT GPU for complete long requests. Backend selection occurs before each logical request; this is not hidden tensor/provider fallback. The accepted long completion is 48.311 seconds on GPU versus 118.256 seconds on HTP, a 59.147% reduction, but the difference includes coherent EOS at 756 tokens versus repetitive max-token termination at 2,048. It is a total-completion comparison, not equal-output work.

No normalized decode delta or decode-based ranking is made. QNN's 17.828 tok/s value is a raw Genie observation with unspecified first-token inclusion; LiteRT's 16.302 tok/s explicitly excludes the first token. Prefill/TTFT comparisons also retain the route-native tokenizer-count difference. Dual-route setup and memory are separate costs, and process measurements do not expose additive HTP/GPU-private memory.

The second candidate targets FP16 global-attention value-cache I/O (`past_value_{4,9,14}`) in AR1/AR128, with transformer compute intended to remain on HTP. The original ranking involved no conversion or phone run; the later host attempts below are distinct evidence and do not change the accepted campaign.

**2026-09-10 — FP16 host attempts (`d0bfa74`).** Four attempts are retained separately, including their failures:

| Improvement attempt | Observed boundary |
|---|---|
| [01](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/results/global-value-fp16-attempt-01/result.json) | QAIRT import could not resolve `libpython3.10.so.1.0`; neither patching nor conversion started. |
| [02](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/results/global-value-fp16-attempt-02/result.json) | Import then could not resolve `libunwind.so.1`; still before patching or conversion. Existing experiment-local host libraries resolved the prerequisites without installation or SDK changes. |
| [03](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/results/global-value-fp16-attempt-03/result.json) | Patch preflight rejected the assumption that both variants contain six selected encoding records. AR1 has six explicit input/output entries; AR128 has only three input entries. Conversion did not start. |
| [04](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/results/global-value-fp16-attempt-04/result.json) | Both ONNX patches passed scope checks. AR1 conversion entered optimization/quantization, then was stopped for app priority before producing a DLC. |

Attempt 04 verifies only the ONNX boundary: FP16 inputs/outputs for the three selected global value caches, exactly six AR1 and three AR128 encoding removals, and unchanged other I/O, encodings, and weight initializers. It does not prove the datatypes or execution behavior of a converted QNN model.

The supervisor honored a `STOP` request, sent TERM, and reaped its owned process group without automatic restart. Attempt 04 retains classification `app_priority_interruption_not_model_failure`: no DLC or compiled context was produced, and AR128 conversion, compilation, and inference never started. Its actual DLC cache signatures, Convert-count change, full HTP delegation, unsupported/fallback count, context size, and fidelity remain null/unmeasured—not passed or zero. No phone access occurred; work was held for app priority.

**2026-09-10 — Partial conversion and storage failure (`d5e6b94`).** After a separate release, [attempt 05](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/results/global-value-fp16-attempt-05/result.json) used the unchanged recipe and produced an AR1 DLC of 2,356,848,948 bytes, SHA-256 `4e67d80e…a6cc`. Official DLC CSV inspection confirms `Float_16` on all six selected global value-cache interfaces: inputs and outputs for layers 4, 9, and 14. Their dimensions and every unselected public interface signature remain unchanged. This advances beyond attempt 04's ONNX-only scope check.

The AR1 operator count remains 6,875 and `Convert` remains 31→31, so the hoped-for conversion-count reduction is not demonstrated. Converter float-precision warnings rise from 75 to 81, adding three global concatenations and three output Casts. These are precision observations, not CPU-provider fallback counts or full HTP-delegation proof.

Sequential AR128 conversion failed with `OSError: [Errno 28] No space left on device` while dumping external data into the roughly 16 GiB `/tmp` tmpfs. This is a host-storage failure, not numerical or model failure. The traceback-bound, UID-owned scratch directory was removed only after retaining ownership evidence and the partial file's exact size/hash: 8,263,168,000 bytes / SHA-256 `5d0b944e…760ae`. The completed AR1 DLC, candidate/source ONNX, and other temporary directories were left untouched; owned converter processes were absent.

Both read-only inspection attempts are also retained: the first timed out after 90 seconds with empty logs, while a separate guarded inspection completed. Neither was a conversion or inference retry. Candidate and baseline CSVs are losslessly compressed and hash-bound.

Attempt 05 ended without an AR128 DLC or matched pair. The proposed storage fix was an environment change, not a model correction: `QAIRT_TMP_DIR` under a fresh disk-backed owned directory.

**Source-only efficiency step (`bbd1eec`).** The [disk-scratch and AR1-reuse helper](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/DISK-SCRATCH-READINESS.md) adds AR128-only conversion with read-only reuse of attempt 05's passed AR1 artifact. It pins the result, DLC size/hash, and actual interface provenance before QAIRT import; mismatch cases are rejected. Reused and newly converted artifacts have separate receipts, and the unchanged precision patch cannot bypass the mandatory actual two-AR cache-pair gate before compilation. This source/synthetic step itself ran no conversion or inference.

**2026-09-10 — Paired DLC interfaces (`ce3b021`).** After separate release, [attempt 06](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/results/global-value-fp16-attempt-06/result.json) verified and reused AR1 SHA-256 `4e67d80e…a6cc` without rewriting or reconverting it. Only AR128 was newly converted, producing a 2,356,859,020-byte DLC at SHA-256 `48fc15f0…7b64`. The reused AR1 identity was checked again afterward; it is not counted as a new conversion.

Official CSVs now confirm the selected global value-cache inputs and outputs are Float16 in both variants, all unselected public signatures and dimensions remain unchanged, and datatype/encoding agrees at all **30 four-way AR1/AR128 cache contracts**. This is actual DLC interface compatibility, not compiled-context or execution evidence.

AR128's operator count rises 6,830→6,842: Convert 30→36, plus three Casts and three Dequantize operations. Converter floating-precision warnings rise 15→21, comprising 15 RmsNorm operations plus three global Concats and three output Casts. Reused AR1 remains at Convert 31→31 and warnings 75→81. There is no demonstrated count-based speed gain; these warnings establish neither CPU-provider fallback nor full HTP delegation.

Attempt 06 used owned disk-backed scratch. The SDK removed its temporary files, the empty scratch root was removed, and owned processes were reaped. That conversion milestone performed no context compilation, inference/fidelity test, or phone run.

**2026-09-10 — Host context compile (`f637a74`, Gemma slice only).** A separately authorized [context attempt 01](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/results/global-value-fp16-context-attempt-01/result.json) ran the unchanged hash-pinned accepted compiler recipe, substituting only the reviewed paired DLC paths/hashes and fresh output/cache/scratch paths. It produced one 1,186,430,976-byte SM8550/v73 weight-sharing context, SHA-256 `1d80d016…ca9f8`: 61,440 bytes larger than the baseline. This publication covers only the experiment-owned evidence in that mixed-scope commit; its separate app/gallery files are neither published nor approved by the Gemma review.

Official metadata confirms QNN HTP backend 6 / SoC 43, build `v2.49.40.260810104044`, both original AR1/AR128 graph aliases, and 38 inputs / 31 outputs per graph. Only the selected global value-cache types/quantization differ; unselected names, shapes, positional/SWA bindings, and active quantization remain unchanged. All 30 four-way cache contracts match and all **120 cache tensor boundaries are `FLAT_BUFFER`**. Weight-sharing or HMX weight-kernel markers do not imply NativeKV cache layout.

The [Genie FP16 source notes](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/GENIE-FP16-CACHE-SOURCE-NOTES.md) provide conditional rationale, not runtime proof: ordinary flat-buffer updates copy raw bytes, while key-derived clearing uses `0x8000`, interpreted as FP16 negative zero for the selected values. NativeKV accepts only quantized uint8 and is not selected or claimed. Quantization-dependent cache dump/spec/export paths were not exercised and must not be assumed valid for mixed quantized-key/FP16-value state. SDK example source does not establish every shipped-runtime path's behavior.

The accepted warn-level compiler API can suppress native logs, so the exhaustive unsupported-operator count remains **null, not zero**. The retained builder architecture-default warning is not a CPU-provider observation; no extra compile was performed just to obtain optional logs. Compilation and metadata compatibility do not prove CPU-free neural placement, runtime loading, fidelity, long-output improvement, or speed. The increased DLC Convert counts and precision warnings remain disclosed.

Owned compile scratch was empty/removed and processes were reaped. At this compile-only milestone, no runtime reset/inference, fidelity test or phone run had occurred; those outcomes were unmeasured. The later short-query evidence below does not alter the original completed campaign, its registry card or registry evidence.

**2026-09-10 — Frozen stage and diagnostic plan (`212f0d4`).** The [file-preparation result](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/results/frozen-genie-stage-readiness/result.json) binds a separate private stage of **21 payload files / 4,003,855,761 bytes**, manifest SHA-256 `58484160…fe25`. Large payloads are independent copies, not links into the accepted baseline. The runner is read-only executable `0555`, other inputs read-only, and directories private `0700`. This is a hash freeze, not hardware-enforced immutability; future use must reverify the external digest and every payload.

The stage uses compiled context `1d80d016…ca9f8` under the unchanged alias, with the accepted runtime libraries, LUTs, tokenizer, BOS suppression and configuration bytes unchanged. Config SHA-256 `f8008e04…7eba` retains context 4096, greedy sampling and base ceiling 2048. Exact short/long prompt and token-ID bytes are pinned; expected input counts are inherited evidence, not a fresh tokenization observation.

Its only execution script describes **one fresh-dialog first-short query capped at 16 tokens**, explicitly engineering/noncanonical. It was not executed during stage preparation. Long inputs were frozen but **that stage contains no long script**; an exact-long/max2048 comparison requires separate preparation, evidence review and permission. The [diagnostic plan](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/PHONE-RETURN-DIAGNOSTIC-PLAN.md) still distinguishes short viability from long-collapse fidelity. Stage preparation copied/hashed files and checked source/configuration only: no runtime/model load, tokenization replay, compilation, phone lock or ADB.

**2026-09-10 — Candidate controller, source/mock readiness (`62b8a16`).** The separate [controller result](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/results/phone-return-controller-readiness/result.json) and [reviewed lifecycle notes](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/PHONE-RETURN-CONTROLLER-READINESS.md) add orchestration without modifying the frozen stage or old baseline runner. The default prints a plan; execution requires an explicit execute flag, exact reviewed stage digest, fresh run directory and a one-use slot attestation from an actual new Pi grant. The slot string is a manual attestation, not cryptographic permission, and readiness itself grants no slot.

The source requires one full `phone.lock` lease before all ADB actions, including identity, push, polling, signals, raw pull and cleanup. It pins the device and exact reviewed Android build, verifies every local/remote payload hash and runner mode, and consumes the slot before the first ADB action. There is no automatic retry/reconnection or long/prompt/model/backend override. Only the single max16 engineering query is supported, with a 1,800-second host process deadline and independent remote watchdog; bounded transfer/pull/cleanup budgets are not a guarantee of immediate kernel termination.

For the model entry, wrapper and watchdog, recorded PID/starttime, exact executable and NUL-delimited argv are rechecked before signalling. Unknown identity means **no signal to the unverified PID and no destructive root cleanup**. These are sequential `/proc` checks followed by numeric-PID signals, **not atomic or pidfd-bound identity operations**: the final check-to-signal race remains. Fake tests demonstrate refusals on observed mismatches, not elimination of the real race or validation of Android `/proc`/shell behavior.

Raw stdout/stderr, command metadata, partial outputs and errors are retained before optional metrics. An incomplete raw pull preserves local partials **and the remote root**, even if processes are absent; unknown process state also leaves cleanup explicitly incomplete. Root removal requires both complete raw collection and confirmed process absence, followed by a separate absence check. Optional profile failure yields null/reason rather than deleting evidence. Even exit 0 does not establish native query success, EOS, provider placement or fidelity; the default metric hook leaves those unmeasured.

The controller adds **40 fake-device/tiny-stage cases**, bringing the owner suite to 104 tests after the 64-test stage milestone. Temporary host locks, mocked ADB-client spawning and host shell syntax checks used **no real ADB, repository phone lock, runtime/model load or phone**. At that source/mock milestone, live Android process/watchdog behavior and FP16 runtime/fidelity results were still pending. The existing mixed-cache API risks and null unsupported-op count remain explicit. Neither readiness milestone changes the completed campaign, registry or app evidence.

**2026-09-10 — Physical Gate A, first-short/max16 only (`81f4ede`).** The separately released [short compatibility result](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/results/phone-return-short-attempt-01/result.json) used unchanged reviewed controller `62b8a16`, frozen stage `58484160…fe25` and FP16-cache context `1d80d016…ca9f8`. Exact SM-S918B/SM8550 identity/build, payload hashes and runner mode passed under the full `phone.lock` lifecycle. This is one engineering query, not a replacement campaign.

One context deserialized and one dialog/query completed. Physical QnnDsp logs record **17 starts and 17 status-0 completions: two AR128 and fifteen AR1 calls**, with SMART_MASK selected. No CPU-backend, runtime-fallback or cache-quantization-error marker was observed; the known `usesCrossAttention` capability message is retained. These are bounded short-route observations, not universal CPU-free neural placement, uniform-integer execution or NativeKV proof. The compiled flat-buffer metadata and source/API limitations remain distinct.

The runtime echoed the exact rendered short-prompt bytes and profiled **170 input tokens / 16 generated tokens**. Both token logs match all **157 complete logged prefix IDs**, including one BOS, then truncate mid-number; they are not a complete 170-ID runtime trace. The configured 16-token ceiling was applied and reached, and the query returned normally. The independent **EOS-versus-limit stop enum is null**, because no such event/enum was exposed; no EOS or independent stop-cause event is invented.

The [89-byte UTF-8 output](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/results/phone-return-short-attempt-01/raw/controller/raw/device/short-output.txt), SHA-256 `70711436…d6357`, is byte-identical to the accepted BOS-corrected max16 baseline:

> The choice between the Cedar, Juniper, and Rowan inference engines hinges entirely on the

Narrow sanity is `looks_sensible: true`, `issue_notes: null`. This coherent prefix is not a complete answer, numerical state/logit equivalence, general quality acceptance or evidence that long-output repetition is fixed.

| Raw Genie observation | Value / interpretation |
|---|---|
| Dialog creation event | 2,178,751 µs |
| Query event | 1,478,281 µs |
| Reported TTFT | 486,106 µs |
| Generation-rate observation | 17.6189728 tokens/s; first-token inclusion unspecified |
| Normalized decode | **Null**; undefined first-token semantics, not a normalized comparison |

These are runtime-defined boundaries from one max16 diagnostic, not a canonical first/warm distribution or a speed win. Process PSS, VmHWM and HTP-private memory remain **null**: this controller collected no memory sample, and an allocation message is not a total-memory measurement.

The process finished before the first status poll, so there was no live-native PID sample. Execution is established by query/provider/profile/output evidence, not exit 0 alone. Both checks found all recorded model/wrapper/watchdog roles absent; no signal was issued. Raw pull preceded optional processing and scoped-root deletion; root absence and lock release were verified. This exercises natural completion, not every timeout/signal path or elimination of the controller's residual PID race.

Public telemetry reports battery 69% / 31.9°C on USB, thermal status 0→0, AP 40.3→43.9°C and skin 33.5→34.0°C. **Complete battery dumps remain private and hash-bound** because they contain unrelated learned charging/sleep history; public battery JSON is explicitly labelled core-field extraction, not rewritten raw data. Query/provider/output/profile/cleanup bytes, including raw log whitespace, remain unchanged. The [retention notes](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/results/phone-return-short-attempt-01/README.md) distinguish the public manifest from the original private collection inventory.

No retry, long query, rebuild or stage/controller change occurred in Gate A. At Gate A, no long-output, reset/reuse, speed, campaign or new registry result had been established; exact-long work required separate review. The accepted completed campaign and its five long-output failures remain unchanged.

**Exact-long host readiness (`b43a57f`)—not a long result.** The [separate stage and lifecycle](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/results/exact-long-readiness/result.json) contains 18 independent read-only payload copies totaling 4,003,852,753 bytes, manifest `047dd808…b846e`. FP16 context `1d80d016…ca9f8`, configuration, tokenizer/BOS, LUTs and libraries are unchanged. One fresh dialog is configured for the exact **1,929-token long input and full 2,048-token ceiling**, fitting context 4096 without truncation. Token identity is inherited from verified bytes, not new tokenization. There is no preceding short query, retained KV reuse or repeat; host/remote bounds remain 1,800 seconds.

The [fixed-scope adaptation](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/EXACT-LONG-READINESS.md) uses hash-pinned reviewed templates with enumerated substitutions and direct `nohup` plus absolute redirections. An inverse test recovers the original short-controller source. An owned FIFO-blocked host dummy verifies pipe closure before child completion and subsequent reaping—not Android detachment. Gate A file-mtime clues are not proof of a launch defect or a timing result. Lock/raw-first/retained-root gates and the non-atomic PID-race limitation remain.

That preparation was file/source/mock readiness only: **no long/native/ADB/model execution, tokenization replay or recompilation** occurred in the readiness milestone. Its repetition metrics and undefined-first-token raw-rate caveats were predeclared unchanged. The later physical call below received a fresh exact release; short evidence, app priority and private-raw retention remain unchanged.

**Physical Gate B (`e585e79`)—execution passed, repetition unchanged.** The separately reviewed [exact-long outcome](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/results/phone-return-long-attempt-01/result.json) used one fresh process/dialog/query, adapter `b43a57f`, stage `047dd808…b846e` and unchanged FP16-global-value context `1d80d016…ca9f8`. Profile counts are **1,929 input / 2,048 generated tokens**. The exact prompt was echoed; both truncated token logs match their 158 complete prefix IDs with one BOS, not a complete runtime input-ID trace.

Provider evidence records **16 AR128 + 2,047 AR1 = 2,063 QnnDsp executions**, all status 0, one context deserialization and SMART_MASK. No CPU-backend, runtime-fallback or cache-quantization-error marker was observed. These are bounded physical observations, not universal CPU-free or uniform-integer proof. The configured 2,048 ceiling was reached and the query returned normally; the independent **EOS-versus-limit stop enum remains null**.

The decisive negative result is the [complete 10,027-byte output](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/results/phone-return-long-attempt-01/raw/controller/raw/device/long-output.txt), SHA-256 `f0e9d284…97b2d`: **byte-identical to all five retained baseline long outputs**. No baseline request was rerun. Narrow sanity is false, with the exact issue `Severe repetition collapse with occasional <unk> leakage in the exact max-token output.`

The frozen repetition implementation and pinned text tokenizer reproduce every baseline metric without changed thresholds:

| Repetition observation | Unchanged result |
|---|---|
| First qualifying 128-token/four-gram window | **Start index 83, zero-based** (84th generated token); unique ratio 0.248 |
| Exact periodic suffix | **Start index 478, zero-based**; period 9; 1,570 tokens = 174 complete cycles + 4 trailing tokens |
| Other declared metrics | All 4/8/16-gram statistics unchanged; dominant word six-gram count 215 |

The window start is **not causal onset or the first internal state/logit divergence**. These indices come from re-encoding the retained output text, not a complete logged emitted-ID stream. Selected global-value FP16 interfaces alone did not change this exact request's text or repetition. Internal quantization may remain; the result does **not disprove every cache-precision hypothesis**, establish numerical state equivalence, or justify a broader model-quality conclusion.

Raw Genie reports query **109.901620 s**, reported TTFT **2.469576 s** and generation rate **19.1982803 tokens/s**. They are single runtime-defined observations under different run/thermal conditions, not a normalized speed win or distribution. First-token inclusion remains unspecified, so normalized decode is null. Thermal status changed 0→1; process PSS, VmHWM and HTP-private totals remain unmeasured. Live PID validation does not supply those memory metrics.

The **54,108,333-byte provider log** is retained losslessly as gzip with original SHA-256 `33ab01bb…2d440`; full query/output/profile/transport/cleanup evidence remains exact. The live native PID was validated, the process exited naturally, all recorded roles and the scoped root were verified absent, raw pull preceded cleanup, and the lock was released. No signal, retry, warmup, short request or follow-on was used. Full battery originals remain private/hash-bound; public battery data contains only labelled core extracts.

This is a negative text/repetition result for this candidate/request, not a campaign replacement. The completed campaign/card/registry and the short compatibility result remain unchanged. No further runtime or optimization result is established here.

The [request-routing recommendation](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/REQUEST-ROUTING.md) remains an unmeasured policy for the existing canonical tiers, not a built hybrid or a general prompt-length threshold. It selects HTP for short/medium and LiteRT GPU for long before each complete request, with no mid-request switch or retry on another provider. Co-resident setup, memory, and speed require measurement; separate accepted route measurements are not a hybrid benchmark.

## Results

**The experiment is complete as physical execution/performance evidence, with a disclosed long-output sanity failure.** One loaded QNN HTP dialog/context completed all 16 exact requests with 15 full resets and no retry. Short and medium outputs pass narrow sanity; every long output collapses into severe repetition through the max-token ceiling, so this is not quality acceptance.

| Evidence boundary | Current result |
|---|---|
| QAIRT 2.49.40 package provenance | Acquired outside Git and hash-bound |
| Gemma4 factory dispatch | Still absent in the compared source |
| Implicated converter / shape-inference sources | Byte-identical to QAIRT 2.49.0 |
| Android/HTP runtime candidate | SM8550/v73 components present; selected runtime-library hashes changed |
| Gemma transform with 2.49.40 compatibility layer | AR1 and AR128 CL4096 one-split variants completed; static I/O and ONNX checker passed |
| Public checkpoint identity | Original ONNX, external data, and encodings unchanged after transform |
| Host QNN conversion | AR1 and AR128 HTP-targeted DLCs completed and hash-bound |
| Converted graph inventory | 2,280,676,608 parameters per DLC |
| Mixed-precision boundary | 15 RmsNorm float fallbacks per variant; 15 AR1 Float16 value-cache outputs; AR128 outputs uFxp16 |
| Host weight-shared context | 1,186,349,056 bytes / SHA `b8c169ce…af95a`; QNN HTP backend ID 6 |
| Context graph inventory | AR1 + AR128, each 38 inputs / 31 outputs; SM8550, arch 73, native HMX A16W4 markers |
| Token LUT | 402,653,184 bytes / SHA `3b55bb6b…4239`; source INT2 to runtime uint8 |
| Per-layer embedding LUT | 2,348,810,240 bytes / SHA `bc5f25db…9fa4`; source INT4 to runtime uint8 |
| Sampled LUT fidelity | Both within half of one uint8 quantization step on the deterministic sample |
| Runtime bundle | Context + tokenizer + Genie/QNN HTP/v73 libraries + CL4096 greedy configuration hash-bound outside Git |
| Attempt 01 physical boundary | Both AR graphs/SWA mappings and SM8550 HTP stack initialized; missing NetRun extension caused exit 139 pre-query |
| Attempt 02 physical boundary | Corrected extension loaded and context deserialized; 30 value-cache quantization mismatches caused exit 1 pre-dialog/query |
| Root cause | 15 AR1 Float16 value outputs versus matched AR128 uFxp16 inputs and outputs with differing quantization parameters |
| Corrected AR1 DLC | 2,356,847,444 bytes / SHA `7e88facd…c9e1`; 2,280,676,608 params; 31/31 uFxp16 outputs |
| Corrected context | 1,186,369,536 bytes / SHA `a1d52d00…cc44`; QNN HTP backend ID 6; two 38-in/31-out graphs |
| Cache correction proof | All 15 AR1-in/out + AR128-in/out datatype/scale/offset signatures identical |
| Remaining precision boundary | 75 float-precision component fallback ops retained; not uniform-integer/no-fallback proof |
| Cache-corrected phone stage | 17 files / 4,003,765,361 logical bytes; manifests, hashes, dependencies, and permissions verified |
| Attempt 03 physical boundary | Verified SM-S918B/SM8550; local/remote hashes passed; extension + QNN HTP/backend/device/v73 initialized; corrected context deserialized |
| Cache blocker on physical load | Prior 30 cache-quantization validation errors absent; blocker cleared |
| New pre-execution blocker | Context exposes `position_ids_global_cos/sin`; Genie requests `position_ids_cos/sin`; I/O discovery/dialog creation fails |
| Attempt 03 execution/output | Exit 1; 0 graph executions; 0 tokens; no output; profile components null |
| Position-ID correction | Identity rename `position_ids_global_cos/sin` → `position_ids_cos/sin` in AR1 and AR128; weights/numerics unchanged |
| Rebuilt DLC boundary | 2,280,676,608 params and 31/31 uFxp16 outputs each; AR1 cache QDQ preserved |
| Rebuilt context | 1,186,369,536 bytes / SHA `7739ce52…d394`; HTP backend 6; two SM8550/v73 graphs |
| Positional-name proof | Exact global + SWA names present in both graphs; old global names absent |
| Cache-contract preservation | All 15 four-way AR1/AR128 datatype/scale/offset signatures remain identical |
| Corrected private stage | 17 files / 4,003,765,361 logical bytes; hashes, deps, runtime completeness, and modes pass |
| Attempt 04 provider proof | Verified SM8550 QnnHtp/QnnDsp; corrected context/dialog loaded; 2 AR128 + 15 AR1 executions status `0x0` |
| Runtime fallback boundary | 0 QNN CPU-backend markers and 0 runtime-fallback markers |
| Bounded output | 16 tokens / 82 bytes / SHA `c7f1bbe3…e44c`; coherent partial text; sanity true/null |
| Viability profile | Init 1.900 s; TTFT 0.523 s; prompt 327.332 tok/s; generation 17.572 tok/s; one-run only |
| Fatal prompt identity | Bound 170 tokens / one BOS; runtime 171 and log `[2, 2, …]`; automatic extra BOS proven |
| Attempt 04 campaign boundary | Effective prompt was noncanonical; bounded execution/profile remain page-only |
| BOS suppression | Config-only `bos-token: 2` → `-1`; QAIRT source prepends only for nonnegative values |
| Identity preservation | Model, context, LUTs, workload/rendered bytes, and tokenizer unchanged |
| Host-effective sequence | 170 tokens, exactly one leading BOS, prefix `[2, 105, 9731, …]`, SHA `31a85f9c…ad78` |
| Canonical-BOS-corrected stage | 17 files / 4,003,765,362 logical bytes; hashes, deps, runtime completeness, modes pass |
| Attempt 05 effective input | Runtime profile 170 tokens; one BOS; 157 complete logged IDs match committed sequence before truncation |
| Attempt 05 provider proof | 2 AR128 + 15 AR1 QnnDsp executions; starts=done=17; all status `0x0`; no CPU/runtime fallback markers |
| Attempt 05 output | 16 tokens / 89 bytes / SHA `70711436…6357`; coherent partial fragment; sanity true/null |
| Attempt 05 profile | Init 2.095 s; TTFT 0.528 s; prompt 321.854 tok/s; generation 17.703 tok/s; viability only |
| Cleared blocker | Automatic extra BOS absent; bounded physical effective sequence matches canonical single-BOS identity |
| Remaining campaign boundary | Max16 viability is not the 2048-ceiling first/warm distribution |
| Harness loaded route | One process; one refcounted shared QnnHtp engine retained by unqueried keeper dialog |
| Request isolation plan | Fresh dialog + independent `EngineState` per request, applied before query and freed afterward |
| Exact campaign order | 16 requests: first short + 5 short + 5 medium + 5 long; exact prompt hashes; max 2048 each |
| Per-request evidence | Unique raw output/profile, separate dialog/query timing, independent validation |
| Failure policy | 1,800 s timeout kills process; no retry; partial/missing files remain error evidence |
| Campaign stage | 20 files / 4,003,790,569 logical bytes; hashes and permissions verified |
| Launch preflight result | Local exit 126 / `Permission denied`; empty stdout; runner body never entered |
| Phone/campaign boundary | No `phone.lock`, ADB, remote root, process, request, output, profile, metric, or retry |
| Executable fix | Git mode only: `100644` → `100755`; syntax and `test -x` pass |
| Design/scope effect | None; exact shared-engine/fresh-dialog 16-request plan unchanged |
| Physical setup passed | Lock, identity, local/remote hashes, dependencies, push, and Genie process startup |
| Shared-engine schema blocker | Dialog extraction passed `cache-groups` into standalone Engine; key rejected |
| Failure depth | Keeper + 16 request-dialog creates failed; exit 1; provider/context/query/graph never reached |
| Request/evidence boundary | 0 logical requests, outputs, or metrics; setup +16 profiles retained with null components |
| Campaign attempt 01 status | Setup failure only; no physical isolation proof, distribution, performance, or registry result |
| Corrected loaded route | One process, one normal QnnHtp dialog/context, `shared-engine=false`; both `past_` and `swa_` groups retained |
| Reset isolation plan | 15 public `GenieDialog_reset` calls before requests 2–16; no model remap |
| Source-proven reset scope | Counters, pending/last tokens+embeddings, HTP KV/model, sampler/grammar/Harmony, dialog state |
| Corrected campaign shape | Exact first+5 short+5 medium+5 long, 16 queries, max 2048 each |
| Profile accounting | Cumulative snapshots; newly appended query event per request; reset timestamps measured separately |
| Corrected stage | 20 files / 4,003,786,019 logical bytes; hashes/modes verified |
| Canonical campaign | Complete: 1 first short + 5 short + 5 medium + 5 long; max 2048; 0 timeout/error/retry |
| Loaded-route isolation | One process/context/dialog; 15 source-proven full resets; cumulative event growth validated |
| Physical provider proof | 117 AR128 + 15,158 AR1 = 15,275 QnnDsp completions status `0x0`; zero CPU/runtime fallback/fatal markers |
| Setup | 2.112 s through one loaded dialog ready for first request |
| Warm short median | TTFT 462.433 ms; prefill 367.647 tok/s; Genie generation rate 19.584 tok/s; 474 tokens/EOS |
| Warm medium median | TTFT 907.551 ms; prefill 654.879 tok/s; Genie generation rate 18.774 tok/s; 418 tokens/EOS |
| Warm long median | TTFT 2,605.519 ms; prefill 740.741 tok/s; Genie generation rate 17.828 tok/s; 2,048/max |
| Registry decode boundary | Null: Genie does not define first-token inclusion in its generation rate |
| Output sanity | Short/medium true; all 5 long false: `Severe repetition collapse in the exact max-token output.` |
| Process memory | Peak PSS 344,201 kB / VmHWM 460,200 kB; HTP-private unavailable, sparse samples may miss peaks |
| Thermal/battery | Status 0→4; skin 35.9→49.0°C; AP 37.8→57.1°C; battery 58→52%, USB-powered |
| Raw provider log | 399,795,157 bytes, hash-bound and losslessly gzip-retained |
| Cleanup | Scoped root/process absent and `phone.lock` released |
| Android LLM registry row | None; toolchain capability evidence is not registry-eligible |

Attempt chronology remains intact: the initial campaign setup failed before any request on the invalid shared-engine schema, and the corrected full-reset campaign is a distinct complete attempt rather than selective request reruns. The successful attempt proves execution and loaded-route performance distributions while retaining every output and the long-tier failure.

### Post-completion improvement boundary

| Improvement evidence | Current result |
|---|---|
| First qualifying diversity window | Start index 83 zero-based / generated token 84 / absolute position 2,012; ratio 0.248; window start, not causal onset |
| Stable loop | Period 9 from token 479 / absolute 2,407; final 1,570 tokens; dominant pattern 215× |
| Capacity hypothesis | Excluded: generation ends at absolute 3,977, below context capacity 4,096 |
| LiteRT references | GPU/CPU coherent and EOS at 756; no periodic suffix; same rendered bytes but different artifact/tokenizer |
| Causality boundary | Text diverges at first word; no token-ID/logit/state equivalence or numerical-causality claim |
| Candidate 1 | Request-level hybrid: QNN HTP short/medium + LiteRT GPU long; explicit backend per complete request |
| Long completion comparison | GPU 48.311 s vs HTP 118.256 s, 59.147% shorter; output counts/stops differ (756 EOS vs 2,048 max) |
| Decode comparison | Null for ranking: Genie first-token inclusion unspecified; LiteRT explicitly excludes it |
| Candidate 2 | Selected global-value FP16: short compatibility passed, but exact-long output/repetition unchanged; no text benefit on this request |
| Retained attempts 01–03 | Two import/loader-path failures and one encoding-removal preflight failure; all before conversion |
| Attempt 04 patch scope | AR1 removes 6 selected encoding entries, AR128 removes 3; other I/O/encodings/weights unchanged |
| Attempt 04 interruption | App-priority `STOP` → TERM before DLC; owned group reaped; no automatic restart; not model/numerical failure |
| Attempt 05 AR1 gate | DLC 2,356,848,948 B / SHA `4e67d80e…a6cc`; 6 selected input/output interfaces Float16; other shapes/signatures unchanged |
| Conversion-count result | 6,875 operators; Convert 31→31; no demonstrated count reduction or speed benefit |
| Precision warnings | 75→81 (3 Concat + 3 Cast); not CPU-provider fallback or full-delegation proof |
| Attempt 05 AR128 failure | Errno 28 dumping external data to `/tmp` tmpfs; host storage failure, no AR128 DLC |
| Scratch cleanup | Exact owned 8,263,168,000-byte partial file hash retained; only traceback-bound scratch removed |
| Inspection chronology | First read-only inspection timed out; second completed; no conversion/inference retry |
| Source-only reuse helper | `bbd1eec`: pinned read-only AR1 reuse, separate reused/new receipts, mismatch refusal, mandatory actual pair gate |
| Attempt 06 artifacts | AR1 `4e67d80e…a6cc` reused unchanged; only new AR128 2,356,859,020 B / SHA `48fc15f0…7b64` |
| Actual paired-cache gate | Selected global inputs/outputs Float16; other signatures/dimensions unchanged; all 30 four-way datatype/encoding contracts match |
| AR128 operator observations | 6,830→6,842; Convert 30→36, +3 Cast/+3 Dequantize; no count-based speed benefit |
| AR128 precision warnings | 15→21; not a CPU-provider fallback count or full-delegation proof |
| Attempt 06 scratch/processes | Owned disk-backed `QAIRT_TMP_DIR` used; scratch empty/removed and processes reaped |
| Context compile recipe | Unchanged hash-pinned accepted recipe; only paired DLC substitutions and fresh storage paths |
| Improvement context | 1,186,430,976 B / SHA `1d80d016…ca9f8`; +61,440 B versus baseline; HTP backend 6 / SoC 43 / v73 |
| Compiled cache metadata | Original 38-in/31-out AR1/AR128 aliases; all 30 four-way contracts match; all 120 boundaries `FLAT_BUFFER` |
| Source/API limits | Byte-copy rationale only; key-derived FP16 negative-zero clear; NativeKV uint8-only and not selected; dump/export semantics untested |
| Unsupported-op count | Null: native logs can be suppressed at accepted verbosity; not a zero-unsupported or CPU-free execution claim |
| Frozen stage | `212f0d4`: 21 payload files / 4,003,855,761 B; manifest `58484160…fe25`; independent copies, runner0555; baseline unchanged |
| Frozen config/input boundary | Config `f8008e04…7eba`, libraries/LUTs/tokenizer/BOS and short/long bytes unchanged; no new tokenization |
| Diagnostic chronology | Gate A short/max16 and separately released Gate B exact-long/max2048 each executed once; original stages/evidence retained |
| Controller readiness | `62b8a16`: plan-only default; actual fresh one-use Pi attestation, full phone.lock, exact device/build and local/remote hashes required |
| Deadlines | Host process + remote watchdog 1,800 s; bounded phase waits, not guaranteed immediate termination; no automatic retry |
| PID limitation | Starttime/exe/argv checks before numeric signal; no atomic/pidfd binding, residual check-to-signal race remains |
| Retention/cleanup | Raw before optional metrics; unknown PID is not signalled; unknown process state or incomplete pull retains root/cleanup-incomplete status |
| Offline test boundary | 40 fake controller cases / 104 owner tests; no real ADB, actual repository lock, runtime/model load or phone |
| Physical Gate A | `81f4ede`: one context/dialog/query; 2 AR128 + 15 AR1 QnnDsp completions status 0; SMART_MASK |
| Bounded provider observations | No CPU-backend/runtime-fallback/cache-quantization-error markers; not universal CPU-free placement or uniform-integer proof |
| Input evidence | Exact prompt echo, profile 170; 157 complete logged prefix IDs/single BOS verified, logger then truncated |
| Short output/sanity | 16 tokens / 89 B / `70711436…d6357`, identical bounded baseline; true/null sanity only |
| Stop-cause boundary | Configured 16-token ceiling reached, normal query return; independent EOS-versus-limit enum null |
| Raw timing boundary | Creation 2,178,751 µs / query 1,478,281 µs / reported TTFT 486,106 µs; one engineering observation |
| Decode normalization | Raw 17.6189728 tokens/s; first-token inclusion undefined, normalized decode null; no speed-win claim |
| Missing memory | No process sample or live-native PID sample; PSS/VmHWM/HTP-private totals null |
| Cleanup/privacy | Natural exit; recorded roles/root absent, raw first, no signal; full battery private, public labelled core extracts only |
| Exact-long host readiness | `b43a57f`: 18 files / 4,003,852,753 B, manifest `047dd808…b846e`; same context/config, one fresh 1,929-input/max2048 query, 1,800 s bounds; later executed separately |
| Long lifecycle boundary | Fixed hash-pinned adaptation, direct-nohup absolute redirections and host FIFO/reaping test; no Android detachment or timing proof |
| Physical Gate B | `e585e79`: 1,929 input / 2,048 generated; 16 AR128 + 2,047 AR1 status-0 executions; one process/dialog/query, SMART_MASK |
| Long-output verdict | Full 10,027 B / `f0e9d284…97b2d` identical to all five baseline outputs; severe repetition/`<unk>` remains, sanity false |
| Frozen repetition result | Window starts at index 83 / ratio 0.248, not causal onset; period-9 suffix starts at index 478 and spans 1,570 tokens; all declared metrics unchanged |
| Long stop/rate limits | Cap 2048 reached, independent stop enum null; raw query 109.901620 s / rate 19.1982803 tokens/s, normalized decode null; no speed win |
| Long retention/cleanup | 54,108,333 B log losslessly gzip-retained; live PID validated, natural exit, roles/root absent, no signals; full battery private/core extracts public |
| Remaining hypotheses | Negative for this selected global-value FP16 candidate/request; internal quantization may remain, other cache-precision causes not disproven |
| Remaining candidate evidence | Numerical fidelity, reset/reuse and unused cache APIs, broader placement and normalized performance remain unproven; no new campaign |
| Mixed-commit review scope | Gemma slice of `f637a74` only; no app/gallery publication or approval |
| Routing-policy boundary | Unmeasured request-level recommendation; no built/measured hybrid or general length threshold |
| Publication effect | Completed campaign/card/registry unchanged; new short compatibility is page-only, not a campaign rerun or new registry evidence |

No paid Workbench job ran. Output sanity is a narrow corruption/repetition screen, not model quality. The Android LLM registry remains the immutable complete physical campaign row with the five long failures, thermal escalation, process-memory scope, unavailable HTP-private memory, and undefined decode first-token semantics preserved.

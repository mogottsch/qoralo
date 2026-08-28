# Plan: LFM2.5-2.6B QNN/HTP

## Completed

1. Preserved `0029` and `0033` as immutable prior evidence and reserved independent `0034` ownership.
2. Re-verified the canonical Android LLM protocol and exact short/medium/long workload hashes.
3. Bound the exact `LiquidAI/LFM2.5-2.6B` source revision `ab006873…`, both safetensor sizes/hashes, the 22-convolution + 8-attention architecture, tokenizer, native template, and canonical 171/600/1922-token inventories.
4. Retained the earlier negative assessment: installed QAIRT's high-level GGUF/factory route has no LFM2 dispatch. That assessment is a rejected route, not the solution boundary.
5. Obtained Moritz's explicit license authorization for public `onnxruntime-qnn==2.5.0`, `com.qualcomm.qti:onnxruntime-android-qnn:2.5.0`, and `com.qualcomm.qti:qnn-runtime:2.49.0`; restricted packages and derivatives stay outside Git.
6. Pinned the architecture-aware LiquidONNX exporter at commit `9a23ddd…` under the same already-bound LFM Open License.
7. Exported the exact source as symmetric block-32 Q4 ONNX, preserving all recurrent convolutional and attention cache state.
8. Replaced an invalid contrib-op domain emission with an explicit standard-ONNX RMSNorm decomposition; the rewritten graph passes `onnx.checker`.
9. Passed a bounded host CPU smoke with the exact canonical short prompt and retained output bytes/hash. This is host viability only.
10. Built a one-token, 4,096-capacity explicit-state route and lowered RoPE/GQA to standard ONNX while retaining new K/V slices and 22 convolution states as graph I/O.
11. Declared the unsupported block-Q4 embedding as an explicit CPU selected-row frontend rather than allowing fallback. Transformer/state/final-norm/LM-head compute remains in QNN-owned parts; CPU performs the global greedy reduction and tokenization.
12. Solved v73 preparation limits without changing weights:
    - split 10,752-wide MLP projections into 6,144 + 4,608;
    - zero-pad only the second down-projection activation and quantized weight blocks to K=6,144;
    - split graph preparation into memory-bounded ordered contexts;
    - split the 128,000-wide LM head into 22 HTP chunks.
13. Compiled all 263 contexts for SoC model 43 / SM8550 / HTP V73 using ONNX Runtime QNN EP 2.5.0, block-quant optimization, and `session.disable_cpu_ep_fallback=1`.
14. Validated every framework-op trace: all 1,583 source nodes map to 2,747 QNN ops with zero unsupported nodes. The 1,779,492,144 bytes of contexts remain outside Git.
15. Replayed the exact 171-token canonical short prompt through the final split ordering on the host with zeroed state; its first five greedy tokens matched both transformed-monolith and original export references. This is wiring/viability evidence, not Android performance.

16. Built the native API-31 AArch64 phone runner and a locally verified 540-file ignored stage containing the 263 context pairs, public Android runtime libraries, exact Q4 embedding tables, and exact 171-token short prompt.
17. Ran one full-lock physical attempt after RSA authorization. Exact identity and all stage hashes passed, but the first EPContext remained unclaimed; fallback-disabled ORT stopped before session/model execution. Preserved the raw failure and verified scoped cleanup absent.
18. Updated the runner to log all EP device types and select only the Android QNN NPU device; rebuilt and hash-bound the replacement runner/stage.
19. Ran the one authorized retry under the full lock lifecycle. ORT advertised the Qualcomm NPU and the runner selected it exclusively, but QNN EP 2.5.0 still did not claim `layer-00-core-norm`'s matched host-AOT EPContext. Fail-closed stopped before execution; all hashes passed; cleanup was absent and the lock released.
20. Stopped without a campaign and retained the complete raw blocker evidence.

21. Moritz selected and authorized the direct-QNN continuation.
22. Built an API-31 AArch64 runner that loads the same 263 contexts once through public QNN APIs and preserves the explicit state and CPU embedding/orchestration/global-argmax boundaries.
23. Proved the first exact context loads, retrieves, and executes directly on the host HTP emulator; outputs are finite and bounded against the CPU reference.
24. Assembled and locally verified a complete ignored direct-QNN phone stage.
25. Ran one bounded physical gate; the Android linker stopped before `main` because the stage omitted `libc++_shared.so`. Preserved raw evidence and verified cleanup absent.
26. Added the exact NDK r28b `libc++_shared.so`, rebuilt the 273-file manifest, and added an architecture-aware DT_NEEDED preflight that runs before phone.lock or ADB.
27. Ran the corrected direct-QNN phone gate. The runtime loaded 57 exact contexts, then context 58 (`layer-07-up-0`) failed in `QnnContext_createFromBinary` before readiness/graph execution. Preserved raw evidence and verified cleanup absent.
28. Probed ORT shared EP contexts: 263 ordered graphs compiled into 33 binaries, but host retrieval rejected the shared-weights buffer. Retained this as a rejected diagnostic rather than assuming Android support.
29. Fused each layer's eight sequential parts into one graph and grouped four independent LM-head chunks per graph, reducing the loaded route to 37 ordinary contexts without context reload.
30. ONNX-checked all 37 models and compiled every context fallback-disabled for SM8550/V73.
31. Revalidated all traces: 1,583/1,583 source nodes map to 2,747 QNN operations with zero unsupported nodes.
32. Compared five token steps against the 263-part CPU route: all greedy decisions match, and all logit/state deltas from changed optimization boundaries are retained.
33. Loaded and executed fused layer 0 in x86 HTP emulation; both hidden/state outputs are finite and close to CPU reference.
34. Rebuilt the direct runner for consolidated graph ABIs and prepared a hash-bound 48-file Android stage with 37 contexts; ELF and manifest preflights pass.
35. Ran one authorized physical fused-route gate. Direct QNN loaded 19 fused layer contexts, then failed creating context 20 (`layer-19`) before route readiness or graph execution. Preserved raw evidence and verified cleanup absent.
36. Reclassified the blocker as physical resident QNN/DSP resources rather than a simple context-count or process-RSS threshold.
37. Compiled all 37 fused graphs into one 1,601,482,752-byte shared-resource SM8550/V73 QNN context while retaining their exact order.
38. Verified QNN system metadata and every graph descriptor: 37/37 graph names bind in order to the one binary.
39. Confirmed the x86 HTP emulator rejects the shared-weights buffer as unsupported on that host platform; physical Android support remains unproven.
40. Prepared a 12-file ignored Android stage whose runner loads one context once and retrieves all 37 graphs; hashes and ELF preflight pass.
41. Ran one authorized physical shared-context gate. All stage checks passed, but `QnnContext_createFromBinary` rejected the 1.60 GB context before graph retrieval/readiness/execution.
42. Preserved the raw result, verified scoped cleanup absent, and stopped without retry or campaign.

43. Moritz authorized an exact-runtime correction after identifying that the physical single-context attempt used Android backend v2.49.0 against a v2.49.40 host context.
44. Rebuilt the ignored 12-file stage with licensed QAIRT 2.49.40 Android HTP/stub/skel libraries. Context and runtime build IDs exactly match `v2.49.40.260810104044`; hashes, ABIs, SONAMEs, and dependencies are bound and verified.
45. Ran one authorized matched-runtime physical gate. The backend build ID exactly matched the context, but context creation still failed before graph retrieval/readiness/execution.
46. Preserved raw evidence and verified scoped cleanup absent plus lock release. Runtime mismatch is ruled out and option 1 will not be retried.

47. Merged the 37 fused regions into one ordinary monolithic one-token ONNX graph with 38 explicit state inputs, 38 state outputs, and 22 logit chunks; no shared-resource/weight-sharing format or streaming.
48. Compiled one fallback-disabled SM8550/V73 QNN subgraph: 1,541/1,541 optimized source nodes supported, 2,698 QNN operations, zero unsupported nodes.
49. Verified ordinary context metadata: one 1,600,097,976-byte context, one graph, 41 inputs, 60 outputs, build `v2.49.40.260810104044`.
50. Loaded once and executed the complete graph through x86 HTP emulation; position-zero greedy token 124894 matched both prior CPU reference routes.
51. Built the ignored exact-runtime Android stage and passed local hash plus ELF preflight without phone access.
52. Ran one authorized physical position-zero gate under `phone.lock`: all 12 stage hashes passed, the ordinary context loaded once, one graph loaded, and one direct-QNN HTP graph execution completed.
53. Verified global argmax 124894 exactly matches both CPU routes and x86 HTP; preserved timing as a single diagnostic only.
54. Preserved raw provider, hashes, identity, input/output, memory, thermal/power, and cleanup evidence; remote root absent and lock released.
55. Ran the smallest feasible host multi-step check: first two canonical-short tokens through one loaded context and two x86 HTP graph executions.
56. Carried all 38 states, advanced position/mask, and matched both CPU references at position 1 with global argmax 25.
57. Ran one authorized physical two-step gate: loaded one ordinary context/graph once and completed two sequential direct-QNN HTP executions without reload.
58. Verified position-1 global argmax 25 across physical, CPU, and x86 HTP; preserved diagnostic-only timing and process-memory limits.
59. Preserved exact provider/stage/prefix/output/memory/thermal/identity/cleanup evidence; remote root absent and lock released.

## In progress

1. Commit and independently review the physical two-step loaded-state evidence.
2. Stop all ADB and expanded workload activity until a separately agreed next gate receives explicit authorization.
3. Context streaming remains prohibited. No full canonical completion, output-quality, campaign, performance, or registry claim.

## Phone and campaign sequence

1. obtain Pi's phone priority handoff;
2. acquire `artifacts/locks/phone.lock` for the full ADB lifecycle;
3. stage only under the experiment-scoped remote root and verify every deployed hash;
4. record identity, Android build, battery/thermal/storage state, and startup boundaries;
5. run one bounded viability request and retain physical HTP logs/profile evidence;
6. if viable, run one first short request plus five additional short, five medium, and five long requests on one loaded route;
7. retain all outputs, timings, memory, thermal/power context, stop reasons, sanity states, and cleanup proof;
8. publish normalized registry rows only after experiment evidence is committed and handed to Kate.

## Stop conditions

Stop and report rather than weaken the claim if any model/state context fails physical HTP loading/execution, explicit CPU work expands beyond the declared embedding/orchestration/global-argmax boundary, cache reset cannot be proven, the phone cannot retain the complete loaded route, or a different license/export-control/paid-service checkpoint appears. CPU/GPU provider fallback, a generic target declaration, or text without physical provider proof is not success.

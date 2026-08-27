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

## In progress

1. Build static profiles:
   - short prefill: sequence 171;
   - medium prefill: sequence 600;
   - long prefill: sequence 1,922;
   - decode: sequence 1;
   - shared maximum attention KV capacity: 4,096;
   - recurrent convolution cache: 22 explicit `[1, 2048, 3]` states.
2. Lower the Q4 embedding to an HTP-owned representation while preserving the 167 block-quantized matrix routes.
3. Generate fallback-disabled SM8550 / HTP v73 AOT contexts through Qualcomm ONNX Runtime QNN EP 2.5.0 with block-quant-to-LPBQ optimization and framework-op tracing enabled.
4. Validate QNN graph ownership, profile I/O/cache geometry, host equivalence, and reset semantics.

## Phone and campaign sequence

Only after AOT/provider gates pass:

1. obtain Pi's phone priority handoff;
2. acquire `artifacts/locks/phone.lock` for the full ADB lifecycle;
3. stage only under the experiment-scoped remote root and verify every deployed hash;
4. run one bounded viability request and retain physical HTP logs/profile evidence;
5. run one first short request plus five additional short, five medium, and five long requests on one loaded route;
6. retain all outputs, timings, memory, thermal/power context, stop reasons, sanity states, and cleanup proof;
7. publish normalized registry rows only after experiment evidence is committed.

## Stop conditions

Stop and report rather than weaken the claim if fallback-disabled compilation fails, any model/state operator remains outside HTP, cache reset cannot be proven, the phone cannot load the exact contexts, or a different license/export-control/paid-service checkpoint appears. CPU/GPU fallback, a generic target declaration, or text without physical provider proof is not success.

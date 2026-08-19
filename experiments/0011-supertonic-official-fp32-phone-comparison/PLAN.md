# Plan — official Supertonic 3 FP32 phone comparison

## Scope

Execute the bounded phases below against pinned, ungated, first-party **official FP32 ONNX inference/export assets**. Do not authenticate, accept click-through terms, use a PyTorch/training checkpoint, quantize, calibrate, optimize a QNN context, rebuild ORT, edit experiment 0010, or create a hybrid route. The later authorization permits only the exact stable `Softplus` expansion in phase 3; no other operator rewrite is in scope.

## Step 1 — official FP32 phone CPU

1. Record first-party revision, access state, OpenRAIL-M license, Git/LFS metadata, sizes, and SHA-256 hashes before use.
2. Validate all four ONNX contracts and run a complete host CPU sanity check.
3. Use official config, Unicode indexer, and M1 style with the frozen transcript, seed `20260813`, and predeclared `T239/L238/729746` contract. Run duration prediction but do not derive a new deployment shape from it.
4. Under the phone lock and exact identity gates, run duration predictor → text encoder → vector estimator five times → vocoder → trimmed WAV entirely on CPU.
5. Preserve session, first, warm, component, and end-to-end timing; output hashes/validity; cumulative RSS high-water; and ORT profiles showing zero QNN events. Pull evidence, remove the unique remote stage, and release the lock.

**Gate:** pass only if the complete text-and-M1-to-WAV chain succeeds with finite output of the declared size and all profiled kernels identify `CPUExecutionProvider`.

## Step 2 — official FP32 fail-closed HTP attempt

1. Specialize graph I/O shapes only. Prove ordered node protobufs, ordered initializer protobufs, operator sequence, and graph interface names unchanged.
2. Run dynamic and specialized graphs on CPU after freezing equivalence thresholds; preserve the numerical report.
3. Host-gate each component independently through patched ORT 1.27.1 + QNN 2.49.0 with `session.disable_cpu_ep_fallback=1`. Record partition/node counts and every unsupported node. Stop any rejected component before phone.
4. For each fully delegated component, freeze output/profile criteria and physically probe real chain-derived inputs on the authorized S23 with detailed profiling and exact provider options.
5. Run complete HTP transcript-to-WAV only if all four components fully delegate and pass their component gates. Otherwise stop with an incompatibility map; never enable fallback or silently create a hybrid.

**Gate:** physical execution requires RPC execute time, QNN accelerator execute time, accelerator cycles, and HVX-thread evidence. “Official FP32 source” must not be restated as “FP32 HTP arithmetic” unless lowering precision is independently established.

## Phase 3 — stable Softplus and matched complete routes

1. Hash-lock the rejected specialized vector. Replace exactly its one `Softplus` with `Relu(x) + Log(1 + Exp(-Abs(x)))`; prove wiring, opset, dtype, shape, consumer safety, deterministic serialization, and preservation of all other ordered nodes and original initializers.
2. Freeze numerical thresholds. Compare original and rewritten vectors on CPU under the same runtime for every real step input and both recursive five-step chains.
3. Require one complete fallback-disabled host QNN partition. Validate the existing Android package and hashes offline, then physically probe the rewritten vector with real inputs and unambiguous QNN/RPC/accelerator/cycle/4-HVX evidence.
4. Freeze the matched benchmark protocol. Run fresh all-HTP and CPU route processes in the predeclared order with cooldowns and thermal snapshots. Preserve six executions per route, component/session/setup/end-to-end latency, RTF, cumulative RSS high-water, output hashes, full profiles, and a prospective full-tensor comparison.
5. Keep listening separate. Do not generate the final HTML comparison in this phase.

**Gate:** call the route all-HTP only if duration, text, each of the five recursive vector calls, and vocoder have QNN-only ORT provider events, zero CPU-provider events, and physical QNN profiling evidence.

## Outcome

Steps 1 and 2 produced the official CPU baseline and isolated one unsupported vector `Softplus`. Phase 3 replaced only that node, passed CPU and host/physical vector gates, and achieved a complete all-HTP route. Its warm generation median was 2.818 seconds versus 8.068 seconds on CPU, but the prospective E2E numerical policy failed because cosine `0.92668` was below `0.95`. Moritz did not review either sample, so listening quality remains unknown; technical execution and structural validity are not acceptance.

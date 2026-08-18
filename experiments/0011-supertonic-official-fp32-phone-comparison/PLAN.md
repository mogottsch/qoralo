# Plan — official Supertonic 3 FP32 phone comparison

## Scope

Execute only these two steps against pinned, ungated, first-party **official FP32 ONNX inference/export assets**. Do not authenticate, accept click-through terms, use a PyTorch/training checkpoint, quantize, calibrate, rewrite operators, optimize a QNN context, rebuild ORT, edit experiment 0010, or create a hybrid route.

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

## Outcome

Step 1 passed. In step 2, duration prediction, text encoding, and vocoding fully delegated and passed their physical execution/profile criteria. The vector estimator failed closed on one unsupported `Softplus`, so complete HTP synthesis and matched CPU/HTP listening artifacts were not eligible.

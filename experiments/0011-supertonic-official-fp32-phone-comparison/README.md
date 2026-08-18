# Experiment 0011 — official Supertonic 3 FP32 phone comparison

## Question

Can Supertone's **official FP32 ONNX inference/export assets** run end to end on the authorized Galaxy S23 Ultra CPU, and can the same assets fully delegate to QNN HTP without CPU fallback?

This is not a PyTorch or original-training-checkpoint comparison. No public training checkpoint is available.

## Inputs

The ungated first-party source is pinned to Hugging Face revision [`724fb5abbf5502583fb520898d45929e62f02c0b`](https://huggingface.co/Supertone/supertonic-3/tree/724fb5abbf5502583fb520898d45929e62f02c0b), licensed under OpenRAIL-M. [`results/source-inventory.json`](results/source-inventory.json) records exact sizes, SHA-256 hashes, Git object IDs, and complete LFS metadata.

The comparison contract is:

- transcript SHA-256 `350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f`;
- official `tts.json`, `unicode_indexer.json`, and M1 style;
- seed `20260813`;
- predeclared `T239 / L238 / 729746`-sample deployment shape;
- authorized phone `R5CW81PR8SY` / `SM-S918B` / `SM8550`.

The duration predictor still runs. Its `16.9202`-second prediction is reported, but this fixed comparison does not rebuild the deployment graph shape from that prediction.

## Result

### Step 1 — complete phone CPU: passed

All four official components ran CPU-only from text and M1 conditioning through WAV generation, with no neural intermediate substitution:

| Metric | Result |
|---|---:|
| Session creation, all components | 0.722 s |
| First end-to-end run | 6.529 s |
| Warm end-to-end runs | 6.766 / 6.897 / 6.870 s |
| Warm median | 6.870 s |
| Duration predictor, warm range | 8.0–8.8 ms |
| Text encoder, warm range | 80.7–82.0 ms |
| Vector estimator, five steps, warm range | 5.464–5.562 s |
| Vocoder, warm range | 1.212–1.274 s |
| Process RSS high-water after runs | 569196 KiB |

The 729746-sample output is finite and a valid mono 44.1 kHz PCM16 WAV. All four ORT profiles contain only `CPUExecutionProvider` kernel labels and zero QNN events. See [`results/step1-phone-cpu-checkpoint.json`](results/step1-phone-cpu-checkpoint.json).

### Step 2 — fail-closed full HTP: bounded incompatibility

Only graph I/O shapes were specialized. Ordered nodes, initializers, weights, and operators remained byte-identical, and the specialized CPU chain passed the predeclared equivalence policy (`max abs 0.000366`, `RMSE 0.00000700`, cosine `0.999999991`).

Host gates used patched ORT 1.27.1 with QNN 2.49.0 and `session.disable_cpu_ep_fallback=1`:

| Component | Host gate | Physical S23 HTP probe |
|---|---|---|
| Duration predictor | 1 partition, all 205 optimized nodes | passed; RPC/accelerator/cycle/HVX evidence |
| Text encoder | 1 partition, all 343 optimized nodes | passed; RPC/accelerator/cycle/HVX evidence |
| Vector estimator | **rejected**: 2 partitions, 867/868 nodes | not attempted |
| Vocoder | 1 partition, all 135 optimized nodes | passed; RPC/accelerator/cycle/HVX evidence |

The vector estimator leaves one unsupported node:

```text
/vector_estimator/vector_field/time_encoder/mlp/mlp.1/Softplus (Softplus)
```

Therefore a complete all-four-component HTP transcript-to-WAV run was **not attempted**. No hybrid route or CPU fallback was enabled. The three eligible physical probes used real inputs produced by a complete official FP32 host chain. See [`results/step2-fail-closed-htp-checkpoint.json`](results/step2-fail-closed-htp-checkpoint.json).

## Claim boundaries

- “FP32” describes the public source ONNX assets. Physical HTP profiles prove accelerator execution but do not establish FP32 arithmetic or identify the internal QNN lowering precision.
- The minimal C++ runner hard-codes the pinned contract values from `tts.json` and consumes lossless binary serializations of the official JSON Unicode indexer and M1 float tensors; these adapters do not replace neural intermediates.
- CPU `ru_maxrss` is cumulative process high-water RSS, not component-isolated PSS; it includes runtime, loaded models, and allocator memory.
- Physical component numerical comparisons are descriptive because only output shape, finiteness, and accelerator-profile criteria were frozen before those outputs.
- No quantization, calibration, operator rewrite, QNN context optimization, ORT patch/rebuild, or experiment 0010 modification was performed here.
- Models, tensors, audio, profiles, Qualcomm binaries, serial logs, and local run directories remain ignored.

## Files

- [`PLAN.md`](PLAN.md) — bounded two-step procedure and gates
- [`results/source-inventory.json`](results/source-inventory.json) — pinned first-party inventory
- [`results/specialization-policy.json`](results/specialization-policy.json) — predeclared CPU-equivalence criteria
- [`device/htp-probe-policy.json`](device/htp-probe-policy.json) — frozen physical-probe criteria
- [`host/official_fp32_e2e_runner.cc`](host/official_fp32_e2e_runner.cc) — deterministic Android/host end-to-end runner
- [`host/official_fp32_component_probe.cc`](host/official_fp32_component_probe.cc) — fail-closed component probe

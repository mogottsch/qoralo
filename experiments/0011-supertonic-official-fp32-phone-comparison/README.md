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

### Step 1 — complete phone CPU: technical pass

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

The 729746-sample output is finite and a structurally valid mono 44.1 kHz PCM16 WAV. “Structurally valid” means the format and numeric checks passed; it is not a listening-quality judgment. All four ORT profiles contain only `CPUExecutionProvider` kernel labels and zero QNN events. See [`results/step1-phone-cpu-checkpoint.json`](results/step1-phone-cpu-checkpoint.json).

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

Therefore a complete all-four-component HTP transcript-to-WAV run was **not attempted** in step 2. No hybrid route or CPU fallback was enabled. The three eligible physical probes used real inputs produced by a complete official FP32 host chain. See [`results/step2-fail-closed-htp-checkpoint.json`](results/step2-fail-closed-htp-checkpoint.json).

### Stable Softplus phase — complete all-HTP technical route achieved

The exact rejected `Softplus` was replaced by:

```text
Relu(x) + Log(1 + Exp(-Abs(x)))
```

The expansion is stable because `Exp` never receives a positive value. The rewrite is source-hash locked, deterministic, and changes only that node: seven standard-domain nodes replace it and one scalar float32 constant is appended. Five focused safety tests passed. Same-runtime CPU comparisons passed the frozen policy for every real step input and the recursive five-step chain; final recursive max error was `0.00004796`, RMSE `0.000001404`, and cosine `0.99999999998`.

The rewritten vector then fully delegated as one QNN partition (`874/874` optimized nodes), passed a physical fallback-disabled HTP probe, and enabled matched complete phone routes:

| Metric | CPU reference | All HTP |
|---|---:|---:|
| Session creation | 0.792 s | 22.815 s |
| First generation | 7.368 s | 3.091 s |
| Warm generation median | 8.068 s | 2.818 s |
| Warm generation range | 7.587–9.073 s | 2.807–2.841 s |
| Warm RTF | 0.488 | 0.170 |
| Setup-inclusive first result | 8.160 s | 25.906 s |
| Process RSS high-water | 689456 KiB | 1374408 KiB |

Warm generation was `2.86×` faster on the all-HTP route. All 48 neural executions—six duration, six text, thirty recursive vector, and six vocoder—have ORT QNN-provider events plus physical RPC, accelerator-time, cycle, and 4-HVX evidence, with zero CPU-provider node events.

Both 729746-sample outputs are finite, bounded, and structurally valid mono 44.1 kHz PCM16 WAVs. The prospective numerical policy nevertheless **failed**: MAE `0.00704`, RMSE `0.02000`, and cosine `0.92668` versus the frozen `0.95` cosine minimum. See [`results/softplus-matched-e2e-checkpoint.json`](results/softplus-matched-e2e-checkpoint.json).

## Moritz listening verdicts

- Official FP32 CPU sample SHA-256 `8db92db13567b86be503d204fe367f2052b54dbfc99c0f7bfc5b23d9fd431da7`: **accepted**, “Good—even a bit more crisp than samples 1 and 2.”
- All-HTP sample SHA-256 `47c30043ccc053fe11b908a383c2bc9996c003b85ec293bae122c5794294783c`: **accepted**, “Same as sample 3.” This is a perceptual comparison to the accepted CPU sample, not numerical equivalence.

These are exact-sample listening verdicts. The HTP comparison does not erase or pass the failed prospective numerical policy, and neither verdict proves broad-corpus quality.

## Claim boundaries

- “FP32” describes the public source ONNX assets. Physical HTP profiles prove accelerator execution but do not establish FP32 arithmetic or identify the internal QNN lowering precision.
- The minimal C++ runner hard-codes the pinned contract values from `tts.json` and consumes lossless binary serializations of the official JSON Unicode indexer and M1 float tensors; these adapters do not replace neural intermediates.
- CPU `ru_maxrss` is cumulative process high-water RSS, not component-isolated PSS; it includes runtime, loaded models, and allocator memory.
- The matched run used the original I/O-specialized vector for CPU and the audited stable-Softplus derivative for HTP; both model hashes are retained.
- The HTP-first route order, 120-second cooldowns, and thermal snapshots reduce but do not remove ordering and thermal bias. CPU latency increased across its warm runs.
- Apart from the single audited `Softplus` expansion, no operator rewrite was performed. No quantization, calibration, QNN context optimization, ORT patch/rebuild, or experiment 0010 modification occurred.
- Models, tensors, audio, profiles, Qualcomm binaries, serial logs, and local run directories remain ignored.
- Both exact experiment-0011 samples have positive Moritz listening verdicts. Those sample-level verdicts remain separate from the failed HTP numerical gate and do not establish broad-corpus equivalence.

## Files

- [`PLAN.md`](PLAN.md) — bounded procedures and gates
- [`results/source-inventory.json`](results/source-inventory.json) — pinned first-party inventory
- [`results/specialization-policy.json`](results/specialization-policy.json) — predeclared CPU-equivalence criteria
- [`device/htp-probe-policy.json`](device/htp-probe-policy.json) — original frozen physical-probe criteria
- [`results/softplus-phase-policy.json`](results/softplus-phase-policy.json) — frozen rewrite and prospective E2E numerical criteria
- [`results/matched-e2e-protocol.json`](results/matched-e2e-protocol.json) — predeclared matched benchmark protocol
- [`results/vector-softplus-rewrite-provenance.json`](results/vector-softplus-rewrite-provenance.json) — exact rewrite proof
- [`host/official_fp32_e2e_runner.cc`](host/official_fp32_e2e_runner.cc) — deterministic Android/host end-to-end runner
- [`host/official_fp32_component_probe.cc`](host/official_fp32_component_probe.cc) — fail-closed component probe

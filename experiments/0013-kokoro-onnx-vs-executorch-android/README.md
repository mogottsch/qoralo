# Experiment 0013 — Kokoro ONNX Runtime versus ExecuTorch on Android CPU

## Question

For the exact official FP32 Kokoro v1.0 weights and `af_heart` voice, which faithful mobile CPU route is currently viable: unquantized ONNX Runtime or current ExecuTorch/`torch.export`?

## Frozen source and input

- Official repository: [`hexgrad/Kokoro-82M`](https://huggingface.co/hexgrad/Kokoro-82M)
- Revision: `f3ff3571791e39611d31c381e3a41a3af07b4987`
- Checkpoint: `kokoro-v1_0.pth`, SHA-256 `496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4`
- Voice: `voices/af_heart.pt`, SHA-256 `0ab5709b8ffab19bfd849cd11d98f75b60af7733253ad0d67b12382a102cb4ff`
- Code: `kokoro==0.9.4`, wheel SHA-256 `a129dc6364a286bd6a92c396e9862459d3d3e45f2c15596ed5a94dcee5789efd`
- License: Apache-2.0
- Text: [`protocol/transcript.txt`](protocol/transcript.txt), SHA-256 `bec8bf482f4d816f0c95471c289a2607a7a169e33389b8b13e525214ec639461`
- US English; `af_heart`; speed `1.0`; phase/noise seed `20260818`; one requested CPU thread

[`results/source-weight-verification.json`](results/source-weight-verification.json) proves that all 548 checkpoint tensors equal the loaded official modules exactly. The 140 additional state tensors are the official code's default affine `InstanceNorm` ones/zeros, not substituted learned weights. The exact official voice tensor is losslessly serialized to a 522240-byte float32 mobile asset; it also equals the pinned sherpa SID-3 block byte for byte.

PyTorch `.pth`/`.pt` files are source containers, not Android graphs. No community q8/q4 file, experiment-0009 QDQ derivative, QNN, HTP, NNAPI, GPU, or Vulkan path was used.

## Result

Neither route reached a valid Android latency comparison in this bounded experiment.

| Route | Host result | Android result | WAV / latency |
|---|---|---|---|
| Exact-source-derived FP32 ONNX Runtime | Controlled export and host CPU passed the separate deployment-validity policy | **Blocked before ORT environment/session creation** by app visibility of shell-copied scoped-storage assets | None |
| ExecuTorch 1.4 / `torch.export` | **Blocked before a full-model PTE** on the data-dependent duration-expanded sequence consumed by LSTMs | Ineligible; not attempted | None |

### Route A — deliberate fixed-contract FP32 ONNX

The previously pinned sherpa graph is **not** used. Its `disable_complex=True` path substitutes Kokoro's approximate `CustomSTFT`; against official eager with the same input and seed it measured cosine `0.883336` and NRMSE `0.536136`. That is inadequate for this exact-source comparison even though the graph remains useful in earlier deployment experiments.

A controlled graph was therefore exported directly from the exact official checkpoint:

- standard ONNX `STFT` for the official analysis transform;
- a mathematically equivalent real-valued inverse-STFT overlap-add with Hann-envelope normalization;
- the official phase/noise model inputs materialized with PyTorch CPU seed `20260818` and the source tensor's memory-format RNG ordering;
- no learned-weight change, quantized op, random op, or non-FP32 initializer.

The controlled eager wrapper passed its frozen source-equivalence gate:

| Metric | Result |
|---|---:|
| Output / durations | exact shape; exact 125 duration values; sum 304 |
| Cosine | `0.9999999999986571` |
| NRMSE | `0.00000163934` |
| Maximum absolute error | `0.00000107288` |

The 332038651-byte ONNX, SHA-256 `d11a0dd7c4eb768e1f0ef03090c69b6761f55e37b9f196749349591c40be232b`, passed ONNX checker and host ORT 1.23.2 CPU. Host output was finite, non-silent, unclipped, exactly 182400 samples / 7.6 seconds at 24 kHz, and its profile contained 3102 `CPUExecutionProvider` node events and no QNN event.

The original preliminary `.999/.01` waveform screen nevertheless remains an explicit **failure**: host ORT versus the controlled eager wrapper produced cosine `0.9970098725` and NRMSE `0.0847079096`. It is not relabeled. Before any phone output, Pi approved and [`protocol/deployment-fidelity-policy.json`](protocol/deployment-fidelity-policy.json), SHA-256 `22c7f2dd5c3596acf66107c3712c886b827f4a332d13dca981d183f6efc40ad7`, froze a separate valid-audio and phase-tolerant acoustic policy. The host cross-runtime output passed that separate screen (log-mel cosine `0.999453`, log-mel MAE `0.785 dB`, spectral convergence `0.0594`, RMS-envelope correlation `0.999387`). This supports deployment eligibility; it does not erase waveform divergence or constitute listening evidence.

Two authorized phone launches then stopped at asset bootstrap:

1. the original FUSE path was rejected by an over-strict symbolic-path test;
2. after a narrowly corrected canonical containment check and offline tests, the app still saw the correctly hash-staged shell-owned asset as `regular=false` under Android 15 scoped storage.

The second run was the one authorized correction. Per the stop condition, no internal-storage/`run-as` staging redesign or third launch was attempted. Neither launch initialized ORT, created a session, ran a model, or produced audio. Both used the exact identity gate and physical lock; both force-stopped/uninstalled the app, removed the unique `/data/local/tmp` and app-external directories, verified absence, and released the lock. See [`results/phone-onnx-bootstrap-checkpoint.json`](results/phone-onnx-bootstrap-checkpoint.json).

### Route B — bounded current ExecuTorch screen

The exact model fails both strict and non-strict `torch.export` first at a data-dependent SDPA guard. Bounded, source-tested wrappers exposed the deeper blocker:

1. eager attention exposes intentionally skipped `pack_padded_sequence`;
2. removing only no-op pack/pad operations for batch 1 and constructing the known all-ones attention mask exposes `u0`, the duration-driven `repeat_interleave` output length;
3. the subsequent LSTM decomposition cannot extract that data-dependent length, even with nonzero and upper-bound checks.

The official complex inverse STFT exports in isolation but fails ExecuTorch edge lowering at `phase * 1j`. Two real-valued STFT alternatives lower in isolation, but isolated 10–11 KB PTE files are not full-model evidence. The direct all-real full wrapper also misses the source waveform gate (cosine `0.998418`, NRMSE `0.060798`). A complete fix would require captured/fixed alignment semantics, a padded/manual recurrent rewrite, control-flow/custom-kernel work, or another broad model change. Those were explicitly out of scope. No full-model `.pte`, Android ExecuTorch runtime, phone run, sample, or latency exists. See [`results/executorch-export-checkpoint.json`](results/executorch-export-checkpoint.json).

## Conclusion and claim boundaries

- **No Android CPU latency or memory comparison can be claimed.** Both route values are unavailable, not zero.
- The ONNX route is host-eligible as an **exact-source-derived, unquantized FP32, fixed-contract representation**, not waveform-identical official eager execution and not the sherpa `disable_complex=True` graph.
- ExecuTorch is a bounded current export blocker, not a slower or faster measured route.
- The Android ONNX blocker is staging/bootstrap, not an ONNX Runtime compatibility result.
- No sample WAV was produced for Moritz because no authorized phone inference completed.
- No HTP/QNN or quantization work began.
- Models, source weights, wheels, APKs, raw profiles, phone logs, serial evidence, tensors, and audio remain ignored.

## Files

- [`PLAN.md`](PLAN.md) — bounded procedure and stop conditions
- [`protocol/benchmark-policy.json`](protocol/benchmark-policy.json) — matched timing/input contract
- [`protocol/deployment-fidelity-policy.json`](protocol/deployment-fidelity-policy.json) — prospective phone-validity/acoustic gate
- [`results/source-inventory.json`](results/source-inventory.json) — exact hashes, licenses, representations, and runtimes
- [`results/source-weight-verification.json`](results/source-weight-verification.json) — checkpoint/code/voice identity
- [`results/onnx-export-provenance.json`](results/onnx-export-provenance.json) — exact graph/operator/tool provenance
- [`results/host-onnx-fidelity-checkpoint.json`](results/host-onnx-fidelity-checkpoint.json) — controlled export, immutable numerical failure, and separate acoustic screen
- [`results/executorch-export-checkpoint.json`](results/executorch-export-checkpoint.json) — bounded full-model blockers
- [`results/phone-onnx-bootstrap-checkpoint.json`](results/phone-onnx-bootstrap-checkpoint.json) — exact phone bootstrap failures and cleanup
- [`tools/export_onnx_fp.py`](tools/export_onnx_fp.py) — controlled fixed-contract FP32 export
- [`tools/verify_source_weights.py`](tools/verify_source_weights.py) — source tensor and voice proof
- [`tools/analyze_outputs.py`](tools/analyze_outputs.py) — frozen waveform/acoustic diagnostics
- [`android/`](android/) and [`device/run-phone-onnx-cpu.sh`](device/run-phone-onnx-cpu.sh) — deterministic CPU harness and safe runner

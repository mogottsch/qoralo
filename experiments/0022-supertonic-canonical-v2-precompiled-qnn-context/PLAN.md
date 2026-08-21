# Experiment 0022 plan

This is the durable implementation plan for comparing source-ONNX QNN startup with precompiled-context startup. The repository, not chat or ignored `.local` state, is authoritative.

## Current state

No implementation, context generation, phone staging, or benchmark output exists. Only the approved scope, immutable lineage, protocol, copied canonical transcript, preflight state, and contract tests have been created. The experiment path alone is owned by Sean. Other sessions own their own experiments and dashboard paths.

The approved comparison is source ONNX QNN compilation (arm A) versus external precompiled QNN EPContext reload (arm B) for the exact stable-Softplus all-HTP Supertonic graph set. Each arm must be matched in every respect except source compilation versus context reload. At least three independent cold processes per arm are required.

## Important discovered compatibility gate

The historical 0011 runner hard-codes:

- processed text length 239;
- latent length 238;
- 729,746 output samples;
- `<en>` plus 230-byte legacy text plus `</en>` = 239 characters.

Canonical v2 is exactly 226 bytes, so `<en>` plus canonical v2 plus `</en>` = 235 characters. Yet the approved scope also says to preserve the same transformed graph hashes. Re-specializing shapes would change graph hashes and is therefore not an allowed silent choice.

Before implementing or producing output, prove whether four masked padding positions can preserve the exact T239/L238 graphs while retaining canonical-v2 semantic input. The proof must freeze the pad ID, mask values, positions, effective model inputs, and comparison to a dynamic/eager canonical-v2 oracle. If this cannot be proven, stop and tell Pi that exact canonical-v2 input and exact frozen graph identity are jointly incompatible. Never use the legacy transcript as a shortcut.

## Resume checklist

1. Reserve only `experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/` during coordinated work.
2. Run the contract tests and verify the working tree does not contain uncommitted 0022 changes.
3. Reconstruct each ignored dependency and verify its SHA-256 against `protocol/experiment-contract.json`.
4. Check current measured RAM use before any QAIRT/ORT compilation. Do not overlap near-machine-size compiler jobs without adequate measured headroom.
5. Resolve the T235-to-T239 padding/mask gate and commit the proof before generating any QNN context or WAV.
6. Inspect pinned ORT 1.27.1 QNN EPContext behavior, especially non-embedded external context generation and loading. Freeze exact provider/session options.
7. Build one deterministic runner supporting both arms and emitting per-session readiness, total ready time, process time, six generation records, PSS/VmHWM, provider/profile paths, hashes, and cleanup status.
8. Pass host source-assignment, context-generation, and independent reload gates before using the phone.
9. Use Windows adb only with `ADB_LIBUSB=1`, `artifacts/locks/phone.lock`, exact identity/boot gates, verified staging, and verified cleanup/uninstall. Coordinate phone order with peers.
10. Run physical proof separately if profiling perturbs benchmark timing. Context reload must itself be proven with source graphs unavailable.
11. Commit only 0022 evidence, then hand exact commit/metrics/provenance/WAV/hash/missing reasons to Marius and FYI Pi.

## Exact validation command

```bash
python3 -m unittest discover \
  -s experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/tests \
  -p 'test_*.py' -v \
&& git diff --check
```

## Exact next technical command after validation

Use this read-only inspection first; do not generate contexts yet:

```bash
rg -n 'ep\.context_(enable|embed_mode|file_path)|EPContext' \
  experiments/0010-supertonic-qnn-htp-feasibility/.local/onnxruntime-v1.27.1-source/onnxruntime/test/providers/qnn/qnn_ep_context_test.cc \
  experiments/0010-supertonic-qnn-htp-feasibility/.local/onnxruntime-v1.27.1-source/onnxruntime/test/onnx/main.cc
```

If that ignored ORT source is absent on the new device, reconstruct the pinned ORT 1.27.1 source first, record its revision/archive hash in 0022, and then run the equivalent command. Do not infer API semantics from memory.

## Known portable hashes

- Canonical transcript: `424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67`.
- Duration graph: `8a1875ef0f6960ca16fc06814509b1c3258e8f50b04a5d590d3ab6db8c775016`.
- Text graph: `769fd1d257674e8624bdea941f7a903d9460051f9845b604cd2c2980f281a8c3`.
- Stable-Softplus vector graph: `f2318c54726a034dcc89aa9818a91f1c3db0e3067b9932c7c2dae65957897c7b` (source specialized vector `723316adfcff378c8ac72ee9db34cadf3b890e4167fa9a76f07398e0d4ff5b92`).
- Vocoder graph: `35b90eeae4a01d06f82dccc903a63d23c95eb2d9095ffa0d62f2cf151817c7c7`.
- Android ORT 1.27.1 library: `40bc591798287525f365e8ded4bbc40e0c4e9440737e876026ec09ba359ac041`.
- QAIRT baseline: `2.49.0.260730`; all QNN library hashes are in the machine contract.

## Claim boundaries

- “All HTP” covers the four neural sessions only; frontend, orchestration, trimming, and WAV encoding remain CPU work.
- Fallback must be disabled. A successful session/load alone is not provider or physical proof.
- Host source assignment and EPContext reload are gates, not physical-phone HTP evidence.
- QNN’s internal arithmetic precision is not established; “official FP32 source” must not become “FP32 on HTP.”
- Report context generation as offline cost and arm-B cold readiness separately.
- Do not transfer 0011 or 0021 listening acceptance. Every new byte-different WAV is `not_reviewed` until Moritz reviews its exact SHA-256.
- Do not edit `docs/android-benchmarks/`; Marius owns dashboard ingestion.

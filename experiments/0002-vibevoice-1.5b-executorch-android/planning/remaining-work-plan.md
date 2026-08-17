# Remaining ExecuTorch work — VibeVoice 1.5B Android spike

## Purpose

Convert the unfinished portion of the existing 39-step ExecuTorch feasibility spike into a durable Pi Messenger Crew task graph. This document covers only unfinished steps. It must not recreate completed work or broaden the repository into product development.

This is a historical work plan. The detailed experiment record is the experiment [`README`](../README.md).

## Fixed scope

Determine whether `microsoft/VibeVoice-1.5B` can run locally on a Samsung Galaxy S23 Ultra using ExecuTorch/XNNPACK, with reproducible host and Android evidence. Finish the component-first path through end-to-end generation, locked-reference comparison, full-build measurement, memory optimization, and execution optimization.

Do not add Podleaf work, product UI, source ingestion, Gemma integration, application architecture, unrelated model research, or other Android runtimes to this Crew plan. LiteRT, ONNX Runtime Mobile, Qualcomm QNN, and VibeVoice Realtime 0.5B remain later experiments after this 39-step ExecuTorch sequence.

## Locked inputs

- VibeVoice source revision: `6dd49cb7200c0367205a5f1e650244259e9e423d`
- VibeVoice 1.5B model revision: `c00898d257e6b46004e3e2866a47534085fb685a`
- Reference WAV SHA-256: `fb0152dc686836fe23d9c39c3b24c1de82398f51b9747f5e36ad1db819ce0358`
- Reference duration: 13.066667 seconds, 24 kHz mono PCM S16LE
- Reference generation: CPU FP32, SDPA, seed 42, CFG 1.3
- Primary runtime: ExecuTorch 1.2 with XNNPACK
- Device: Galaxy S23 Ultra SM-S918B, Snapdragon 8 Gen 2, Android 16/API 36, arm64-v8a

## Completed work — do not recreate

Steps 1–16, 20–21, and 24–25 are complete and committed. In particular:

- Lane A steps 1–10: FP32 and FP16 acoustic decoder, explicit 34-tensor streaming cache, host validation, Android validation, and publication.
- Lane B steps 11–16: deterministic diffusion fixture, one-step export, host validation, Android validation, and native ten-step DPM-Solver loop.
- Lane C steps 20–21 and 24–25: deterministic real Qwen2 prefill/decode fixtures and separate FP32 XNNPACK exports with 56 explicit fixed-capacity KV tensors.

Real Qwen2 host execution is finite but not accepted at the preserved `atol=1e-5, rtol=1e-4` threshold. Maximum error is `4.730224609375e-4`; prefill has 12,844 mismatches and chained decode has 11,315. The approximately 6.18 GB FP32 PTEs are correctness artifacts, not deployment candidates. Diagnose this rather than silently widening tolerance.

## Required task mapping

Create one traceable Crew task for each unfinished original step. Prefix each task title with its original step number. Do not merge away the original step numbers.

### Lane B — connectors and semantic path

1. **Step 17 — Capture and export connectors.** Complete paired real generative connector fixture capture and ExecuTorch/XNNPACK export based on `export/speech_connectors.py`. Record deterministic metadata, tensor ABI, hashes, numerical comparisons, commands, and conclusions. Large tensors/PTEs stay ignored.
2. **Step 18 — Export the semantic audio encoder.** Define a stable tensor ABI, capture a deterministic real fixture, export through ExecuTorch/XNNPACK, and validate on the host before Android.
3. **Step 19 — Run the semantic path on Android.** Integrate the accepted connector and semantic encoder artifacts into the debug Android probe, run them on the Galaxy S23 Ultra, and record correctness, determinism, latency, and memory.

### Lane C — Qwen2, quantization, and conditioning

4. **Step 22 — Diagnose and validate Qwen2 prefill on the laptop.** Localize the FP32 XNNPACK numerical drift using reproducible graph/segment diagnostics. Fix the export or establish a narrowly justified component-specific acceptance criterion while preserving the original strict metrics. Do not proceed merely because outputs are finite.
5. **Step 23 — Run Qwen2 prefill on Android.** Proceed only after step 22 is accepted. Account for the impractical 6.18 GB FP32 artifact and avoid a predictable phone low-memory/storage failure without first reducing or partitioning it. Record any principled packaging change.
6. **Step 26 — Run single-token Qwen2 decode on Android.** Use actual prefill-produced caches, preserve the 56-tensor ordering, and validate chained decode correctness, determinism, latency, and memory.
7. **Step 27 — Quantize the Qwen2 backbone to INT8.** Quantize one component at a time, validate prefill and chained decode on host and Android, and preserve FP32 reference metrics.
8. **Step 28 — Quantize the Qwen2 backbone to INT4.** Attempt the likely practical mobile target only after INT8 evidence. Record method, package size, memory, latency, tensor error, and any quality risk.
9. **Step 29 — Implement token selection.** Implement deterministic native token selection compatible with the exported prefill/decode ABI and locked generation settings. Validate against captured PyTorch behavior.
10. **Step 30 — Implement speaker conditioning.** Capture the real two-speaker conditioning path, define its native/export ABI, and validate deterministic outputs needed by the generation controller.

### Lane D — end-to-end generation and optimization

11. **Step 31 — Build the native generation controller.** Orchestrate Qwen2 prefill/decode, explicit KV caches, token selection, speaker conditioning, connectors, semantic/audio path, diffusion scheduling, and streaming decoder in Kotlin/C++ without Python runtime state.
12. **Step 32 — Generate one speech chunk from text.** Produce the smallest real text-to-audio chunk on Android and compare intermediate tensors against the locked host path.
13. **Step 33 — Generate three to five seconds.** Extend the controller to a stable multi-chunk run, recording continuity, correctness, latency, and memory.
14. **Step 34 — Add the second speaker.** Exercise real two-speaker conditioning and switching without major corruption or identity collapse.
15. **Step 35 — Run the locked reference transcript.** Generate the fixed two-speaker reference transcript on the phone with locked settings.
16. **Step 36 — Compare Android output with the reference.** Record objective metadata plus omissions, repetitions, corruption, speaker consistency, and listening notes. Do not require byte-identical audio when precision/quantization differs, but retain hashes and intermediate tensor evidence.
17. **Step 37 — Measure the complete XNNPACK build.** Record package/model size, load time, time to first audio, generated duration, wall time, real-time factor, peak RSS/PSS/VmHWM, determinism, output hash, and device/runtime versions.
18. **Step 38 — Optimize memory.** Reduce peak memory and package duplication without weakening accepted correctness. Re-measure the complete build.
19. **Step 39 — Optimize execution.** Improve execution time after memory work, re-run the locked reference, publish final reproducible measurements, update `docs/progress.json`, and document the ExecuTorch feasibility conclusion.

## Dependencies

Preserve these logical dependencies:

- Step 19 depends on accepted steps 17 and 18.
- Step 23 depends on accepted step 22.
- Step 26 depends on accepted step 22 and the already completed step 25; it must use the accepted prefill/cache path.
- Step 27 depends on accepted host and Android Qwen2 prefill/decode behavior from steps 22, 23, and 26.
- Step 28 depends on step 27.
- Step 29 depends on accepted steps 22 and 26.
- Step 31 depends on steps 19, 26, 29, and 30 plus the already completed decoder/diffusion work.
- Steps 32–35 are sequential.
- Steps 36 and 37 depend on step 35 and may be separate tasks.
- Step 38 depends on step 37.
- Step 39 depends on steps 37 and 38.

Add orchestration-only dependencies where necessary to serialize the scarce resources below. Correctness and resource safety are more important than maximum parallelism.

## Serialized resources

- **Phone capacity: one.** Never run two Android/device tasks concurrently. Only one worker may use ADB or deploy an APK at a time.
- **Heavy-RAM capacity: one.** Never run concurrent full-model capture/export/quantization jobs on the 32 GiB laptop. Prior full Qwen2 export peaked near 19 GiB RSS; deterministic reference generation peaked near 12.42 GiB.
- **Integration writer: one.** Serialize edits to `docs/progress.json`, shared experiment README sections, dashboard publication, Git integration, and conflict resolution.
- Workers must reserve the files they edit. Large-artifact directories and resource-lock paths are coordination mechanisms, not evidence to commit.

If the phone requires unlocking, authorization, or other physical input, block the affected task with a precise reason and notify the user immediately; do not spin or repeatedly retry.

## Evidence and repository rules

- Keep weights, generated audio, `.pte`, APKs, raw tensors, converted models, logs, traces, and transient telemetry ignored.
- Commit reproducible scripts, stable fixture manifests, hashes, structured results, measurements, acceptance thresholds, and conclusions.
- Review staged paths before committing. Do not use unrelated files from another task in a commit.
- Preserve failed attempts when they inform feasibility; distinguish execution success from numerical acceptance.
- Host correctness precedes Android execution. Android correctness precedes quantization-dependent integration.
- Never silently loosen FP32 thresholds. Any component-specific tolerance must include strict metrics, localization evidence, and a written justification.
- Update `docs/progress.json` only after validated milestones. The dashboard is rendered from that canonical file.
- Each completed task must report commit SHA(s), exact tests/commands, evidence paths, and a concise conclusion.

## Stop conditions

Autonomous work may continue through step 39 unless one of these requires the user:

- privileged or system-wide changes;
- proprietary license acceptance;
- personal-device data access;
- paid services;
- destructive actions outside project-created artifacts;
- a major architecture pivot;
- substantial custom native-kernel work.

Ordinary export failures, numerical mismatches, out-of-memory results, worker failures, flaky tooling, and recoverable Android errors are not automatic stop conditions. Diagnose them, preserve evidence, and retry or re-plan within the documented architecture.

## Planning instructions

- Generate the plan only; do not start workers automatically.
- Keep the 19 unfinished original steps traceable as 19 tasks unless a separate explicit validation/integration task is essential. Do not create tasks for completed steps.
- Use strict dependencies and expose safe parallelism only where files and scarce resources do not overlap.
- Give each task concrete acceptance criteria, evidence files, relevant existing source paths, and the resource it owns.
- Treat `docs/progress.json` as canonical status and this document as the remaining-work specification.

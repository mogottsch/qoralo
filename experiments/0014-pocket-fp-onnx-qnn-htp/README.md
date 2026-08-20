# 0014 — Pocket ONNX through QNN HTP

This experiment began as a fail-closed screen for experiment 0012's exact Pocket FP ONNX graphs, continued through technically complete but unusable Bria-conditioned QNN paths, and was reopened on 2026-08-20 to find the quality failure before doing more acceleration work.

## Final result

**Root cause found and one bounded fixed-voice route recovered.**

The public checkpoint is `kyutai/pocket-tts-without-voice-cloning`. All 42 Mimi encoder and encoder-transformer tensors—9,224,736 elements—are zero. Experiment 0012's local config assigned that file to `weights_path`, bypassing the official fallback detection that would set `has_voice_cloning=false`. Its Bria audio path therefore ran an input-invariant zero encoder instead of failing closed.

That changes the interpretation of the old evidence:

- 0012 accidentally exercised an invalid audio-cloning contract.
- Source/ONNX numerical equivalence validated the broken contract, not speech quality.
- The 2026-08-19 QNN proofs remain valid technical execution evidence, but their Bria-conditioned audio was invalid at the first voice boundary.
- Experiment 0012 and all original 0014 records remain unchanged as history.

The recovered contract uses the official pinned precomputed **Alba state** (SHA-256 `e4a323e8…7b1c`) as a fixed voice. It is not voice cloning.

## Recovered observed path

Moritz independently accepted the exact official-source Alba samples, controlled FP ONNX host samples, QNN-compatible fixed-cache host samples, Android CPU derivative sample, and physical fallback-disabled QNN/HTP sample as good.

The accepted physical QNN sample:

- SHA-256 `2c3901ec39a53596759c1d95381a1d67e4f9ca8886cdf39ac03721863c63eb56`
- fixed Alba state, frozen text, seed 0, temperature 0.3
- EOS step 53; 56 frames; 4.48 seconds at 24 kHz mono
- CPU fallback disabled
- 122 `QNNExecutionProvider` events and 0 CPU provider events
- exactly 122 RPC, accelerator, cycle, and HVX records
- profiled proof: setup 58.198 s, generation 2.352 s, RTF 0.525, VmHWM 2,447,980 kB
- separate unprofiled first complete post-setup generation: 0.740 s, RTF 0.165, VmHWM 2,241,184 kB
- the unprofiled WAV was byte-identical to the accepted profiled WAV

The unprofiled number is one first complete generation after session setup—not a warm median or distribution. The profiled number remains the instrumentation-bearing physical proof.

## Why the static derivative matters

The quality-valid original ONNX route was accepted on x86 host CPU but its original dynamic FlowLM graph diverged on Android CPU before the first sampled latent, reached the 134-frame cap without EOS, and was separately rejected by Moritz. Direct Alba initialization of the fixed-cache derivative removed that platform-sensitive dynamic path:

- host derivative: accepted
- Android CPU derivative: EOS 53, 56 frames, accepted
- fallback-disabled QNN/HTP derivative: EOS 53, 56 frames, independently accepted

The 256-slot cache is bounded to 126 fixed-voice positions + 26 text positions + at most 100 generated positions, so the tested contract does not roll away voice context.

## Claim boundary

This is quality and physical-execution evidence for one exact observed **fixed-Alba** path. It does not establish:

- audio voice cloning with the no-voice-cloning checkpoint
- other voices, texts, seeds, shapes, temperatures, or checkpoints
- FP32 HTP arithmetic; QNN executes these FP-source graphs as FP16
- a warm performance distribution or first-audio latency
- production readiness or resolution of the distinct 0008 archive's license discrepancy

CPU supplies fixed token IDs, the prepacked official Alba state, deterministic noise, recurrent tensor ownership, EOS scanning, orchestration, concatenation, and WAV encoding. Every neural call actually invoked in the observed synthesis path—text conditioner, text prefill, BOS/latent AR, flow, and decoder-12/6/1—ran through QNN HTP.

## Reproduction

- [`tools/audit_zero_voice_encoder.py`](tools/audit_zero_voice_encoder.py) — exact zero-tensor and invariant-output audit
- [`tools/generate_source_oracle.py`](tools/generate_source_oracle.py) — official source Bria/Alba controls
- [`tools/compare_alba_source_onnx.py`](tools/compare_alba_source_onnx.py) — tokenizer, state, recurrent, and full-decode comparison
- [`tools/generate_alba_onnx_baseline.py`](tools/generate_alba_onnx_baseline.py) — controlled ONNX fixed-Alba host samples
- [`tools/generate_alba_static_qnn_candidate.py`](tools/generate_alba_static_qnn_candidate.py) — QNN-compatible host samples
- [`tools/prepare_alba_assets.py`](tools/prepare_alba_assets.py) and [`tools/prepare_alba_android_stage.sh`](tools/prepare_alba_android_stage.sh) — deterministic fixed-state/noise and Android stages
- [`device/run_alba_cpu_validation.sh`](device/run_alba_cpu_validation.sh) — rejected original dynamic Android control
- [`device/run_alba_static_phone.sh`](device/run_alba_static_phone.sh) — locked Android CPU/QNN proof protocol
- [`tools/analyze_alba_phone.py`](tools/analyze_alba_phone.py) — provider, physical, WAV, and system evidence aggregation
- [`tools/fetch_0008_pocket_archive.sh`](tools/fetch_0008_pocket_archive.sh) and [`tools/audit_0008_pocket_archive.py`](tools/audit_0008_pocket_archive.py) — pinned distinct-archive reconciliation

## Evidence

- [`results/zero-voice-encoder-root-cause.json`](results/zero-voice-encoder-root-cause.json)
- [`results/alba-quality-recovery.json`](results/alba-quality-recovery.json)
- [`results/quality-recovery-listening.json`](results/quality-recovery-listening.json)
- [`results/android-alba-original-cpu.json`](results/android-alba-original-cpu.json)
- [`quality-recovery-protocol.json`](quality-recovery-protocol.json)
- [`RESULTS.md`](RESULTS.md)

Historical evidence remains:

- [`results/full-qnn-continuation.json`](results/full-qnn-continuation.json)
- [`results/blind-listening.json`](results/blind-listening.json)
- [`results/temperature-drift.json`](results/temperature-drift.json)
- [`results/host-gate.json`](results/host-gate.json)

**Recommendation:** the observed fixed-Alba route is recovered and is a credible bounded prototype. Do not generalize it to voice cloning or production deployment without broader text evaluation, fixed-voice product fit, licensing review, and a real performance distribution.

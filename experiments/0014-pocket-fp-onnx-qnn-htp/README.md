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

## Canonical-v2 dashboard benchmark

A dated, distinct canonical route now uses the repository-wide 226-byte transcript (SHA-256 `424b3807…b67`). It tokenizes to 64 IDs, so the accepted text26/cache256 route could not be relabeled or reused. New text64/cache512 graphs preserve all `126 voice + 64 text + 292 maximum generated = 482` positions within 512 slots.

Host original-dynamic and cache512 outputs both emitted 163 frames with EOS at step 160, lasted 13.04 seconds, and were independently accepted by Moritz as “good.” Every new cache512 graph also passed fallback-disabled host QNN assignment as one partition.

| Canonical-v2 measurement | Android CPU | QNN/HTP |
|---|---:|---:|
| Setup | 2.597 s | 62.233 s |
| First generation | 5.377 s / RTF 0.412 | 2.491 s / RTF 0.191 |
| Five-warm median | **5.402 s / RTF 0.414** | **2.369 s / RTF 0.182** |
| Warm RTF range | 0.407–0.419 | 0.179–0.182 |
| Process VmHWM | 1,412,276 kB | 2,405,820 kB |
| Representative WAV | `2e9021b9…34bd` | `601cd622…58e5` |
| Moritz verdict | **Accepted: “good”** | **Accepted: “good”** |

All six outputs within each route were byte-identical and had the same 163-frame/13.04-second stop behavior. The QNN result has a separate instrumentation-bearing proof: fallback disabled, 344 QNN / 0 CPU provider events, with exactly 344 matching RPC, accelerator, cycle, and HVX records. Profiled generation was 7.481 seconds (RTF 0.574) and is not used as the warm performance number.

Machine-readable canonical evidence: [`results/canonical-v2-benchmark.json`](results/canonical-v2-benchmark.json) and [`canonical-benchmark-protocol.json`](canonical-benchmark-protocol.json).

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
- [`tools/prepare_canonical_benchmark_assets.py`](tools/prepare_canonical_benchmark_assets.py), [`tools/build_canonical_graphs.sh`](tools/build_canonical_graphs.sh), and [`tools/generate_canonical_host_gate.py`](tools/generate_canonical_host_gate.py) — canonical-v2 fixtures, text64/cache512 graphs, and host gate
- [`tools/run_canonical_host_qnn_gate.sh`](tools/run_canonical_host_qnn_gate.sh), [`tools/prepare_canonical_benchmark_stage.sh`](tools/prepare_canonical_benchmark_stage.sh), and [`device/run_canonical_benchmark.sh`](device/run_canonical_benchmark.sh) — fail-closed host assignment plus persistent phone benchmark/proof
- [`tools/analyze_canonical_benchmark.py`](tools/analyze_canonical_benchmark.py) and [`tools/analyze_canonical_physical_proof.py`](tools/analyze_canonical_physical_proof.py) — first/warm and provider/physical aggregation

## Evidence

- [`results/canonical-v2-benchmark.json`](results/canonical-v2-benchmark.json)
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

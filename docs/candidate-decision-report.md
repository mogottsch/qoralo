# Candidate decision report

**Status: awaiting explicit next-step approval.** The user reviewed the published audio and clearly preferred Candidate C / Kokoro 82M. Candidate A / VibeVoice Realtime and Candidate B / Pocket TTS were hard to distinguish and are effectively tied. This is subjective listening evidence, not an objective metric or Android-feasibility claim. No conversion or follow-up work is authorized by this report.

## Evidence kept separate

### Host listening and reproducibility evidence

| Candidate | Protocol-v2 output | Host generation | First audible | Host RTF | Peak process-tree RSS | Listening rating |
|---|---:|---:|---:|---:|---:|---|
| VibeVoice Realtime 0.5B | 20.133 s raw; exact 15 s normalized | 8.889 s | 0.484 s | 0.441 | 3.532 GB | Effectively tied for second |
| Pocket TTS 100M | 13.840 s raw only | 4.094 s | 0.184 s | 0.296 | 1.145 GB | Effectively tied for second |
| Kokoro 82M | 17.475 s raw; exact 15 s normalized | 6.692 s | 7.042 s | 0.383 | 1.713 GB | **Clearly preferred** |

The preference above is the user's explicit review of these samples. These are host measurements, not Android measurements. Pocket remained short after the one permitted shared punctuation revision and has no documented speed control. Its raw sample is playable, but no silence, loop, time stretch, or normalized 15-second sample was fabricated.

### Android measurements

The VibeVoice 1.5B four-call PTE was **not run on Android**. Its deterministic host validation failed the frozen call-0/call-1 energy gates and one call-3 decoder-cache tolerance. The protocol therefore prohibited deployment and ADB; Android timing, memory, hashes, chunk output, device versions, and determinism are unavailable rather than estimated.

Realtime 0.5B, Pocket, and Kokoro have no Android measurements in this campaign.

### Estimates, not measurements

Realtime 0.5B has 881,492,068 statically classified active parameters. Learned-weight arithmetic is 1,762,984,136 bytes at FP16, 881,492,068 bytes at ideal INT8, and an estimated 453,968,416–493,635,559 bytes for mixed/groupwise INT4. These figures do not prove runtime support, accuracy, memory use, operator coverage, latency, thermals, or Android feasibility. Official streaming state is bounded but dynamic rather than an export-ready fixed-shape ABI.

If listening quality is approved, the recommendation is component-first fixtures. A narrow Qualcomm QNN/HTP probe has first priority, with 8a8w, 16a8w, and 16a4w evidence for partitioning, CPU fallback, transfers, numerical error, and latency. Any proprietary SDK, account, EULA, or redistributed library requires separate approval. LiteRT/LiteRT-LM and ONNX Runtime Mobile remain later comparisons, not work already started.

## Historical 39/39 result

The prior 39/39 ExecuTorch/XNNPACK result remains immutable: the tested VibeVoice 1.5B deployment is rejected for capacity, speed, size, and its historical fixed-rubric audio result. The [locked-prefix supplement](../experiments/0002-vibevoice-1.5b-executorch-android/results/locked-reference-prefix-comparison.json) is clarification only: the old two-chunk Android output matches the equally short, near-silent host prefix within one signed-16-bit PCM unit. That does not satisfy duration or quality acceptance and does not revise the historical conclusion.

The newer four-call host artifact reaches a correctly voiced chunk 3 at about -21.71 dBFS and within one S16 PCM unit of its reference, but that host context is not Android evidence and cannot override the artifact's failed numerical gate.

## Choose one of the five permitted decisions

1. **Proceed with Realtime 0.5B on Android.** First approve its listening quality; then capture component fixtures. Separately approve proprietary Qualcomm terms if that runtime is selected.
2. **Proceed with Kokoro turn-by-turn mobile composition.** Kokoro is the listening-preferred candidate. Pocket remains available as a tied-second comparison but is raw-only under this exact-15-second protocol.
3. **Continue VibeVoice 1.5B recovery.** Require a newly reviewed host-accepted artifact without silently widening frozen thresholds before another Android deployment.
4. **Run a narrow QNN accelerator bake-off.** Approve listening quality and any proprietary terms, then probe components and the three named quantization schemes rather than converting a full model.
5. **Reject a candidate based on listening quality.** Record the user's judgment; do not infer it from host speed or package estimates.

## Evidence index

The machine-readable [decision report](candidate-decision-report.json) pins source-file hashes and the five decision gates. Primary sources:

- [protocol-v2 listening manifest](../experiments/0007-mobile-podcast-preview-bakeoff/publication/bakeoff-manifest.json)
- [explicit user listening review](../experiments/0007-mobile-podcast-preview-bakeoff/results/user-listening-review.json)
- [Realtime feasibility inventory](../experiments/0006-vibevoice-realtime-0.5b-android/feasibility-inventory.json)
- [four-call Android gate result](../experiments/0002-vibevoice-1.5b-executorch-android/results/four-call-android.json)
- [historical fixed-rubric comparison](../experiments/0002-vibevoice-1.5b-executorch-android/results/locked-reference-comparison.json)
- [prefix clarification supplement](../experiments/0002-vibevoice-1.5b-executorch-android/results/locked-reference-prefix-comparison.json)

**Stop here for explicit user approval.**

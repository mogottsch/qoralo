---
experiment: 0024-pocket-tts-qnn-precompiled-context-startup
status: completed
summary: For the documented Pocket reconstruction derivative, external contexts cut median eight-session phone setup from 27.0767 seconds to 1.01122 seconds; both arms ran on HTP and produced distinct, structurally valid WAVs that remain not reviewed.
registry: 0024-pocket-reconstruction-source-onnx-htp, 0024-pocket-reconstruction-external-context-htp
---

# Experiment 0024 — Pocket TTS QNN precompiled-context startup

## Experiment description

Experiment 0024 compared source-ONNX QNN compilation with external EPContext reload for a fixed-Alba, text64, cache512 Pocket TTS route. Each arm created eight sessions: text conditioning, text prefill, BOS autoregression, latent autoregression, flow, and Mimi decoder variants for 12, 6, and 1 frame. Context generation was an offline cost and was excluded from phone reload setup.

This is a new deterministic reconstruction derivative, not the exact experiment-0014 graph set. Reconstructing from the same pinned public weights, tokenizer, Alba state, code, and exporter reproduced the four controlled ONNX file sizes but not their SHA-256 values. All eight specialized graph hashes consequently differ from 0014. The experiment kept that boundary explicit and required fresh CPU, host QNN, phone execution, physical provider, and audio evidence instead of relabeling the derivative.

The matched phone route used the exact 226-byte canonical-v2 transcript, 64 Pocket tokenizer IDs, one thread, ORT 1.27.1, QAIRT 2.49, CPU fallback disabled, and the authorized Galaxy S23 Ultra. Every benchmark process created sessions once, ran one first and five warm complete generations, and reset tokens, flow cache, decoder state, and deterministic noise before each generation. The [reconstruction record](../../../experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/reconstruction.json) defines the derivative, while the [experiment contract](../../../experiments/0024-pocket-tts-qnn-precompiled-context-startup/protocol/experiment-contract.json) defines the matched comparison.

## Progress

1. **August 22, 2026: reconstruction passed its CPU gates.** The pinned exporter passed its component checks, and the derivative completed the canonical transcript on ORT CPU at EOS step 160 with 163 latent frames and 312,960 samples. The resulting host WAV was structurally valid but started `not_reviewed`.
2. **August 22, 2026: eight external contexts passed host reload.** Each component generated a non-embedded context and then reloaded in a separate source-absent container. Generation and reload recorded eight QNN events and zero CPU events, with matching output hashes per component. These were functional host smokes, not a physical-phone timing distribution.
3. **August 22–23, 2026: Android packages were prepared.** The source and context stages shared the same runner and runtime. The context package contained eight small descriptors and eight external binaries with no source graph. A first approved attempt stopped before ADB because the historical Windows transport was absent; the committed contract then selected the pinned native Linux ADB path.
4. **August 23, 2026: the first phone window was interrupted.** Three complete source processes and one complete context process passed. During context run 2, an external device disconnect made ADB return 255 before any result was pulled. The run was excluded. A former two-state cleanup check had incorrectly treated transport failure as absence, so the pending root remained.
5. **August 25, 2026: cleanup was closed and the campaign resumed.** After reconnect, the exact pending root was removed and verified absent with a tri-state check under the phone lock. Two new context processes completed, followed by separate profiled proof processes for both arms.

The [host context result](../../../experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/host-context-smoke.json) preserves the functional reload evidence. The interrupted run remains in the [phone checkpoint](../../../experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/phone-campaign-checkpoint/checkpoint.json), and the [cleanup-resume record](../../../experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/phone-campaign/cleanup-resume/cleanup-resume.json) closes it before the final results. This failure history matters because the six measured benchmark processes span two phone windows rather than one laboratory-controlled sequence.

## Results

External contexts reduced median eight-session phone setup by **26.06548 seconds**, from **27.0767 seconds** to **1.01122 seconds**. That is a **96.26535%** reduction and a **26.7763×** source/context ratio for the exact 0024 derivative. There was no minimum speedup gate.

| Phone measurement | Source ONNX | External context |
|---|---:|---:|
| Three setup runs | 27.0767, 23.8668, 28.6125 s | 0.729463, 1.26412, 1.01122 s |
| Median setup | 27.0767 s | 1.01122 s |
| Median first RTF | 0.172432 | 0.167330 |
| Pooled 15-warm median RTF | 0.168605 | 0.164032 |
| Warm RTF range | 0.164660–0.177048 | 0.163039–0.165763 |
| Maximum process VmHWM | 2,568,248 kB | 201,616 kB |

Every completed benchmark generation reached reference EOS step 160, emitted 163 frames and 312,960 samples, and produced 13.04 seconds of finite, non-silent, unclipped 24 kHz mono PCM16 audio. The source arm was internally deterministic at SHA-256 `028f8a1e…4241`; the context arm was internally deterministic at `7c3fc41d…6d81`.

The two arm outputs are not interchangeable. They are byte-distinct, with correlation **0.453032** and source-over-difference SNR **−0.356050 dB**. Those values are descriptive numerical evidence, not a listening verdict. Both retained phone WAVs remain **`not_reviewed`**. Neither inherits experiment 0014's verdict because both exact hashes differ.

| Evidence class | What 0024 established |
|---|---|
| Technical execution | Three fresh benchmark processes per arm completed the canonical-v2 route with full per-generation state reset. |
| Physical provider proof | Separate source and context proof processes each recorded 344 QNN and zero CPU events, with matching RPC, accelerator-time, accelerator-cycle, and HVX records. They were excluded from benchmark timing. |
| Structural audio | Both exact WAVs are complete and structurally valid at 13.04 seconds, but they differ from each other. |
| Numerical/acoustic comparison | Correlation and SNR describe the difference only; no equivalence or quality gate was applied. |
| Exact-sample listening | Unavailable for both new hashes. Moritz has not committed a verdict for either retained 0024 phone WAV. |

The [machine-readable final result](../../../experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/result.json) contains every run and comparison. Peak PSS was not recorded; the dashboard therefore keeps it unavailable rather than substituting zero. VmHWM is cumulative process-lifecycle high-water, not isolated model or DSP memory. Source runs happened before context runs, the campaign spans two dates, and recorded AP temperatures differed between runs; those order and thermal differences are disclosed confounders. The result is bounded to this reconstructed derivative and does not establish production readiness or an exact 0014 comparison.

# Measured Android CPU thread sweep

**Status:** 9/9 configurations succeeded; 36/36 WAVs and 9/9 telemetry streams independently validated.

These are observed physical-phone measurements, not estimates. **Differences below 5–10% are inconclusive.** Values at or above 10% are directional only because this is a single rotated campaign and the thermal policy changed mid-campaign.

## Observed results

| Seq | Candidate | Threads | Load (s) | Cold RTF | Warm median RTF | Warm callback median (s) | Peak sampled PSS (MiB) | Peak sampled RSS (MiB) | Thermal pre → gate → post |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | pocket | 1 | 0.963 | 0.430 | 0.408 | 0.631 | 651.2 | 713.4 | NONE → NONE → NONE |
| 2 | kokoro | 2 | 1.176 | 1.003 | 1.039 | 5.409 | 887.0 | 949.2 | NONE → NONE → LIGHT |
| 3 | supertonic_3 | 4 | 0.679 | 0.371 | 0.399 | 6.593 | 439.3 | 506.1 | LIGHT → STATUS_1,STATUS_1,STATUS_1,STATUS_1,STATUS_1,STATUS_1,STATUS_1,NONE → NONE |
| 4 | kokoro | 4 | 1.346 | 0.900 | 0.753 | 4.188 | 879.4 | 946.2 | NONE → NONE → LIGHT |
| 5 | supertonic_3 | 1 | 0.605 | 0.389 | 0.401 | 6.634 | 438.5 | 507.3 | LIGHT → STATUS_1,STATUS_1,STATUS_1,STATUS_1,STATUS_1,STATUS_1,STATUS_1,NONE → NONE |
| 6 | pocket | 2 | 0.705 | 0.374 | 0.367 | 0.538 | 651.4 | 720.5 | NONE → NONE → LIGHT |
| 7 | supertonic_3 | 2 | 0.785 | 0.355 | 0.362 | 5.996 | 440.4 | 509.0 | LIGHT → LIGHT → LIGHT |
| 8 | pocket | 4 | 0.843 | 0.462 | 0.511 | 0.876 | 653.2 | 722.6 | LIGHT → LIGHT → LIGHT |
| 9 | kokoro | 1 | 1.211 | 1.421 | 1.424 | 7.578 | 876.0 | 946.5 | LIGHT → LIGHT → LIGHT |

## Thread comparison

### pocket

Observed warm median RTF: 1 thread 0.408, 2 threads 0.367 (-9.9%), 4 threads 0.511 (+25.3%). The lowest observed value was at 2 threads.

Interpretation labels: 2 threads `inconclusive_5_to_below_10_percent`; 4 threads `directional_at_or_above_10_percent`.

### kokoro

Observed warm median RTF: 1 thread 1.424, 2 threads 1.039 (-27.0%), 4 threads 0.753 (-47.1%). The lowest observed value was at 4 threads.

Interpretation labels: 2 threads `directional_at_or_above_10_percent`; 4 threads `directional_at_or_above_10_percent`.

### supertonic_3

Observed warm median RTF: 1 thread 0.401, 2 threads 0.362 (-9.6%), 4 threads 0.399 (-0.6%). The lowest observed value was at 2 threads.

Interpretation labels: 2 threads `inconclusive_5_to_below_10_percent`; 4 threads `inconclusive_below_5_percent`.

## Protocol amendment and interruption

Sequences 1–6 used the registered NONE-only thermal gate and the original 30/60-second passive stabilization. The prior runner was intentionally interrupted while waiting at LIGHT before sequence 7 synthesis. Its orphan pre-state and empty allocated run directory remain retained and hash-addressed.

After Moritz's explicit authorization, sequences 7–9 treated NONE and LIGHT as eligible, waited only at MODERATE or higher, and used no fixed passive sleeps. All three resumed synthesis gates observed LIGHT (`STATUS_1`). No device setting, thermal policy, or CPU setting was changed.

This mid-campaign change is a real comparability limitation, especially for configurations 7–9. It is not normalized away.

## Validation and provenance

- 36/36 retained WAVs: SHA-256 matched, canonical mono PCM16 decoded completely, frame/rate/duration agreed, and audio was non-silent and unclipped.
- 9/9 telemetry JSONL files: non-empty and structurally valid (264 samples total); every parsed Android thermal status is retained per configuration.
- 9/9 host evidence manifests and all files they pin matched SHA-256; warm medians were recomputed.
- 401/401 staged deployment files and all nine descriptors matched their registered hashes before resume.
- Raw ledger: `artifacts/0009/thread-sweep/campaigns/20260813T150053Z-e6053419a29b/ledger.json` (`b21b4c1e25671f2469d455e6b1b6d446b336a98e090e4030b3fdaff0baa52493`).
- Resume verification: `artifacts/0009/thread-sweep/campaigns/20260813T150053Z-e6053419a29b/resume-attempts/20260813T153736Z-5ee916e67492/resume-verification.json` (`df4efdc338773f7b64a55a1eb9d162b53ea7fa33cd2c2813ae4e276b3c5d2b81`).
- No root, system tuning, QNN/QAIRT, proprietary SDK, or text splitting was used. Listening was not performed.

## Limitations

- The eligibility policy changed after sequence 6: sequences 1-6 required NONE; sequences 7-9 accepted NONE or LIGHT and waited only at MODERATE or higher.
- The campaign was intentionally interrupted before sequence 7 synthesis and later resumed after hash/ledger verification; the gap is preserved as provenance.
- This is one balanced, rotated campaign rather than replicated randomized campaigns. Thermal status and order remain possible confounders.
- Pocket used the packaged Bria reference, not the requested Alba voice.
- Listening evaluation was not performed.

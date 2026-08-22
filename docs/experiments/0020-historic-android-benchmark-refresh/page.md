---
experiment: 0020-historic-android-benchmark-refresh
status: completed
summary: The historical Supertonic CPU route was rerun on the authorized phone after two transport and storage blockers; synthesis stayed within the comparison margin, setup slowed, and Moritz accepted the exact retained WAV.
registry: 0020-supertonic-2026-08-20
---

# Experiment 0020 — Historical Android benchmark refresh

## Experiment description

Experiment 0020 audited the Android benchmark registry and created a safe place for exact reruns without changing frozen historical results. Its first refresh target was the Supertonic 3 released-INT8 CPU route from experiment 0008. The comparison kept old and new values side by side rather than replacing the 0008 row.

The rerun pinned the original model archive, sherpa-onnx 1.13.5 Android AAR, M1 voice (SID5), CPU provider, one thread, timing boundary, and actual-duration RTF calculation. It also reproduced the historical one-first-plus-three-warm protocol and the exact 230-byte legacy-v1 transcript with SHA-256 `350c8d3d…471f`.

That historical match is also the experiment's main limitation. Canonical v2 was adopted after this rerun and has different bytes, punctuation, and output duration. Experiment 0020 is therefore an old-versus-new check for the frozen legacy route, not a canonical-v2 benchmark. The [refresh policy](../../../experiments/0020-historic-android-benchmark-refresh/protocol/refresh-policy.json) defines the 10% RTF comparison margin, evidence handling, and phone-safety rules.

The wider registry audit classified every visible full end-to-end route by transcript provenance and missing evidence. It found no canonical-v2 visible rows at that checkpoint: 17 used legacy v1 and nine used other noncanonical text. See the [transcript provenance audit](../../../experiments/0020-historic-android-benchmark-refresh/results/transcript-provenance-audit.json) and [normalization queue](../../../experiments/0020-historic-android-benchmark-refresh/results/v2-normalization-queue.json).

## Progress

1. **August 20, 2026: registry and route contract audited.** The experiment recorded missing fields across the visible registry, preserved the original 0008 measurements, and froze the exact Supertonic refresh contract.
2. **Two native-Linux ADB readiness checks found no phone.** Both stopped before staging. A later check through the pinned Windows `adb.exe` and audited shim reached the expected unlocked `SM-S918B`; the earlier zero-device observations remain valid for their timestamps.
3. **The first phone bootstrap exposed an Android 16 ownership problem.** The package could not read shell-owned files under app-external scoped storage, so inference never started and the attempt produced no benchmark values or WAV.
4. **A second staging approach was also rejected.** The final bounded adapter copied hash-verified inputs as the app UID into `getFilesDir()`. It left the frozen 0008 experiment untouched and changed no model, runtime, benchmark, timing, memory, or output behavior.
5. **The adapted route completed and cleaned up.** The run waited for thermal eligibility without tuning the device, completed one first and three warm generations, pulled four hash-matched WAVs, then removed internal files, external output, and the package before releasing the phone lock.
6. **Moritz reviewed the retained median sample.** On August 20, 2026, he marked the exact WAV `1cf003d5…ee6e` “good.” The verdict applies only to the 0020 legacy-v1 refresh sample.

The blocked bootstrap remains visible in [its result record](../../../experiments/0020-historic-android-benchmark-refresh/results/supertonic-bootstrap-attempt.json). The [adapted build provenance](../../../experiments/0020-historic-android-benchmark-refresh/results/supertonic-adapted-build-provenance.json) and [staging and cleanup record](../../../experiments/0020-historic-android-benchmark-refresh/results/supertonic-internal-stage-and-cleanup.json) document the route that finally ran.

## Results

The completed comparison found a different pattern for startup and synthesis. Warm median RTF moved from **0.370303** to **0.393086**, a **6.15%** increase. Cold RTF moved from **0.385468** to **0.415874**, a **7.89%** increase. Both stayed inside the predeclared 10% RTF margin. Setup moved from **0.765108 seconds** to **1.003262 seconds**, a **31.13%** increase, so the result flags setup rather than hiding it inside the synthesis comparison.

| Measurement | Historical 0008 | 0020 refresh | Relative change |
|---|---:|---:|---:|
| Setup | 0.765108 s | 1.003262 s | +31.13% |
| First / cold RTF | 0.385468 | 0.415874 | +7.89% |
| Warm median RTF | 0.370303 | 0.393086 | +6.15% |
| Peak sampled PSS | 463,003,648 bytes | 463,911,936 bytes | +0.20% |
| Process VmHWM | 531,345,408 bytes | 534,081,536 bytes | +0.51% |

All four refreshed outputs were finite, non-silent, unclipped mono PCM16 at 44.1 kHz. Each had 729,746 frames and lasted 16.547528 seconds, matching the historical output duration and protocol. The three warm RTFs were `0.391103`, `0.393086`, and `0.400190`; the retained sample came from the median run.

| Evidence class | What 0020 established |
|---|---|
| Technical execution | The exact historical CPU contract ran on the authorized Galaxy S23 Ultra after the input-ownership adapter. |
| Structural audio | Four complete outputs passed container, format, duration, finite, non-silent, and unclipped checks. |
| Numerical/acoustic comparison | Timing and memory were compared with 0008. No waveform similarity or reference-signal quality metric was claimed. |
| Exact-sample listening | Moritz accepted the retained warm-median WAV (`1cf003d5…ee6e`) as “good” on August 20, 2026. |

The [canonical refresh result](../../../experiments/0020-historic-android-benchmark-refresh/results/supertonic-3-int8-cpu-refresh.json) records the complete old/new comparison. CPU provider evidence comes from the pinned descriptor and route; the historical harness produced no ORT provider profile. It also did not record effective frontend IDs. Most importantly, the run used legacy v1 and only three warm generations. It must not be promoted as a canonical-v2, five-warm benchmark or compared as though its transcript matched experiments 0021 and 0022.

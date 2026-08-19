# Experiment 0009 — Android TTS optimization

This experiment contains the two optimization tracks authorized after the measured experiment 0008 Android baseline.

## Tracks

### Exact Kokoro v1.0 INT8 host quality gate

[`kokoro-int8/`](kokoro-int8/) quantizes only the exact pinned `kokoro-multi-lang-v1_0` source used by experiment 0008. The selected mixed S8S8 QDQ candidate is 46.0% smaller, passed the automated host checks, and passed Moritz's finalized **relative INT8-vs-FP32 degradation** listening gate with four ties and one low-confidence preference for each variant. That ballot found no systematic preference between the paired variants; it did not establish that either route/sample was pleasant, usable, or product-quality accepted. The candidate has not been deployed to Android and has no measured Android speed or memory claim.

Start with:

- [`kokoro-int8/QUALITY_GATE.md`](kokoro-int8/QUALITY_GATE.md)
- [`kokoro-int8/WORKER_HANDOFF.md`](kokoro-int8/WORKER_HANDOFF.md)

### Physical Android CPU thread sweep

[`thread-sweep/`](thread-sweep/) measures the exact experiment 0008 Pocket, Kokoro, and Supertonic 3 deployments at one, two, and four CPU threads on the pinned Galaxy S23 Ultra. All nine configurations completed their technical runs; all 36 retained WAVs passed structural validation and all nine telemetry streams passed schema/integrity validation. No listening review was performed in the thread sweep, so route quality is unknown.

Observed best warm-median RTFs were:

- Pocket: two threads, `0.367`
- Kokoro: four threads, `0.753`
- Supertonic 3: two threads, `0.362`

Differences below 5–10% are inconclusive. The campaign used a user-authorized thermal-policy amendment after sequence six, so values at or above 10% remain directional rather than a replicated tuning conclusion.

Start with:

- [`thread-sweep/results/measured-thread-sweep.md`](thread-sweep/results/measured-thread-sweep.md)
- [`thread-sweep/results/measured-thread-sweep.json`](thread-sweep/results/measured-thread-sweep.json)
- [`thread-sweep/WORKER_HANDOFF.md`](thread-sweep/WORKER_HANDOFF.md)

## Scope boundaries

- No root, system tuning, QNN/QAIRT, proprietary SDK, or text splitting was used.
- Pocket still uses packaged Bria rather than requested Alba.
- Raw generated models, blind-listening media, device WAVs, logs, APKs, and telemetry remain ignored but are hash-addressed by committed manifests and reports.

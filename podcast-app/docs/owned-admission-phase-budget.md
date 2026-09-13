# Saved/source-only admission phase check — 2026-09-13

No device action, cleanup, threshold change or new AUDIO attempt was used for this assessment.

## Recorded boundaries

| Boundary | Available memory | What source shows has already happened |
|---|---:|---|
| Host `health-before-inference` |3,228,548KiB (3152.879MiB)|Exact APK/pack verification and idle closure; app processes absent. Main UI/instrumentation and generation-service startup are not yet paid. Verification may affect reclaimable file cache; that is not an owned-RSS measurement.|
| First in-process guard sample |3,045,628KiB (2974.246MiB)|Main/instrumentation startup, Room/Compose, source copy/revision/plan work, pure native RNG check, generation process/foreground-service startup, job claim and pack/plan verification. Guard starts before `ttsFactory()`: no QNN context construction, serialization buffers, neural graph work or Player yet.|

The global difference is178.633MiB. **It cannot all be attributed to startup.** This run recorded device-wide MemAvailable/temperature, not owned VmRSS/VmHWM/PSS. The later per-segment native RSS metric was never reached. No owned-RSS measurement for this admission stop was found in the retained command/guard receipts.

The source does identify already-paid work within the planning allowances: managed/framework startup is part of the512MiB allowance; the2,160,000-draw RNG helper may overlap about24.7MiB across native temporary, Java float array and byte buffer, already covered by the64MiB explicit-buffer allowance. No claim is made that its Java arrays were collected by the second boundary. Main native bridge/code loading also precedes the guard. The128MiB progressive/player/capture increment is mostly future work at this point because Listen/Player was never entered.

QNN resident provisioning1024MiB, serial constructor/copy allowance256MiB and later waveform/player work remain unpaid. The total2048MiB envelope deliberately contains overlap and uncertainty; it is not a proven allocator upper bound.

## Is the whole-start floor reapplied?

Yes. The host enforces3072MiB before cold app/test startup, and `OwnedAudioGuard.start()` independently enforces the same3072MiB after some budgeted setup. This is conservative but not phase-consistent: it grants no credit even for known startup already performed. It should not be described as a measured lack of room for all remaining allocations. At the second observation, **2974.246−(2048+600)=326.246MiB** remains even if the entire planning envelope and emergency reserve are conservatively charged again.

## One proposed policy—not implemented

1. Keep **3072MiB whole-start admission** at the fresh host boundary, plus current ownership/quiet-audio/temperature checks.
2. At the authenticated **pre-context** boundary, require **2648MiB = the full2048MiB planning envelope +600MiB reserve**. Do not subtract the observed global drop or estimate an RSS credit. Charging the full envelope again despite already-paid setup is intentionally conservative.
3. Keep independent sampling, stale/unknown rejection, **<1280MiB / ≥42°C** proactive stops,600MiB emergency reserve, exact plan/PID-start/lease binding, durable owned failure, guarded native teardown and no retry unchanged.

This is one fixed phase rule derived from the retained budget, not an adaptive ratchet to the most recent reading. It would have admitted the recorded2974.246MiB pre-context sample with326.246MiB above the full re-charged envelope/reserve. It is still only a provisional evaluation policy; opaque QNN/DSP costs and device-wide variation remain risks. Historical3.5GiB/3GiB observations remain unchanged. Any implementation must label both boundaries distinctly, freeze/test them and revalidate affected exact-APK proof before another genuine attempt.

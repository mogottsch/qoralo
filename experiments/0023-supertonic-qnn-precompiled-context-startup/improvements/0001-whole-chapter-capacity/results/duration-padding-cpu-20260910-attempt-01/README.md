# CPU duration pair: official FP32 also predicts about30 seconds

**The two-call CPU discriminator completed.** With the same exact full text/active IDs/style, the unchanged official dynamic FP32 duration model predicts29.8093s **without extra padding** and29.8191s with715 padded tokens. This measured padding effect is about9.77ms, not the roughly60s gap to the unforced~90s prose target.

## Exact results

| Case | Active / total tokens | CPU FP32 duration | Source FP32 multiply/floor frames | Call time |
|---|---|---:|---:|---:|
| Active1333 |1333 /1333|29.809314727783203s|1,314,590|0.079716768s|
| Padded2048 |1333 /2048|29.819082260131836s|1,315,021|0.230579474s|

Padded minus active: **+0.009767532348632812s**; ratio1.0003276671 (~+0.033%). Measured phone WAV:1,314,042frames /44100 =29.79687074829932s. CPU predictions exceed that frame-derived duration by12.443979ms and22.211512ms respectively. The **native predictor scalar is still null/uncaptured**: native FP32 multiplication followed by floor prevents treating the ideal real-arithmetic interval as an exact scalar bound.

Raw scalar output files (each132B `.npy`, one FLOAT32 value; derived results, not learned weights):

- `raw/data/active1333-output-0.npy`: `d04defde22401b67402e44c07be43b987c44b9e9594e11f61eaaf7c3ef23b436`
- `raw/data/padded2048-output-0.npy`: `1d2805e448a7b4e6bd0f7479d8c4776e7abc59d8cd09f158f120ae987b0c2d05`

Both returned arrays and pre-classification receipts were retained before interpretation. `raw/data/result.json` contains exact scalars, input raw-byte hashes, providers, bounds, counters and postchecks. Source/mask/voice/common-input provenance remains in `../duration-padding-cpu-readiness-20260910/input-binding.json`; the actual25,856B NPZ with style data stays protected LOCAL-ONLY.

## What this does and does not establish

- The approximately30s prediction already occurs in the **official FP32 CPU model on the active1333 input**. This pair does not support the added715 padding positions or a QNN-only numerical failure as the major explanation for the duration-target gap on this request.
- Padding is not universally neutral: its9.77ms effect is measured here, and the earlier canonical padding evidence remains unchanged. No additional inputs/cases were run.
- This is a same-model/same-session **CPU ORT1.23.2** contrast. Comparing it with phone ORT1.27.1/QNN is cross-runtime/backend and against frame-derived duration, not a paired captured native scalar. It is not a proof of QNN fidelity for other components or all inputs.
- Approximately90s was a prose-length target, not a measured reference output. These results do not establish why the model predicts30s, a universal learned-duration cap, spoken completeness, or a safe duration override.
- Jere's separate one-pass ASR sees fragments throughout the source but is not a speech-completeness ground truth. No further ASR, full TTS rerender, duration stretching/forcing, chunking or graph change was performed here.

The next question is model/conditioning/coverage behavior, not a reason to enlarge RAM, repeat the whole pipeline blindly or reinstate the old vocoder VTCM diagnosis. Any follow-on model case or change requires fresh scope.

## Execution and preservation

Reviewed request `78fc97c0…417f9031`, readiness `3c682e2`, actual release retained. One CPUExecutionProvider session, constructor fallback disabled, **two calls only** in1333→2048 order. Official dynamic model `c3eb9141…325db`; prior structural evidence ties its unchanged1086 nodes/98 initializers to the phone's T2048 source `394ea3e7…8cbad9`. No model file was changed.

Actual runtime: CPU ORT1.23.2, NumPy1.26.4, Python3.10.13. Affinity0–3, intra4/inter1,4GiB soft/hard RLIMIT_AS. Setup0.050468923s; worker0.614655502s, outer0.857387543s; peak process RSS376,796KiB. Model/input/20 selected runtime postpins passed; no QNN library mappings. No QNN/phone/vocoder/other-model calls, installation or retry.

Worker/group reaped and absent, owned disk scratch empty (`cleanup.json`). Preserve actual common-input NPZ and original models/contexts/WAV/failures/private originals. This release is consumed. Nik's FINAL saved-result audit verified exact request/input/runtime bindings, both raw scalars/frame conversion, postpins/no QNN mappings and cleanup without another runtime/model call: `/home/moritz/.cache/nik-podcast-reviews/duration-padding-cpu-20260910-attempt-01/independent-audit.json`. The CPU comparison gate is complete; no extra cases or phone retry requested. No listening acceptance or push.

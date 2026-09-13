# AS12 control: 16 successful prefill graphs, incomplete logit capture

The single granted `mapping-as12-20260913T104909Z-01` control completed with native/controller **0**, exactly **16 AR128 status-0 completions / zero AR1**, and the exact 1,929 post-query IDs (`3b5c04fe…52b64`). All 28 native observations read soft/hard **RLIMIT_AS = 12,884,901,888 bytes**. The model, observer library/stage, LUTs, input, cap 1, 300-second deadline and capture limits were otherwise unchanged.

## Execution succeeded; the paired capture did not

- All **128 actual non-cache input buffers** completed: **65,536,000 bytes**, covering steps 0–15 and final `n_past=1920`, `n_process=9`.
- The genuine selected-ID observer recorded exactly ordinal 0 / token **818**. The output is 3 bytes. The retained Genie profile's `num-generated-tokens` counter is **0**; it is not silently rewritten to match the selected-ID count.
- **No final-logit payload exists.** The journal has 128 completed payloads and no capture-error marker.
- The real binder rejected the capture with `complete128 non-cache inputs plus final logits required`, before creating a bound-input directory or executing a model.

The conditional host reference remains **unstarted**. Do not manufacture a comparison from these inputs, partial debug logits or the selected token, and do not stitch them to a future run's vector.

## Why the output observer was bypassed

The saved runtime identifies the actual PLE path:

> per-layer embeddings not yet supported in CB scheduler — using legacy strategy-loop path

It then records `getDequantLogits Returning 1*262144` for the final AR128 step (`n_past=1920`, `n_process=9`). The original observer was placed only in **`getLogits(Tensor&)`**, which this route bypasses. This is an observer-dispatch defect, not evidence that the model omitted its logits.

Pi authorized host-only relocation into the actual `getDequantLogits` path, after its original pointer offset and before its unchanged `deQuantizeOutputs` call. That pointer already selects **row 8**; applying another row-8 offset would be wrong. A real-dispatch sentinel regression and separate frozen observer derivative are required before any newly scheduled capture.

## Resource result and causal limits

The old 8 GiB shadow-stack failure and QNN 5005/6000/1009 errors remain preserved separately. Those errors were not present in this run; the sole error-level provider message was the known unsupported-`usesCrossAttention` warning.

This run's maximum recorded kernel VmPeak was **8,554,459,136 bytes**, below the old 8 GiB cap, and its starting virtual layout differed from the failed run. Therefore this single success does **not** prove that 12 GiB was uniquely necessary or that AS alone explains every prior failure. It establishes successful execution under the explicitly larger allowance, not a physical-RAM-budget increase or a QNN fidelity fix.

Minimum sampled AS headroom was **4,345,516,032 bytes**; maximum sampled RSS **205,819,904 bytes**; minimum sampled MemAvailable **2,814,427,136 bytes**. HTP-private memory remains unknown. Query/TTFT timing includes diagnostic capture I/O and is not a comparable performance benchmark. No long-generation quality conclusion follows from cap 1.

## Raw preservation, privacy and release

All 67 ADB operations were under `phone.lock`. Fresh preflight and actual postflight verified `939c731e…ed1023c` / `1b2ef1c1…ef1612f`. Raw pull completed before independent cleanup; all owned roles/root were verified absent; no signal was sent. The lease was released promptly for Janek, with no second attempt.

All input tensors, complete tokenizer IDs and the full provider log remain private and hash-bound. The public provider file is a **labeled execution/dispatch metadata extract** that omits neural debug values; battery files are labeled current-state extracts. The outer `SHA256SUMS` describes these extracts; the copied original controller manifest describes the complete private originals.

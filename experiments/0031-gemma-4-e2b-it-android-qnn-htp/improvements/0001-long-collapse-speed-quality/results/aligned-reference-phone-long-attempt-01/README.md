# Aligned GPU long reference: sensible completion

**The single authorized request completed with the exact1929 single-BOS input IDs and no obvious repetition collapse.** This establishes a sensible same-input reference, not a particular QNN defect or a repair of the QNN route.

## Actual run

- Run `aligned-long-20260912T100120Z-01`; consumed slot `pi-gemma-aligned-gpu-long-20260912-a`.
- Readiness `4eedb257`; stage digest `247493005323235fac12203085f5d07599f179249bbbde908d4c17c288678e92`.
- One fresh LiteRT Session/GPU request, context8192, max2048. No warmup, second request, rewind, alternate backend/cap, `:nocache`, EOS change or replay.
- All1929 actual pre-RunPrefill IDs independently match the frozen int32le bytes: SHA256 `3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64`. The actual prefill counter is also1929. The saved rendered body matches the planned removal of only the caller-owned `<bos>`; metadata still supplies the single BOS.
- GPU-only request settings, the bound GPU accelerator and Adreno driver libraries, `/dev/kgsl-3d0`, and normal task completion are retained. This is not a claim that every supporting operation is CPU-free.
- Native/controller exits0. The task reports `done`, no runtime error,643 delivered callback IDs and runtime generated count644. The runner labels the below-cap completion `eos`; the actual filtered terminal ID remains **unknown**.

## Exact output and comparison

The complete3717-byte output is a sensible natural-language summary of the benchmark brief, with no obvious repetition collapse. It starts “This brief outlines a rigorous framework…” and ends with a practical measurement recommendation. This is the narrow output-sanity check, not correctness, quality, grounding or human acceptance.

Output: [`raw/controller/raw/device/outputs/aligned-reference-long-01.txt`](raw/controller/raw/device/outputs/aligned-reference-long-01.txt)

SHA256: `c64a18a7e0059a2a874b6310133f4f00f53f0f2c1d8b935acaec3d29c6d0d55d`

The643 actual **stop-filtered callback IDs** are retained separately (`026f8f05…71fbca`). Frozen descriptive metrics give four-gram unique ratio0.996875, no exact periodic suffix within the frozen detector's range, and no rolling-collapse trigger. The full output was read rather than treating null detector fields alone as a pass.

The reference differs from the QNN accepted-selection trace at token index0:2094 versus818. That is an observed trajectory difference, not causal localization. Reference callback filtering cannot establish absence of sampled1,50 or106, and cannot recover the terminal token. The earlier complete QNN selected-ID trace remains a separate observation.

**Interpretation:** the same effective single-BOS workload does not require the observed QNN collapse on this reference. The historical double-BOS CPU/GPU results remain unchanged. Model artifact/quantization, frontend/runtime build, backend arithmetic, context capacity and stop-policy differences still prevent this from being a matched numerical ground truth. QNN long-output reliability and root cause remain unresolved; no further precision or EOS sweep follows automatically.

## Timing and lifecycle evidence

One engineering observation, not an accepted speed comparison:

| Measurement | Observed |
|---|---:|
| Setup |11.504s|
| Request-to-first-token |4.071s|
| Prefill |3.969s|
| Decode callback interval |27.261s|
| Total request |31.332s|
| Peak sampled process PSS |909,882,368 bytes|
| Process VmHWM / ru_maxrss |918,790,144 bytes|

Setup includes the fresh GPU route/cache initialization. Output length and operating/build conditions differ from QNN; this is not a normalized QNN speedup. Process memory is not total GPU-private allocation, which was not separately measured. Raw timings, memory sampling semantics and operating observations remain in `result.json` and the runner evidence.

All149 ADB calls held the full non-inherited lock. Complete raw evidence was pulled before remote-root removal; scoped model/wrapper/watchdog processes and root were verified absent. **No signal operation was needed.** The lock was released. Live preflight and prelaunch target-process absence passed, and an additional read-only postflight check confirmed the installed app/test hashes remained `e1b33f…`/`060edd…`. The task made no app, app-data or model-pack changes.

All622 original controller hash entries were verified. Full battery dumps remain private and hash-bound; only labeled extracts are included. The first offline analysis used the wrong rendered-file name and is preserved in `analysis-attempt-01.json`; the corrected analysis uses actual `rendered-long.txt`. Both analysis passes used the **same captured request**, with their retained raw files independently compared. No inference was repeated to fix analysis. The actual launcher, grant, source hashes, postflight wrapper and test receipts are retained with this package.

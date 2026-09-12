# Offline provider-route memory assessment — 2026-09-12

## What3.5GiB meant

The app gate inherited3.5GiB from experiment0037's HTP controller (`htp/tools/run_phone.py`, introduced with155d61eb), which explicitly required3584×1024KiB available before staging. It was a conservative chosen safety floor, **not an observed OOM threshold, a proven allocator minimum, or an inherited Gemma weight requirement**. Both0037 and the new app have at most **four resident sessions**;32versus4 total constructors must not be advertised as an8× peak-memory reduction.

The successful0037 HTP run started with4,546,780KiB available; minimum sampled available memory was4,038,444KiB, a508,336KiB (~496.4MiB) decrease. Its own-process lifetime peakRSS was173,864KiB, sampled peakRSS77,816KiB and PSS74,440KiB. Device-wide variation is not attributable memory accounting, and processRSS/PSS does not include all DSP/DMA/global allocations. None of those observations proves a safe universal lower starting floor.

## Actual generic pack metadata

Offline QNN System binary inspection of the **actual app binaries**, with no context load, neural Run or phone access, reports:

| Context | Declared storage sum | Sum +128MiB allowance, rounded to64MiB |
|---|---:|---:|
| Generic duration |10,215,936B|192MiB|
| Generic text |25,766,656B|192MiB|
| Shared vector |185,444,096B|320MiB|
| Shared vocoder |178,103,040B|320MiB|
| **Resident total** |**399,529,728B (~381.0MiB)**|**1GiB**|

Sums include reported IO, op data, constants, DDR tensors, shared weights and spill/fill. Shared weights are reported as zero; no unverified resource sharing is assumed. Serialized categories can overlap and hidden allocator/backend costs may be omitted, so the1GiB figure is a **planning provision, not a proved allocation upper bound**. The old worst-size exactT309 duration/text pair plus these same shared contexts declared403,975,680B, slightly more than the generic set—not orders of magnitude more.

All four binaries total212,603,064B (~202.8MiB); largest is vector136,490,968B (~130.2MiB). Pinned ORT `onnx_ctx_model_helper.cc` reads an external binary into a local `unique_ptr<char[]>`, passes it to context creation, then releases that source buffer when the function returns. Constructors are serial. The ordinary path therefore has a largest single source-read buffer, not four app-held whole-binary copies; QNN-internal copies remain opaque. Budgeting256MiB for serialization/copies is conservative and intentionally may overlap declared constants.

## Additional app allocations

- **No Gemma load:** this is an AUDIO-only job. The application never constructs/loads a Gemma engine for this test. Model files merely present on disk are not charged as resident Gemma weights.
- **Managed/UI/native/framework allowance:512MiB.** Covers main/instrumentation and generation process startup, native library/code pages, Room/Compose and allocation uncertainty. This is not a measured app baseline and is deliberately generous.
- **Explicit buffers:64MiB allowance.** The native Gaussian probe can overlap one8.64MB native array, one8.64MB Java float array and one8.64MB ByteBuffer (~24.7MiB); the native array is temporary, but retained Java liveness is not optimistically assumed. Vocoder output plus copied vector can overlap12MiB; text/latent/ORT output copies add roughly2MiB; indexer/Unicode/frontend/metadata add several MiB. Most may overlap the framework or QNN allowances; no claimed exact accounting.
- **WAV/page-cache allowance:64MiB.** The app streams PCM assembly with64KiB buffers and a26,460B gap buffer; it does not retain a whole chapter float array. Diagnostic retained chunks, complete chapter and master total roughly56MB on disk for this reference. File page cache is generally reclaimable and is not equivalent to committed model memory, but allowance is retained.

The deliberately additive envelope is **1024+256+512+64+64=1920MiB**, including substantial overlap/margins. Adding the old600MiB emergency reserve gives2520MiB. This supports evaluating a **2.5GiB starting floor only alongside fresh owned low-headroom handling**, rather than asserting it is intrinsically safe. A revised validation gate should check at context/segment boundaries and monitor while running, stop only authenticated owned work before exhausting the reserve, retain at least the prior600MiB emergency boundary (prefer a proactive higher threshold), and never close unrelated work. Candidate03 did not yet have that continuous owned-run guard; its threshold was **not lowered**.

## What actually happened

The corrected preflight first observed ~2.76GiB after closing the proven-idle app and correctly stopped before installation/inference. Moritz then permitted closing ordinary background apps. One read-only selection capture found that Android headroom had already recovered to4,129,952KiB; **no third-party app was closed**. The subsequent app run passed the unchanged3.5GiB gate (3,810,344KiB immediately before inference), completed all165 neural calls and a210.184s WAV, and failed only at same-directory file publication. End headroom was3,887,080KiB and battery34.1°C; own-process lifetime peakRSS337,124KiB remains a process-only observation, not totalDSP memory. No OOM was observed.

Thus neither a lower neural floor nor unrelated app termination was needed for that run. The remaining exact-byte publication recovery is explicitly **non-neural** and has its own modest copy/UI headroom requirement; that is not a lowered neural-generation gate. The1GiB host metadata container exited and was removed. No phone calls or model execution were used for the offline binary-budget extraction.

# Isolated HTP Mean returns low code 1; epsilon-Add matches the literal codes

**Valid operator-specific evidence, not a universal floor or a QNN/model defect.** `mean-add-20260914T164350Z-01` executed `mean_edge` and `epsilon_add` **once each**, in separate native processes under one continuous phone lease. Native/controller exits were 0. Both metadata files report `inferences_completed: 1`; exact named-selection argv and compiled→execution tensor name/ID/shape/type bindings pass.

| Control | Input patterns, repeated 32× | All observed output patterns | Literal finite comparison |
|---|---|---|---|
| Mean, axis 2 over 1,536 channels | zero; one code 1 with 1,535 zeros; uniform 1; uniform 20 | **1, 1, 22, 434** | 0, 0, 22, 434 |
| Epsilon-Add | 0, 1, 22, 434 | **0, 1, 22, 434** | 0, 1, 22, 434 |

All **256 words / 512 bytes** were checked, not only the first four rows.

- Mean raw SHA-256: `9bcb2e46917d0b6df8e3aa7750fe69584f43942ee351bd7cb4c39f9afcacc268`.
- Add raw SHA-256: `5ff936a2c2da774eb7e02baf4c639b1b8d3957b8566dc9a2244be1718fbdc81f`.

The Mean bytes match the preceding chain's named mean readout. The isolated graph has no Add, Power or second output. Therefore **chain fusion/multiple-output aliasing is not needed to explain the observed low code 1 in these controls**. This does not identify the internal kernel or exclude every implementation/materialization mechanism in the separate chain context.

## Exact finite rescale errors

The authoritative compiled grids are input scale **0.5050163865089417**, output scale **0.023287702351808548**, both offset zero. Treating those IEEE scale values as exact real numbers gives:

| Mean pattern | Ideal output-code coordinate | Observed code | Error versus nearest code | Decoded error versus ideal real mean |
|---|---:|---:|---:|---:|
| Zero | 0 | 1 | +1 | +0.0232877023518 |
| Sparse one | 0.0141184692676 | 1 | +1 | +0.0229589156418 |
| Uniform one | 21.6859687950 | 22 | 0 | +0.00731306523085 |
| Uniform twenty | 433.719375900 | 434 | 0 | +0.00653509050608 |

Mean differs from the frozen nearest-even comparison at **64/128 codes**, maximum **one output quantum**. This is an observed error, **not a documented allowable error bound**. None of these coordinates is a half-integer tie.

For Add, the declared real epsilon is `655 × 1.5259021823865737e−9 = 9.994659294632058e−7`, or **4.2918185502555006e−5 output steps**. Its FP32 decode is `9.994658967116266e−7`; this small distinction changes none of the four expected integer codes. All Add codes match; decoded error against ideal real addition is minus the real epsilon. No positive floor is introduced at zero.

`analysis.json` preserves exact rational coordinates/errors as well as readable decimals. This is a finite comparison against declared grids, **not reconstructed DSP arithmetic**.

## Recorded precision/profile and documentation limits

Actual I/O is **UF16**, not Float16 transport. The authored/inspected graphs each contain one operation. Compiler metadata records optimization type 3 and `fp16_relaxed_precision: 0`; neither establishes internal accumulator precision or the fixed-point rescale implementation.

The saved basic profiles report four HVX threads and selected-graph RPC/accelerator execution. Mean: 3817/3048 µs; Add: 3795/2982 µs. Average/min/max are three views of **one execution**, not three runs. Thread counts do not identify an operator kernel; these single-fixture timings are not a performance claim.

Reviewed SDK sections define Mean/Add semantics, UF16 support, and general converter nearest-integer quantization with representable zero. They do **not** supply a ReduceMean minimum-one rule, instruction-level rounding scheme or a one-code runtime error tolerance. Float-model FP16/associativity notes cannot establish precision of this UF16 operation. Source hashes/sections and scoped conclusions are in `source-profile-audit.json`.

## Lifecycle and investigation boundary

All **95 ADB operations** occurred under one lease; each phase and final owned-role absence passed. Raw pull completed before root removal; no signals occurred; actual `bf53c566…` / `f1543993…` postflight passed; phone released before analysis. Both phases read back AS12 GiB and FSIZE8 MiB. Private originals and both raw arrays are hash-bound; battery files are labeled current-state extracts.

No Power/chain/model/reference rerun or arithmetic policy patch was performed. In particular, **Mean→max(1,q) is not adopted**. The observation explains why literal node-by-node composition can hit a pole that this synthetic HTP path avoids. It does not establish that the same real Gemma activations caused long-output repetition.

The next proposed checkpoint uses **already-saved full-vocabulary endpoints**, not another DSP control or full reference execution: [NEXT-CHECKPOINT.md](NEXT-CHECKPOINT.md).

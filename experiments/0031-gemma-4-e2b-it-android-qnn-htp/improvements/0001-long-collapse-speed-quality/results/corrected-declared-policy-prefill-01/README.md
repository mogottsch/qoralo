# Storage-corrected reference: partial result at a zero-power edge

The separately granted `corrected-ref-20260914T082259Z-01` run used the same complete captured inputs, final DLC policy and own 30 caches, with the tested Float16 storage correction and first-nonfinite guard. No phone or model variant was introduced.

It completed **five chunks**, then stopped in chunk **5** (the sixth AR128 chunk), operator **6294 / `node_pow_606`**, with NumPy's **`divide by zero encountered in power`**. Child/guard/service/controller exits were 1; the child was reaped. Guard wall time was **164.292 seconds**, service memory peak 4.5 GiB / zero swap. There was no memory/time-budget stop. The trace has **40,760 begins / 40,759 ends** and preserves the interrupted operation.

**No final corrected reference vector exists; there is no corrected full-vector comparison.** The grant is consumed. No automatic full-prefill or phone replay occurred.

## The stop is a numerical-policy boundary, not proof of model failure

The saved chain is layer-31 post-feedforward normalization:

1. square;
2. mean;
3. add epsilon;
4. power −0.5;
5. multiply back into the activation.

Epsilon decodes to **9.994658967e−7**, while the mean/add output grid has scale **0.02328770235**, offset 0. Exhaustively checking all 65,536 representable mean codes shows that adding epsilon changes **no code**. A zero mean therefore remains zero at the next declared boundary.

IEEE `0^−0.5` is a **positive-infinity pole**, not NaN. The conservative guard deliberately stops there; this alone does not establish a QNN/model failure or prove what the quantized HTP backend must do. No epsilon floor, fusion assumption, upper clamp or NaN repair has been adopted.

## Bounded QnnCpu scalar fixtures

Authored host-only fixtures use the actual grids and exponent, not LLM data:

- Exact UF16/UF16 Power is rejected at node validation with **3110** (`QNN_OP_PACKAGE_ERROR_VALIDATION_FAILURE`). CPU documentation lists FP32 and UF8 Power support; HTP documentation lists UF16 support.
- F32 Power executes successfully and returns **+Inf** for zero.
- F32 Power followed by Convert, and direct F32-special-value Convert, execute successfully but map **+Inf, −Inf and NaN to code 0**, not upper code 65535, on this host CPU route.

These CPU observations do **not** establish HTP behavior, justify NaN repair, or prove an upper-saturation policy. Reviewed generic quantization documentation describes clamping but does not settle the nonfinite edge. The existing host `libunwind.so.1 → libunwind.so.8` compatibility alias and C++ dependencies are hash-bound; no dependency was installed or changed.

The first fixture could not load the existing CPU backend without that compatibility path. The second stopped before execution because non-static tensor buffers were incorrectly attached at creation (7004). Both are retained separately. The corrected fixture follows the documented creation/execution buffer boundary; three scalar graphs execute and the exact UF16 graph remains explicitly unsupported on CPU.

## Next bounded checkpoint

Pi authorized **host-only preparation** of a tiny HTP edge/fusion discriminator: isolated same-grid Power plus a small normalization-chain control, with an explicitly instrumented intermediate-output variant. Exposing intermediates can change fusion opportunities and must be labeled. A physical window will be scheduled only after Nik's priority work and stable USB; no device grant exists yet.

All partial reference arrays/trace remain private and hash-bound. The first-error receipt and bounded derived metadata are retained publicly. Earlier invalid-reference vectors and their additive notice remain unchanged.

# Corrected FP16 storage boundary and nonfinite stop guard

This source-frozen adapter preserves the original invalid reference and corrects only the declared **Float16 static-storage boundary**. No model, DLC, grid, weights, input bytes, cache rules or device runtime is changed.

`declared_dlc_reference_fp16.py` pins the original source `06f108e2…2045`. Count-checked, invertible changes normalize **declared Float16 uint16 transport words** into binary16 views before preserved-memory operations and decoding. Thus `0x3c00` becomes 1.0, not 15360.0. True UF16/grid tensors and BW4 signed decoding are untouched. Already-typed FP16, readonly/strided buffers, endian variants, signed zero, subnormals and special bit patterns are tested independently.

## Stop on the first unexpected nonfinite

The adapter checks graph inputs, decoded operator inputs, logical outputs, encoded outputs and the pre-round/clip quantization expression. Bounded scans use at most 262,144 elements per diagnostic block. NumPy overflow/invalid/divide-by-zero traps also cover hidden expression failures such as RMS square overflow; underflow remains normal precision behavior.

The first unexpected nonfinite is recorded in exclusive, flushed **`native/nonfinite-first.json`** with chunk/operator/tensor/phase and bounded diagnostic metadata. Execution stops; expressions are not replayed to obtain diagnostics. No NaN is silently cast into a valid integer code, and no arithmetic repair is applied. The original declared rounding and clipping of **finite** values remain unchanged.

## Regression evidence

Focused tests validate:

- all 30 actual static FP16 tensors against independent IEEE decoding;
- endian, strided/readonly views, signed zero, subnormal and special-value bit preservation;
- actual loader → preserved Reshape → first RMS path → identity Cast on synthetic data;
- unchanged UF16 and BW4 behavior;
- first-nonfinite capture before integer conversion, hidden RMS/FP16 overflow, bounded strided scanning and immutable first-error receipts;
- a distinct corrected grant, exact same capture binding and unchanged resource limits.

The original invalid vectors/comparison remain preserved with an additive notice. These tests establish the corrected storage contract, not full QNN agreement or model quality.

## One separately authorized host execution

`run_corrected_paired_prefill_host.py` binds a **new one-use grant** to the same complete capture and installs the corrected reference only inside its bounded compute child. The original input/cache runner and all original source files remain unchanged and hash-verified.

Limits stay **12 GiB RAM / 2 GiB swap / 2 CPU / 1,800 seconds / 1 GiB new output disk / 64 MiB trace**, with unchanged headroom checks, own 30 caches and no memory-lock admission. There is no phone recapture, variant or automatic retry. Full vectors must be saved before comparison; any new nonfinite or residual contract uncertainty must be retained and reported.

# One next checkpoint: saved QNN/native-QAT endpoint rank comparison

**Proposal only. No additional phone, model execution, reference replay or DSP-policy patch is requested by this document.**

## Question tied to Gemma fidelity

After the same 1,929-token history, is the QNN endpoint broadly rank-aligned with the independently completed native-QAT CPU control, or is there already broad full-vocabulary disagreement before the repetitive decode suffix?

The invalid V1 portable vector cannot answer that question. The corrected portable run has no endpoint. Continuing to fit each DSP reduction boundary would be an open-ended detour. Two valid, independently computed endpoint vectors already exist:

- Actual QNN final-row8 UF16 vector: **`7b6c6e2d755a024e59d8ac05fbe4a27e992bfa4774c2286fff85144da26bafe9`**, 262,144 values; unique argmax **818**.
- Native-QAT CPU BF16 endpoint: **`021585a71f18f3e9a071455864bde306762ff052afabc190b28f0527a535b28c`**; its exact F32 expansion is **`f2c76d883ed7c67554357d8aa9958803e288adf1e83eb6557b9c3a21d0b253ec`**; argmax **8291**.
- Both must revalidate input-ID hash **`3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64`**, vocabulary mapping, saved provenance and the native BF16/F32 expansion before comparison.

## Discriminating predictions

- **Small endpoint ranking drift:** substantial overlap among fixed top-5/20/128 sets, and each route's winning token remaining near the other's top ranks. A different first token would then be insufficient evidence of catastrophic prefill divergence. It would weaken the case for treating this tiny Mean discrepancy as the repetition explanation.
- **Broad endpoint drift:** low top-set overlap and substantially displaced winning-token ranks. This would show that broad route disagreement is already present at the prefill endpoint, not created entirely during decode. It would neither identify the responsible artifact/policy/backend boundary nor rule out a decode-specific cause of repetition.

These are comparative predictions, **not quality acceptance thresholds**. Native BF16 ties need rank intervals/average ranks and explicit top-k boundary-tie handling; do not invent a unique rank or choose tie-breaking to improve overlap.

## Execution and stop criterion

One saved-only analysis under **1 GiB RAM, zero swap, one CPU, 60 seconds and at most 1 MiB new output**. No model libraries, model forward/generation, ADB, cache injection or output repair. Read the existing arrays, verify bindings, then report fixed top-k overlaps, winner cross-ranks, tie counts and a whole-vocabulary rank statistic. Compare ranks first; do not silently assume native and QNN absolute logit magnitudes/soft-capping are identical.

Stop immediately if a binding, finite-value or expansion check fails. Otherwise stop after **one bounded comparison packet**, regardless of the result; do not automatically launch another precision variant, micro-op sweep, full reference or phone run.

## Remaining empirical limits

The native QAT policy (mixed INT2/4/8, BF16/SRQ) is not the final QNN DLC's calibrated policy. Thus this is a **same-input independent control**, not matched-policy DSP ground truth. Endpoint agreement is not long-generation quality, and disagreement does not distinguish export quantization from HTP arithmetic. Actual full-model intermediate zero rows, internal ReduceMean precision/rescale, and the repetition cause remain unresolved.

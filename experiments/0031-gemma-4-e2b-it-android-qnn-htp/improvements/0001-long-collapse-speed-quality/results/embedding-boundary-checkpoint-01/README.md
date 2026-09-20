# Frozen checkpoint: the model input boundary is the only comparable boundary left

**Frozen, not executed.** No forward, phone action, comparison run, or policy fitting happened here. The endpoint packet and its disclosed output-budget exception are unchanged.

## What saved evidence actually supports

Pi asked for an earliest captured intermediate with both sides available. Checking the saved inventory:

- The QNN capture contains **graph inputs only** — 8 non-cache inputs per chunk across 16 AR128 chunks — plus the final row‑8 logits. **No internal layer activation was captured on the QNN route.**
- The native-QAT run saved **only the final logits** plus module call counts. **No internal activation was saved on the native route either.**

So **per-layer localization is not decidable from saved evidence.** No captured intermediate exists between the model input and the endpoint on either route, and the endpoint has already been compared. That limit is stated here rather than worked around.

Exactly one boundary other than the endpoint still has concrete data on both sides: the **model input**. The QNN side has actual captured `inputs_embeds` and `per_layer_inputs`; the native side has the static embedding tables of the **same checkpoint** (`efab4290…`) that the native run loaded, with a fully declared transform. That is the frozen checkpoint.

## The frozen comparison

For exactly the **1,929 captured IDs**, compare:

| Side | Source |
|---|---|
| QNN | Deployed UINT8 LUTs (`3b55bb6b…`, `bc5f25db…`), requantized to the graph UF16 grids; captured payloads already validated equal to that host formula |
| Native | `embed_tokens` / `embed_tokens_per_layer` quantized tables plus per-row scales from checkpoint `efab4290…`, with the declared INT2/INT4 sign mapping and architectural scale |

The LUT provenance records the same checkpoint hash and names the exact source keys, so both sides descend from one artifact through a **declared** path. The architectural scale **39.191835884530846** was verified to be exactly `sqrt(1536)`. Recomputing the UINT8→UINT16 conversion from the declared LUT encoding and graph grid reproduces the recorded export-boundary contract (`81.15119161593829`, offset `16574`). **Zero free or fitted parameters.**

A bounded consistency check ran during the freeze: all **196,608** captured chunk‑0 embedding codes lie inside the declared LUT image, spanning exactly **16574–37267** across 70 distinct codes. That is consistency with the declared requantization, not equality to native embeddings.

## Predictions

- **Consistent with declared quantization:** per-element differences stay inside the declared budget with no systematic sign or scale pattern. Then both routes start from the same embeddings up to declared quantization, and endpoint divergence arises at or after the first in-graph operation. This still identifies **no layer**.
- **Divergent before any transformer arithmetic:** a systematic offset, a missing or extra architectural scale, wrong row order, or differences far beyond the budget. Then endpoint differences cannot be attributed to in-graph HTP arithmetic alone.

The per-element budget is declared, not fitted: LUT UINT8 half-step **0.0252606476**, plus measured UINT8→UINT16 added error **≤ 0.00080416**, plus the native **BF16 half-ulp at the element magnitude**. This is a storage/quantization budget, **not an accuracy acceptance threshold**.

Difference distributions, worst rows and the exact fraction outside budget are reported either way, with no pass/fail quality verdict.

## Stop criterion and envelope

Stop immediately on any binding, size, hash or dtype failure. Otherwise stop after **one bounded packet**, whatever the outcome — no variant, no second boundary, no repeated reconstruction, no automatic follow-up.

If separately authorized, the envelope is **2 GiB RAM, zero swap, one CPU, 300 seconds, 256 KiB new output**, with preparation spill counted in the output accounting, and **zero** forward calls, ADB calls and token-text decoding. It reads static tables and captured payloads only; a table gather with declared dequantization is not a transformer forward.

## Limits

This cannot decide which layer or operation diverges, cannot attribute the repetition collapse, and establishes no QNN defect, quantization-only cause, or HTP kernel behaviour. Agreement at the input boundary would not imply agreement later.

Five regression tests pass. The first test attempt failed on my own wrong expectation that BF16 has 8 explicit mantissa bits; BF16 has 7, and the tool was already correct. Both the failing and corrected receipts are retained.

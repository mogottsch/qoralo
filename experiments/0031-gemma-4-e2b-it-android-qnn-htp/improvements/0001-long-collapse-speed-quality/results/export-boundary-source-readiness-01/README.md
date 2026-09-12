# Where to put the next matched comparison

**Source inspection is complete; another inference run is not yet ready or authorized.** The native-QAT checkpoint (`a10cab6c`) is valid, but comparing its selected ID 8291 with QNN 818 or LiteRT 2094 cannot localize a defect. These routes implement different numerical policies.

This audit parsed saved graph/encoding metadata, inspected hash-bound source, enumerated the 256 possible LUT codes through the recorded input-grid conversion, and inventoried retained QNN evidence. It instantiated no neural model, created no inference session, ran no forward, and made no device call. The bounded metadata service exited 0 in 0.924 seconds, using 224.3 MiB peak memory and no swap.

## What is actually bound

| Boundary | Evidence | Consequence |
|---|---|---|
| Native source | Pinned mixed INT2/4/8 weights, BF16 computation, 552 observed SRQ8 calls / 550 calibrated | Complete native logits are available, not a QNN w4a16 oracle. |
| Published archive | `args.json`: QAT-mobile checkpoint, w4a16, 20 calibration samples, Seq-MSE enabled | Archive provenance points to a QAT source, but does not identify the exact exporter revision. |
| Actual dynamic ONNX | SHA `51d4e818…bf0d0`; PyTorch `2.10.0+cu128`; 9,596 standard-domain nodes; no local functions or explicit Round/Clip/QDQ nodes | This float graph does not implement native SRQ8 rounding. Its encoding sidecar is separate from the float computation. |
| Archive encoding sidecar | 522 INT4 parameter entries; 6,194 INT16 activation entries | This is a different quantization policy from the native control. Running plain float ONNX would not simulate it. |
| Available exporter source | Clean AI Hub Models v0.61.0, `5975a79b…d8bd5`, uses original float checkpoint defaults | It is not proven to be the archive's producer and must not silently replace it. |

The available v0.61.0 `deq_proj` casts `.weight` to FP32; it does not unpack QAT packed weights or apply `weight_scale`/SRQ. Its embedding loader expects float `.weight`, whereas the retained QAT tables use `embedding_quantized` and block scales. Casting packed codes is not dequantization. No attempt was made to instantiate this mismatched loader as a reference.

The prior full-head audit proves equality of **every exported float head value** with F32 dequantization of the native source head (and equal-content token embedding). It does not establish all active weight mappings, native BF16 arithmetic equivalence, or full exporter fidelity. No head replacement is justified.

## LUT and PLE are additional numerical boundaries

The actual QNN LUT builder—not the current float-only exporter helper—unpacks the QAT token table (INT2) and PLE table (INT4), applies per-row/per-block scales in F32, folds in `sqrt(1536)` / `sqrt(256)`, then globally requantizes each complete table to UINT8. Native embedding execution instead rounds scales, products and outputs in BF16. Those paths are not bitwise matched.

The frozen source-built Genie path then converts UINT8 LUT codes to the actual UINT16 graph-input grids. Its requantization offset is stored as an `int32_t`, and final integer casts truncate. The PLE conversion also clamps; the main UINT8→UINT16 branch does not. Enumerating **all 256 codes** with the saved exact scales found no out-of-range value in either path:

| Graph input | Output-code range | Maximum added conversion error |
|---|---:|---:|
| `inputs_embeds` | 16,574–37,267 | 0.000804162 |
| `per_layer_inputs` | 6,012–59,637 | 0.000589582 |

These are source-modeled conversion errors relative to dequantized LUT values—not runtime tensor captures, native BF16 errors, or proof of model fidelity. The earlier global UINT8 LUT quantization is a separate, coarser step. Do not use a generic nearest-rounding QDQ helper and call its graph inputs identical to Genie.

PLE layout is `[batch, sequence, 35, 256]`, with 8,960 token-identity values per token. Native and archived graph interfaces place the context-dependent projection/normalization/blend **inside the decoder graph**. A reference must supply raw scaled token-identity PLE, not project it twice. Native source projects the main embeddings, applies `1/sqrt(hidden_size)`, reshapes, RMS-normalizes, adds token-identity PLE, and multiplies by `1/sqrt(2)`.

The actual Genie source copies real per-layer rows first and fills remaining AR slots with the EOS embedding. A public helper that left-pads tokens is not automatically equivalent. The final AR128 chunk has only nine real tokens; its valid row, padding, masks, positions and cache placement must be explicitly bound rather than guessed.

## Saved raw-prefill logits

The complete native BF16/F32 vectors from `a10cab6c` are retained privately. No complete QNN-prefill vector was found in the named retained QNN run roots inspected by this audit.

The source-built selected-ID run contains **2,048 `input-logits` records**, every one with **10 leading and 10 trailing entries**. Bound sampler source explicitly emits only those spans. Actual context output metadata is UINT16 with a scale/offset, so a future capture must retain raw type and quantization metadata as well as the complete payload. Twenty debug entries and selected IDs are insufficient for a full-logit comparison. The filename inventory is scoped to the recorded roots, not a claim about every file on the host.

The existing ORT package can provide a float-graph execution path, but no AIMET-ONNX package was found in the inspected QAIRT environment. No simulator session, model load, dependency install, or CPU-backend compatibility inference was attempted.

## Smallest useful next checkpoint

**Start with an export→execution comparison on one frozen numerical policy, not another native generation or precision variant.** This avoids relying on an unproven historical exporter implementation.

Before spending inference:

1. **Complete a bounded static active-weight mapping gate.** Account for active exported weights, constants and legitimate folds with an explicit, reviewable F32 unpack/transpose/per-head mapping to the native source. The head alone is insufficient, and a reconstructed mapping does not establish the unknown producer revision. Preserve intentional SRQ/dtype differences as differences, not loader fixes.
2. **Freeze an exact external-input ledger.** Use the existing 1,929 IDs, frozen LUT bytes and source-defined requantization; record PLE layout, both RoPE families, the 512-token SWA mask, all 30 cache contracts, AR128 chunk order/padding and final valid row. Reconstruct or capture actual input bytes where rounding matters.
3. **Establish a same-export, same-effective-quantization reference.** It must honor the final chosen DLC's actual weight/activation/cache grids and any precision islands—not merely the original encoding sidecar. Prove an available simulator or portable-backend contract first. Plain FP32 ONNX versus HTP is not such a match, and installing a new simulator is not implicitly authorized.

Once those gates pass and a new scoped run is authorized, the smallest informative numerical payload is **all 262,144 logits at the final valid prefill position**, on both matched arms, with raw dtype, scale/offset and softcap boundary. Run only the exact 1,929-token prefill history; no autoregressive continuation is needed for this checkpoint. Compare full-vector error and ranking/margins, not selected IDs alone. Retain all earlier AR128 cache evolution; do not feed the last nine tokens a fabricated empty cache.

A match would constrain the export→execution path **at that history/position only**. A difference would still need localization against input, cache and numerical tolerances before calling it a backend defect. Neither outcome establishes long-output reliability. To isolate upstream-QAT→export transformations separately, an exporter-semantic reference or preserved producer provenance is still needed; disabling native SRQ or changing dtype and relabeling that result would conceal the boundary rather than test it.

**Current status:** source/metadata evidence ready; matched inference contract not yet ready; no new inference/device grant. Pi reported newer installed app identities `04d9293b…` / `2dd4e0d8…`; future device work requires a new phone slot and fresh full hashes. Never restore the superseded `e1b33…` / `060edd5…` pair.

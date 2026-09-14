# Saved endpoint ranks: shared structure, different unique winners

**One saved-only comparison; no forward, phone action, variant or token-text decoding.** This compares the valid native-QAT CPU endpoint with the actual captured QNN final-row8 endpoint after the same **1,929 input IDs**. It uses neither the invalid V1 DLC reference nor the partial corrected reference.

## Decision-facing results, separate from the global statistic

| Observation | Result |
|---|---|
| Native-QAT unique argmax | **8291**; rank **3** in QNN, no tie |
| QNN unique argmax | **818**; rank **5** in native-QAT, no tie |
| Top-5 intersection | **4/5**; one disagreement per route |
| Top-20 intersection | **13/20**; seven disagreements per route |
| Admissible top-128 intersection | **79–80/128**; 48–49 disagreements per route |

The winner difference is **not resolved by a tie**. In QNN's own grid, native's winner is 1,590 code steps below the QNN maximum. In native's own saved F32 units, QNN's winner is 0.875 below the native maximum. These are separate route-local gaps, not a shared magnitude scale or quality threshold.

The native top-128 cutoff has **13 candidates tied at ranks 128–140 for one slot**. QNN has no boundary tie there. The 79–80 overlap interval covers every admissible choice; no arbitrary ID tie-break was applied. The tie-expanded sets intersect at 82 IDs, but **82 is not a valid top-128 overlap**.

## Global statistic and ties

Full-vocabulary Spearman correlation, computed as Pearson correlation of **average tied ranks**, is **0.8883254478291734**.

This does **not** establish small decision or prefill drift. The vocabulary tail can dominate a global rank statistic; the changed unique winner and the top-k disagreements above remain separate observations.

- Native BF16: 2,226 distinct scores; 261,762 values participate in ties; largest tie 3,930.
- QNN UF16: 11,309 distinct scores; 260,498 values participate in ties; largest tie 149.

Rank calculations use the exact BF16-expanded native values and native QNN UINT16 codes. The QNN grid has positive scale, so code ordering is exactly its declared affine-value ordering. No cross-route absolute-logit equivalence or smoothing was assumed.

## Revalidated evidence

- All **262,144 values** in both endpoints; native BF16→F32 bit expansion and finite values verified.
- Exact **1,929-ID byte equality**, SHA-256 `3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64`.
- Native successful/reaped guard, one-forward/no-generation contract, original capture and strict loaded-head/config provenance; all 32 original private-manifest files verified.
- QNN strict same-run capture binding: all 128 actual input payloads plus complete final-row8 logits, 16 successful AR128 executions and zero AR1 executions; raw-before-dequant/sampler and actual release provenance retained.
- Vocabulary size/output-channel order through loaded native head and prior full native-F32/export head-row audit; identical archive/deployed tokenizer bytes. The tokenizer was **not loaded or decoded**.

Endpoint SHA-256 values:

- Native BF16: `021585a71f18f3e9a071455864bde306762ff052afabc190b28f0527a535b28c`.
- Native exact F32: `f2c76d883ed7c67554357d8aa9958803e288adf1e83eb6557b9c3a21d0b253ec`.
- Actual QNN UF16: `7b6c6e2d755a024e59d8ac05fbe4a27e992bfa4774c2286fff85144da26bafe9`.

Raw vectors, complete input IDs and private content remain in their original private locations. This packet contains hashes and bounded derived statistics only.

## Bounds and implication

Actual service exit **0**; service **448 ms / 66.7 MiB / zero swap** under **1 GiB / zero swap / one CPU / 60 seconds**. The child wrote **9,358 bytes**.

**Preparation output-budget exception:** an overly broad metadata-inspection print expanded the full per-channel head-encoding descriptor into a private tool-managed spill file of **18,753,798 bytes**. Therefore the overall 1 MiB new-output bound was **not met when that preparation spill is included**, even though the bounded comparison service and controlled packet output stayed within their limits. The spill is retained privately, hash-bound in `budget-exception.json`, and not copied into this publication. No endpoint vector or token text was printed by that command. There is no retry or claim that a small final packet repairs the earlier budget breach.

Six new synthetic regression tests passed, including exhaustive boundary-tie overlap checks and a high-global-correlation/changed-winner counterexample. The earlier 380-test suite was not rerun for this narrowly bounded packet.

**The useful implication is that a unique endpoint winner and top-k membership already differ before decode, despite substantial shared rank structure.** These differences were not created entirely during autoregressive decoding. This does not mean that the later repetition is already explained at prefill, nor does it exclude a decode-specific repetition mechanism.

Native mixed-INT2/4/8 BF16/SRQ and calibrated QNN/HTP policies differ; upstream embedding/PLE and LUT requantization arithmetic also differ. This is a same-token-history control, **not same-neural-input or matched-policy ground truth**. There is no QNN-defect, quantization-only-cause, or repetition diagnosis here.

This result does not justify another Mean-floor patch or open-ended DSP emulation. Any next localization should explicitly isolate a known route/activation boundary rather than infer causality from global endpoint correlation. **The one authorized packet is complete; no automatic next execution is scheduled.**

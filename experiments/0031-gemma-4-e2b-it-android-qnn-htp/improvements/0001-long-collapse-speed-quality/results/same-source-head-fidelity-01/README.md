# Same-source fidelity: output-head check and next checkpoint

**Bounded offline investigation only. No model forward, generation, precision build or device access.** This follows the successful input-aligned GPU reference (`6bf2f737`), whose different artifact/runtime is not a numerical ground truth for QNN.

## Check a concrete metadata discrepancy against actual weights

The pinned native QAT configuration says `tie_word_embeddings=false`, whereas the retained float-ONNX export configuration says `true`. That discrepancy is not enough to call the exported head wrong.

The audit compared **every262,144 ×1536 =402,653,184 output-head weight** in the original float ONNX against both separately named source-QAT tables, using the pinned INT2 unpacking and scales:

| Candidate | Different values from exported head |
|---|---:|
| Source output head, float32 dequantization |0|
| Source token embedding, float32 dequantization |0|
| Source output head, BF16-forward scale/product rounding |247,659,600|

The complete exported region and both float32 source candidates share SHA256 `eb7ac2b168bd4446daba2aabf0df0d3a0f7b25dfea5afbcffad375e61e4146fc`. The two separately named source tables happen to have identical dequantized values; their origin cannot be distinguished from equal contents. Thus the metadata discrepancy does **not** establish an output-weight error here. No head replacement or tying change is justified by this check.

BF16-forward rounding gives a different, expected numerical candidate (maximum absolute difference0.000393093). A native BF16 reference must not be silently labeled identical to the float32 export. This check does not cover the rest of the model, DLC requantization, activation arithmetic, HTP kernels or runtime state.

The source checkpoint was freshly verified as `efab4290…76a9a4`,2,458,111,846 bytes. The whole-head scan took23.581s; actual service exit0,1GiB peak/no swap under1GiB/no-swap/1CPU/180s,nice15/idle-I/O limits. Three tiny unpacking/rounding fixtures and the249-test host/source/saved suite pass. Only metadata/hashes/aggregate differences are packaged; model tensors remain private.

## Source-reference loader facts

The exact QAT revision `dd693ff40353f057ca5f07e945ad867f4afbf2ec` uses mixed INT2/4/8 modules, quantized token/PLE embeddings, and the native Gemma SRQ activation path. **630 of632 text/head input/output activation scales are nonzero.** The pinned implementation applies8-bit SRQ rounding/clipping; simply dequantizing weights and ignoring these scales is not the native checkpoint's computation.

The currently installed QAIRT Python environment has Gemma4 architecture code but lacks the `gemma` quantization integration. The old local HF directory held only the safetensors file, and the export config lacks its quantization configuration. Neither is a safe drop-in native QAT loader.

For source readiness, the exact public config and quantization implementation were fetched without new accounts/terms or model downloads:

- QAT config SHA256 `cf6d7dc22738b5e6beb364bac833d78b869f5a6ffd57dfc96c6be3f2abc80424`.
- Transformers integration at `323f24345ed92f88e68a14aeef7db78ee2b52475`, SHA256 `9bf6d109dfc3540a46953f5b183af766edcf6a044529c12d7751db47ee71cc17`, matching the previously pinned LUT dequantization source.

These small source fetches did not install or patch the SDK/environment.

## One proposed next numerical checkpoint

Prepare **one native-QAT CPU prefill forward**, with the exact frozen1929 single-BOS IDs supplied directly, no tokenizer/BOS insertion and no `generate()` call. Use the pinned source configuration, strict complete parameter/scale loading, native quantized modules, evaluation/inference mode, and `logits_to_keep=1`. Retain the complete final-position262,144-logit vector, original dtype, float32 serialization, hashes, argmax and top-k diagnostics. Do not add an autoregressive campaign, an altered-LUT arm or a dequantized-only substitute automatically.

This is an **upstream same-checkpoint control**, not a claim that its native BF16/SRQ8 computation equals QNN's w4a16/export/runtime route. A different argmax alone would not identify a defect. Agreement at this point would not prove later state fidelity. Existing QNN logs expose only selected IDs and rounded logit excerpts, so a complete cross-runtime numerical comparison would still require a separately bounded QNN logit observation; no such capture is authorized or performed here.

**Remaining source-readiness prerequisite:** an isolated pinned Transformers/quantizer loader and strict key/shape/scale validation, without changing the working QAIRT environment. No numerical runner has been loaded yet. A future host forward should use fresh disk-backed scratch, explicit live headroom and approximately12GiB RAM/2GiB existing swap/2CPU/600s limits, adjusted before launch to actual capacity. Missing keys, silently ignored SRQ scales, dtype substitutions or an unsupported loader must block the claim, not trigger a different reference automatically.

This is the next proposed checkpoint, not a root-cause conclusion and not another phone-slot request.

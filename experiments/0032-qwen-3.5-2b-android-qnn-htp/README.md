# Experiment 0032: Qwen3.5-2B Android QNN/HTP

## Status

**Blocked before conversion: no authorized public QNN conversion input exists for the 2B model, and the installed QAIRT Qwen3.5 support is not dimension-compatible with this variant. No compiled context, Android execution, or QNN/HTP result exists.**

This is a separate HTP feasibility arm. It does not change or relabel `0027` CPU evidence.

## Cheapest credible route assessment

Qualcomm's public `Qwen3.5-2B` release at revision `bd885dfceb1a1f45564aef4cd69e183085ea9a24` publishes exactly one deployment route: `GENIEX_LLAMACPP` with an Unsloth Q4_0 GGUF. The pinned artifact is 1,214,873,856 bytes with SHA-256 `cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1` and identifies its architecture as `qwen35`.

That is not a usable QNN path with the authorized installed tooling:

- QAIRT 2.49's direct GGUF builder supports `qwen2` and `qwen3`, but not `qwen35`.
- QAIRT separately dispatches `Qwen3_5ForConditionalGeneration` to an HTP ONNX builder, but that route requires a quantized ONNX graph and encodings.
- Qualcomm AI Hub Models v0.61.0 ships only README/manifest/performance/release metadata for `qwen3_5_2b`; there is no `model.py`, `export.py`, `quantize.py`, public ONNX+encodings checkpoint, or QNN context.
- The installed Qwen3.5 builder hardcodes a 4096-wide start point grouped by 256 and explicitly says to update it when variants have different dimensions. Official 2B geometry is 512 for full-attention KV and 2048 for linear keys. Applying the 4B specialization would be unsupported.

Downloading the 1.2 GB GGUF cannot change this architecture-support result, so the expensive download was correctly avoided.

## Bound frontend contract

The pinned official tokenizer/template was reconstructed independently. With thinking disabled, canonical short/medium/long prompts contain 174/597/1926 tokens and all fit a 4096-token context with the 2048-token ceiling. Rendered prompt and token-ID hashes are in [`protocol/experiment-contract.json`](protocol/experiment-contract.json) and [`results/support-assessment/result.json`](results/support-assessment/result.json).

## Exact unblock action

Moritz must choose one:

1. provide an authorized, provenance-bound Qwen3.5-2B quantized ONNX+encodings input compatible with installed QAIRT, or a complete serialized SM8550/HTP v73 context bundle;
2. authorize authenticated Qualcomm AI Hub Workbench use if it exposes a supported 2B QNN context export; or
3. authorize a separately bound updated QAIRT/toolchain or a Qwen3.5-2B converter implementation that adds `qwen35` GGUF support or correct 2B ONNX builder dimensions.

GenieX llama.cpp NPU metrics, the shipped 4B HTP example, and CPU-only text output are not substitutes for physical QNN/HTP provider proof.

No ADB was used. Phone work remains blocked behind both a compiled route and Pi's explicit priority handoff.

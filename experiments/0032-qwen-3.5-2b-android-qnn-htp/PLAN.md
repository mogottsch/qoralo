# Plan: Qwen3.5-2B QNN/HTP

## Completed

1. Kept `0027` immutable and created independent `0032` ownership.
2. Re-verified the canonical Android LLM protocol and workload hashes.
3. Bound the official Qwen3.5-2B revision, hybrid architecture geometry, tokenizer, template, and canonical 174/597/1926-token prompt inventories.
4. Audited the public Qualcomm release and QAIRT 2.49 support:
   - only a pinned `qwen35` Q4_0 GenieX llama.cpp artifact is public;
   - direct installed GGUF conversion does not support `qwen35`;
   - installed ONNX HTP factory dispatch exists but requires absent quantized ONNX+encodings;
   - public QAIHM v0.61.0 has no 2B model/export/quantize implementation;
   - installed Qwen3.5 specialization hardcodes a 4096-wide start point incompatible with 2B geometry.
5. Stopped before a pointless 1.2 GB GGUF download, unsupported source patch, authenticated service call, or phone access.

## Blocked next gate

One explicit Moritz action is required:

1. provide an authorized Qwen3.5-2B quantized ONNX+encodings input or provenance-bound SM8550/v73 serialized context bundle; or
2. authorize authenticated Qualcomm AI Hub Workbench use if a supported 2B QNN export exists; or
3. authorize an updated QAIRT/toolchain or architecture-aware 2B converter implementation.

If unblocked, the next sequence is: bind conversion artifacts → bounded host preparation → compiled-context/provider proof → coordinated phone viability gate → proven loaded-route isolation → canonical 1+5+5+5 campaign. Until then, do not use ADB, run CPU fallback, borrow the 4B config, or publish.

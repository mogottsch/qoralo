# Plan: LFM2.5-2.6B QNN/HTP

## Completed

1. Kept `0029` and `0033` immutable and created independent `0034` ownership.
2. Re-verified the canonical Android LLM protocol and workload identities.
3. Bound the pinned LFM2.5 source/artifact, 22-convolution + 8-attention architecture, tokenizer, template, and canonical 171/600/1922-token inventories.
4. Audited authorized installed/public support:
   - QAIRT direct GGUF conversion has no `lfm2` entry;
   - QAIRT HTP factory has no `Lfm2ForCausalLM` dispatch;
   - no LFM Genie config or QAIRT release support statement exists;
   - Qualcomm publishes no LFM AI Hub recipe, ONNX+encodings, or QNN context.
5. Avoided a redundant 1.67 GB GGUF download because the exact artifact is already bound and architecture support fails before weights are needed.
6. Stopped before implementing an unauthorized LFM2 converter/runtime or accessing the phone.

## Blocked next gate

One explicit Moritz action is required:

1. provide an authorized LFM2.5-2.6B quantized ONNX+encodings input plus model-specific builder, or a provenance-bound SM8550/v73 context bundle; or
2. authorize authenticated Qualcomm support if a non-public QNN route exists; or
3. authorize an updated/toolchain or new LFM2 conversion/runtime implementation.

If unblocked, work must still establish host equivalence, convolutional/KV state layout, full request-state reset, compiled-context identity, physical HTP binding, fallback boundaries, a bounded phone viability gate, and only then the canonical 1+5+5+5 campaign. Until then, do not use ADB, map LFM2 to another architecture, ignore recurrent state, or publish.

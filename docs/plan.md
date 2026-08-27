# Current plan

## Goal

Build and validate the local inference components required for offline-first mobile podcast generation on Android:

1. local LLM inference, eventually used to generate transcripts;
2. local TTS inference, used to render those transcripts as speech.

The comparable Android LLM benchmark is now established, and six canonical CPU/GPU routes have completed it. The immediate open decision is whether to authorize additional Qualcomm QNN/HTP tooling or architecture-specific engineering; application assembly and transcript quality remain outside the current benchmark phase.

## Scope boundary

The repository covers the two inference components and the evidence needed to select and deploy them. It does not currently cover source acquisition, retrieval infrastructure, application UI, script editing, segment rendering, episode assembly, export, or episode management.

Historical TTS experiments and their claim boundaries remain unchanged. LLM work receives its own protocol, skill, registry, and dashboard rather than inheriting TTS transcript, WAV, RTF, or listening fields.

## LLM evidence language

Keep these claims separate:

1. **Technical execution** — the declared model route completed under the stated runtime, provider, device, and workload contract.
2. **Output sanity** — the exact retained text merely looks sensible rather than obviously corrupted, binary-like, empty, or gibberish. This is recorded only as `looks_sensible` plus failure-only notes and is not a quality verdict.
3. **Performance observation** — setup/readiness, TTFT, prefill, decode, total latency, memory, and thermal measurements apply only to the stated route and workload.
4. **Quality evaluation** — deferred from the first LLM experiments. No successful run or sanity check establishes transcript quality, correctness, grounding, style, or acceptance.

Missing evidence remains null with an explicit reason. Host evidence never becomes Android evidence.

## Comparable Android LLM contract

New comparable routes follow [`protocols/android-llm-benchmark/`](../protocols/android-llm-benchmark/) and the project-local [Android LLM benchmark skill](../.agents/skills/android-llm-benchmark/SKILL.md).

The canonical inference-v1 workload freezes short, medium, and long message bytes. Each route separately pins its model artifacts, quantization, tokenizer revision, native chat template, rendered prompt hash, and effective token IDs because tokenizer token counts are model-specific.

The workload uses a `2048` maximum-new-token ceiling. This bounds execution but is not a target output length. Every request records its actual generated-token count and stop reason. Protocol v2 keeps the expensive model/runtime route loaded, records one first request, then at least five loaded-route requests per prompt tier. Before every request, conversation and KV state must be fully isolated through either a proven complete in-session reset or a fresh Session that does not remap/reload the model or recompile the accelerator.

Required observations include:

- exact model, tokenizer, quantization, runtime, provider, and device provenance;
- the setup/readiness boundary and elapsed time;
- prompt byte and effective input-token counts;
- request-to-first-token and, when observable, post-prefill-to-first-token latency;
- prefill latency and input tokens per second;
- decode latency and output tokens per second;
- total request time and actual output-token count;
- peak memory with method, sampling interval, and lifecycle semantics;
- thermal and power context when available;
- every raw text output and SHA-256;
- exact-hash output sanity using only `looks_sensible` and failure-only `issue_notes`;
- null plus a reason for measurements the route cannot expose.

Tokens per second are always shown with tokenizer identity and actual counts. They are useful route measurements but are not perfectly tokenizer-independent units across model families.

## Current LLM evidence

The [Android LLM dashboard](android-llm-benchmarks/index.html) and [registry](android-llm-benchmarks/registry.json) now publish six canonical Android routes:

1. Gemma 4 E2B IT through LiteRT-LM CPU;
2. Gemma 4 E2B IT through LiteRT GPU;
3. Qwen3.5-2B Q4_K_M through llama.cpp CPU;
4. Qwen3.5-2B Q4_K_M through llama.cpp OpenCL/Adreno offload;
5. LFM2.5-2.6B Q4_K_M through llama.cpp CPU;
6. LFM2.5-2.6B Q4_K_M through llama.cpp OpenCL/Adreno offload.

Each row is backed by a complete one-first-plus-five-loaded-route-requests-per-tier Android campaign. Exact metrics, output hashes, stop reasons, thermal context, and limitations stay in the normalized registry and owning experiments. The GPU/OpenCL rows prove accelerator use but are not GPU-exclusive; disclosed CPU orchestration and unsupported-operation boundaries remain part of each route. Process PSS/VmHWM does not include independently allocated GPU-private or vendor memory.

Host smokes remain viability evidence only and never become canonical Android rows. In particular, experiment 0029's one-request LFM CPU smoke is historical; experiment 0033 owns the complete LFM CPU and OpenCL routes.

## Blocked accelerator routes

Experiment 0030's Qwen Vulkan route is stopped before request one. Three controlled variants failed while the Adreno driver created `mul_mat_vec_q5_k_f32_f32`; no provider-bound inference or performance metric exists. Experiment 0035's successful OpenCL route is separate and must not be relabeled Vulkan.

Three QNN/HTP experiments are blocked before conversion and have no registry rows, contexts, phone execution, or HTP performance claims:

- **0031 Gemma:** installed QAIRT resolves SM8550 to HTP v73, but its high-level factory lacks Gemma4 dispatch and the exact public W4A16 graph fails during ShapeInference/ConstantPropagation with `KeyError('value')` before QNN conversion.
- **0032 Qwen:** installed direct-GGUF support covers qwen2/qwen3 rather than qwen35; no public compatible 2B quantized ONNX+encodings or SM8550 context is available, and the installed Qwen3.5 specialization is dimension-incompatible with the 2B model.
- **0034 LFM:** installed QAIRT and current public Qualcomm materials provide no `lfm2` GGUF, HTP-factory, Genie, recipe, or context route. Its hybrid convolutional/attention state requires model-specific conversion, runtime orchestration, and reset proof.

## Current decision boundary

No currently authorized benchmark execution remains unfinished. Resuming any QNN route requires Moritz to choose and explicitly authorize at least one of these paths:

1. provide provenance-bound SM8550/HTP-v73 contexts and complete runtime/LUT bundles for the exact model;
2. authorize authenticated Qualcomm AI Hub, Workbench, or engineering access, including any service terms or costs;
3. authorize installation and binding of a newer licensed QAIRT/toolchain; or
4. authorize architecture-aware converter/runtime engineering with host numerical equivalence, context identity, full-HTP partition/no-fallback proof, and request-state isolation.

Until then, experiments 0031, 0032, and 0034 remain unchanged. Generic fallback, mismatched model configurations, borrowed metrics, authenticated services, new SDKs, and ad hoc graph patches are not authorized work. The concise cross-route resume record is the [latest accelerator handover](handovers/2026-08-26-android-llm-accelerator-results.md); owning experiment evidence remains authoritative.

## TTS direction carried forward

The TTS record is mature and currently has no active experiment in this plan. The complete normalized evidence remains in the [Android TTS dashboard](android-benchmarks/index.html) and [registry](android-benchmarks/registry.json).

Current bounded conclusions include:

- Supertonic 3 official-source stable-Softplus all-HTP remains Moritz's current listening favorite among reviewed exact samples.
- Experiment 0023 reduced its exact legacy-v1 four-session setup boundary from `21.6129 s` to `0.497816 s` with byte-identical output.
- Pocket's fixed-Alba canonical-v2 CPU and HTP routes are technically complete; experiment 0024 separately reduced setup for its reconstructed derivative from `27.0767 s` to `1.01122 s`.
- Kokoro canonical-v2 completed all 18 fallback-disabled host QNN stages but produced structurally invalid final audio and is phone-ineligible in experiment 0017.
- MOSS canonical-v2 passed CPU and host context gates but stopped at the recorded physical-phone QNN `CreateDevice` blocker.

Listening verdicts remain bound to exact reviewed WAV hashes. None of these conclusions selects a broad model family or establishes production readiness.

## Later work

After Moritz selects a practical LLM route from the current performance evidence, define a separate quality workload for transcript generation. That later protocol can address structure, coherence, source use, style, repetition, spoken-language naturalness, editing burden, and exact-output review without retroactively turning performance outputs into quality evidence.

A future end-to-end benchmark may combine the selected LLM and TTS components. It is an integration view over the two component layers, not a third product-pipeline charter.

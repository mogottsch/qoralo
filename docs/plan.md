# Current plan

## Goal

Build and validate the local inference components required for offline-first mobile podcast generation on Android:

1. local LLM inference, eventually used to generate transcripts;
2. local TTS inference, used to render those transcripts as speech.

The immediate focus is not application assembly or transcript quality. It is establishing a comparable Android LLM benchmark, then using it to run multiple models and quantizations while measuring prompt processing, token generation, memory, and operational behavior.

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

The workload uses a `2048` maximum-new-token ceiling. This bounds execution but is not a target output length. Every request records its actual generated-token count and stop reason. The campaign creates the model route once, records one first request, then at least five same-session requests per prompt tier with conversation and KV state reset before every request.

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

## LLM benchmark foundation

The repository now has:

1. canonical fixed short, medium, and long prompt tiers plus a machine-readable Android LLM contract;
2. a project-local benchmark skill;
3. a separate empty LLM registry, schema, validator, generator, and dashboard;
4. shared project framing for the LLM and TTS component layers.

The empty registry contains no placeholder measurements. Only committed experiment evidence may populate it.

## Next experiment

### 0025 — Android LLM model bakeoff

Open a separately scoped experiment to run several practical LLM models or quantizations under the same inference-v1 workload. A bounded host smoke may reject an incompatible artifact before phone work, but it may not substitute for Android measurements or appear as an Android result.

The first experiment compares execution, setup, TTFT, prefill throughput, decode throughput, total latency, memory, and operational constraints. It retains text only for the narrow output-sanity smoke check. Podcast transcript quality evaluation is deliberately later work.

Model choice, runtime, quantization, CPU/GPU/NPU route, and accelerator selection remain experiment decisions rather than assumptions in the shared protocol.

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

After performance evidence identifies practical LLM routes, define a separate quality workload for transcript generation. That later protocol can address structure, coherence, source use, style, repetition, spoken-language naturalness, editing burden, and exact-output review without retroactively turning performance outputs into quality evidence.

A future end-to-end benchmark may combine the selected LLM and TTS components. It is an integration view over the two component layers, not a third product-pipeline charter.

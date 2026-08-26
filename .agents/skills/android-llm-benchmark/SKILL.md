---
name: android-llm-benchmark
description: Run or publish Android LLM inference benchmarks in this repository. Use whenever an agent runs an LLM on Android, compares local model or quantization routes, measures setup/TTFT/prefill/decode throughput or memory, performs the fixed prompt campaign, checks generated-text sanity, or hands LLM evidence to the separate registry dashboard.
---

# Android LLM benchmark

Use the repository's fixed generic inference workload and preserve comparable performance evidence. The first LLM phase is not a podcast-transcript quality evaluation.

## Read the contract first

Read completely:

- `protocols/android-llm-benchmark/README.md`
- `protocols/android-llm-benchmark/contract.json`
- `protocols/android-llm-benchmark/workloads/inference-v1/SHA256SUMS`

Verify the workload from its directory:

```bash
cd protocols/android-llm-benchmark/workloads/inference-v1
sha256sum -c SHA256SUMS
```

Use the exact `short.json`, `medium.json`, and `long.json` bytes. Do not normalize messages, add a private prefix, silently truncate, reduce the output ceiling, or substitute a different prompt.

## Spend strictness only where it protects evidence

The goal is credible Android measurements, not perfect instrumentation. Build time, model downloads, and phone campaigns cost real time and money. Use the cheapest check that protects the claim being made, and do not turn optional runtime behavior into a new publication gate.

Before making any condition fatal:

1. point to the protocol, a safety/authorization boundary, or the specific claim it protects;
2. confirm that violating it invalidates the logical request or claim, rather than only one optional metric;
3. ask whether retaining the raw observation plus `null` and a reason is more accurate;
4. distinguish protocol-level requests from runtime-internal callbacks, chunks, turns, counters, or implementation details.

Do not assume optional telemetry exists, increments, or has an exact count. A successful logical request remains evidence when an internal timing counter is absent. Persist raw output, callback state, timestamps, and errors before optional metric extraction or validation so post-processing cannot discard an expensive run.

Use fatal gates for actual validity and safety failures, such as wrong workload or artifact identity, unauthorized device access, silent truncation, a requested configuration not being applied, or evidence that cannot be bound to the claimed route. Treat unavailable timing splits, unsupported counters, warnings, and nonessential metadata as nullable limitations unless the contract explicitly says otherwise.

“Fail closed” means do not publish an unsupported claim. It does not mean crash, delete captured evidence, or reject valid inference because auxiliary instrumentation is imperfect. Add a new fatal implementation invariant only when its protocol justification is documented and a regression test proves it rejects invalid evidence rather than valid runtime variation.

## Pin the complete route

Before performance work, record:

- model name, canonical source URL, exact revision, parameter count when authoritative;
- every model artifact path, SHA-256, byte size, format, and shard relationship;
- quantization name, bit width, group/block scheme, calibration status, source, conversion tool, and tool revision;
- tokenizer name, source, revision, files, and hashes;
- model-native chat-template source and exact bytes or SHA-256;
- rendered prompt SHA-256, effective input-token count, and token-ID SHA-256 for every tier;
- model context limit and proof that prompt tokens plus `max_new_tokens=2048` fit without truncation;
- runtime, build/revision, provider/backend, threads, libraries, and relevant options;
- Android device identity, build, ABI, charging/screen state, and authorization boundary.

Different tokenizers produce different token counts. Never force one model's tokenizer onto another family. Report tokens per second with tokenizer identity and actual numerator/denominator.

## Gate before the phone

Use the smallest bounded host or local smoke needed to prove that artifacts load, prompts render, context fits, and one output is obtainable. A host smoke is not Android performance evidence and must not populate Android timing or memory fields. Do not demand publication-complete telemetry from this viability smoke; record warnings and instrumentation gaps for the Android contract instead of repeatedly rerunning a successful load/generation path.

Follow repository device locks and approval rules. Do not access a personal phone, accept terms, install proprietary software, or use restricted SDK material without explicit authorization.

## Measure setup once

Start setup timing immediately before the first model/tokenizer file access or runtime creation, whichever happens first. Stop only when the route can accept a canonical request without further:

- model or tokenizer loading/mapping;
- runtime/provider/session creation;
- runtime accelerator compilation;
- initial KV allocation required for readiness.

Record the exact boundary and any internal phases the route exposes. Keep offline conversion or compilation outside setup only when it is independently recorded as preparation and the deployed route truly loads the resulting artifact.

## Run the canonical campaign

With one loaded model/runtime route (and one Engine when the runtime exposes one):

1. run one first complete request with the short tier;
2. run at least five additional loaded-route requests for short;
3. run at least five loaded-route requests for medium;
4. run at least five loaded-route requests for long;
5. isolate conversation and KV state before every logical request;
6. keep the canonical tier order and greedy generation settings;
7. retain every raw UTF-8 output, including partial timeout/error output;
8. record actual output tokens and the exact stop reason for every request.

Runtime object identity is not a validity goal. Use either a proven full in-session conversation/KV reset or a fresh Session per logical request, and record the strategy. For fresh Sessions, measure creation/reset separately on every request and state whether it is included in total-request timing. Keep the model/runtime route loaded: do not remap or reload the model, recompile the accelerator route, or retain prompt-prefix/KV state between logical requests.

The 2,048-token value is a ceiling, not a target. Do not pad, demand a word count, or relabel the ceiling as actual output. Do not require byte-identical output; preserve any variation.

The canonical request timeout is 1,800 seconds. A timeout or error is evidence, not disposable work: retain partial output and observations, record the exact stop reason, and use null plus explicit reasons for events that never occurred. Do not relabel that request as complete or publish metrics it did not produce.

## Record timings precisely

For every request record raw timestamps/durations and derived rates:

- request-to-first-token: before prompt rendering/tokenization through first generated token ID delivered to the caller;
- prefill: effective prompt-token submission through final prompt-token KV readiness;
- post-prefill-to-first-token: prefill completion through first generated token delivery;
- decode: first generated-token delivery through final generated-token delivery;
- total request: request start through final output/stop delivery;
- request-state reset or fresh-Session creation: separately measured, with an explicit statement of whether it is included in total request;
- prefill input tokens/s with input-token numerator and prefill-seconds denominator;
- decode output tokens/s with its exact generated-token numerator and decode-seconds denominator.

State whether the first generated token is included in the runtime's decode-rate definition. If the runtime cannot expose a split, keep that field null with a reason instead of deriving it from an unrelated callback.

Keep the first request separate from loaded-route warm distributions. Do not pool short, medium, and long tiers or compare distributions collected with different repetition contracts as matched.

## Measure memory and operating conditions

Record memory values with units, collection method, sampling interval, and lifecycle:

- peak sampled PSS when available;
- process VmHWM/ru_maxrss when available;
- mapped model/package bytes separately from runtime memory;
- backend/accelerator memory only when directly measured.

Sampled PSS can miss brief peaks. VmHWM is a cumulative process high-water mark and is not isolated model or KV memory. Do not substitute one field for another without labeling it.

For physical phone campaigns record thermal/battery state before and after, charging state, and power evidence when available. Missing values stay null with reasons; null never means zero.

## Apply only the narrow sanity check

Every raw output has a separate required SHA-256. Sanity contains exactly:

```json
"output_sanity": {
  "looks_sensible": true,
  "issue_notes": null
}
```

Valid combinations are:

- `true` and `null`;
- `false` and a nonempty description of the obvious failure;
- `null` and `null` when unchecked.

Use `false` for obvious corruption such as empty/binary-like output, token-ID leakage, gibberish, or severe repetition collapse, then describe it briefly. Do not write notes for a sensible-looking output.

This check is not quality, correctness, grounding, transcript usefulness, style, or acceptance. Do not add a quality score or infer a model-family verdict.

## Finish and publish evidence

Keep raw per-run evidence, outputs, hashes, commands, blockers, and limitations in the owning numbered experiment. Use tests to verify workload hashes, rate calculations, sanity combinations, output hashes, null reasons, and protocol-level campaign counts. Tests should preserve successful requests with missing optional telemetry; do not enforce exact counts for runtime-internal callbacks, chunks, or benchmark turns unless the runtime documents that contract and the published metric depends on it.

After the experiment evidence is committed:

1. add or refresh normalized rows in `docs/android-llm-benchmarks/registry.json`;
2. run `python3 docs/android-llm-benchmarks/validate.py`;
3. run `python3 docs/android-llm-benchmarks/build_registry.py`;
4. run validation again and inspect generated changes;
5. report the experiment commit, route IDs, workload hashes, metrics, output paths/hashes, sanity states, and limitations.

Never put LLM rows in the TTS registry or reuse WAV, RTF, or listening-review fields.

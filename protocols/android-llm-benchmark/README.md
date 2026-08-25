# Android LLM benchmark contract

This directory defines the canonical fixed-input and minimum-evidence contract for comparable Android LLM inference benchmarks in this repository.

The first protocol measures execution and performance. It does **not** evaluate podcast transcript quality, correctness, grounding, style, or acceptance.

## Canonical workload

Use the exact JSON bytes under `workloads/inference-v1/`:

- `short.json`
- `medium.json`
- `long.json`

Verify them with:

```bash
cd protocols/android-llm-benchmark/workloads/inference-v1
sha256sum -c SHA256SUMS
```

The files freeze message roles/content and generation settings. Do not rewrite punctuation, normalize whitespace, add a hidden prefix, silently truncate a prompt, or substitute a different system message.

The canonical messages are model-independent. Every route must separately record:

- the exact tokenizer name, source, and revision;
- the model-native chat-template bytes or an exact hash plus source;
- the rendered prompt SHA-256;
- the effective input-token count and token-ID SHA-256;
- the model context limit and confirmation that input plus the configured output ceiling fits.

Token counts differ across tokenizers. The fixed comparison unit is the exact workload bytes; tokens per second remains a route measurement with explicit tokenizer provenance.

## Output ceiling

Every inference-v1 tier sets `max_new_tokens` to `2048`. This is a safety ceiling, not a requested word count, transcript duration, or required output length.

Record for every request:

- actual generated-token count;
- stop reason: `eos`, `stop_sequence`, `max_tokens`, `timeout`, or `error`;
- complete raw UTF-8 output bytes and SHA-256.

Never pad output to the ceiling or report the ceiling as the generated-token count.

## Campaign shape

Create the model/runtime route once and report setup separately. Setup begins immediately before the first model/tokenizer file access or runtime creation, whichever occurs first. It ends only when the route can accept the canonical request without additional model loading, runtime/session creation, accelerator compilation, or initial KV allocation.

Then run:

1. one first complete request using the short tier;
2. at least five additional same-session requests for each of the short, medium, and long tiers;
3. a full conversation and KV-cache reset before every request;
4. the same loaded model/runtime session for the warm campaign;
5. the fixed tier order and exact generation settings from `contract.json`.

Retain all raw outputs. Greedy inference should normally be reproducible, but byte identity is not a pass gate; disclose any output variation rather than discarding it.

The canonical per-request timeout is 1,800 seconds. A timeout is evidence: retain partial output when available, set the stop reason to `timeout`, and keep unavailable downstream metrics null with reasons.

## Timing definitions

- **Request-to-first-token:** from immediately before workload rendering/tokenization to delivery of the first generated token ID to the benchmark caller.
- **Prefill:** from submission of the effective prompt tokens to the model until the final prompt token's KV state is ready.
- **Post-prefill-to-first-token:** from prefill completion to delivery of the first generated token ID.
- **Decode:** from first generated-token delivery through final generated-token delivery. Decode throughput counts tokens after the first over that interval; if the runtime exposes only an authoritative equivalent, record its definition.
- **Total request:** from the same request start through final output/stop delivery.

Report request-to-first-token even when the runtime cannot split prefill from first-token sampling. In that case keep prefill and post-prefill fields null with explicit reasons; never invent the split.

## Memory and operating context

Record peak memory with the measurement method, sampling interval, and lifecycle boundary. At minimum retain peak sampled PSS when available and process VmHWM/ru_maxrss when available. These are distinct measurements; a cumulative process high-water mark is not isolated model memory, and sampled PSS can miss short peaks.

For physical-phone runs, record device identity, Android build, battery/thermal state before and after the campaign, and power evidence when available. Missing power or thermal fields remain null with reasons.

## Output sanity

Output sanity has exactly two fields:

```json
{
  "looks_sensible": true,
  "issue_notes": null
}
```

Only these combinations are valid:

- `true` / `null`: the exact output looks like sensible natural-language text;
- `false` / nonempty string: the output is obviously broken, with a brief description;
- `null` / `null`: nobody checked it.

This is a superficial corruption/gibberish smoke check. It is not quality, correctness, grounding, usefulness, or human acceptance. The raw output SHA-256 is required separately and binds the observation to exact bytes.

## Evidence publication

Commit the owning experiment evidence first. Then add normalized rows to `docs/android-llm-benchmarks/` and regenerate its dashboard. Use null plus an explicit reason for genuinely unavailable fields. Do not infer Android measurements from a host smoke, and do not copy TTS RTF/WAV/listening semantics into LLM rows.

The machine-readable minimum is in [`contract.json`](contract.json). The operational workflow is in [`.agents/skills/android-llm-benchmark/SKILL.md`](../../.agents/skills/android-llm-benchmark/SKILL.md).

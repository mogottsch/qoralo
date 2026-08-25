# Android LLM benchmark registry

This directory is the durable cross-experiment index for generic Android LLM inference routes. It is separate from `docs/android-benchmarks/` because LLM setup, TTFT, prefill/decode throughput, text output, and memory evidence are not comparable to TTS transcript/WAV/RTF/listening fields.

- [`index.html`](index.html) — generated static dashboard.
- [`registry.json`](registry.json) — normalized committed route evidence.
- [`schema.json`](schema.json) — machine-readable registry contract.
- [`validate.py`](validate.py) — fail-closed schema, workload, source, output-hash, sanity, and campaign validation.
- [`build_registry.py`](build_registry.py) — deterministic dashboard generator.

The registry intentionally starts empty. Do not add placeholder models or measurements. The owning numbered experiment remains the source of truth; this registry only normalizes committed evidence.

## Regenerate and validate

From the repository root:

```bash
python3 docs/android-llm-benchmarks/validate.py
python3 docs/android-llm-benchmarks/build_registry.py
python3 docs/android-llm-benchmarks/validate.py
```

## Evidence boundaries

A route row separates:

- technical execution;
- exact workload and route provenance;
- setup and per-request performance;
- memory and operating context;
- raw text output hashes;
- the narrow `looks_sensible` corruption/gibberish smoke check.

Output sanity is not quality, correctness, grounding, usefulness, or acceptance. Actual transcript-quality work belongs to a later protocol and must not be inferred from these rows.

Host smokes remain experiment-local intermediate evidence and never become rows in this Android registry. Missing values remain null with explicit reasons.

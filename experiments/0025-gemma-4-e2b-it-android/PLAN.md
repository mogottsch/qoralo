# Plan — Gemma 4 E2B IT Android CPU/GPU

## Question

How do the two official LiteRT-LM Android deployment artifacts execute and perform on the authorized Galaxy S23 Ultra under the canonical LLM benchmark?

## Gates

1. **Complete:** pin public ungated Apache-2.0 base/deployment revisions, artifacts, tokenizer/templates, quantization description, LiteRT-LM source/runtime, runner, Android libraries, NDK, and workload hashes.
2. **Complete:** load the exact CPU artifact locally and generate one bounded canonical-short output. Keep all host observations out of the Android registry.
3. **Next:** acquire the phone lock; verify exact serial/model/SoC/ABI/boot state and available storage; stage only under `/data/local/tmp/vibevoice-0025-gemma-4-e2b-it-android`; verify every remote hash.
4. Run one bounded canonical-short CPU smoke and persist/pull its raw evidence before optional telemetry processing. Report the first Android result.
5. Run the equivalent GPU smoke using the distinct official GPU artifact and the same runner/workload/sampler contract.
6. Run the full CPU campaign: one first short request, then five same-session requests for short, medium, and long with verified rewind to step zero before every request.
7. Run the matched GPU campaign under the same logical request contract.
8. Pull and hash all raw outputs/results, record exact thermal/memory/runtime limitations, and delete only the exact experiment-owned remote root.
9. Commit owning experiment evidence. Only afterward update and commit the Android-only LLM registry in a separate change.

## Stop conditions

Stop and ask before accepting new terms, accounts/logins, proprietary SDK agreements, privilege changes, purchases, or destructive device operations. Stop a route claim on wrong identity, truncation, backend/sampler mismatch, failed KV reset, or unbound raw output. Preserve partial/error evidence. Optional BenchmarkInfo or power telemetry may remain null with explicit reasons.

# Plan — Gemma 4 E2B IT Android CPU/GPU

## Question

How do the two official LiteRT-LM Android deployment artifacts execute and perform on the authorized Galaxy S23 Ultra under the canonical LLM benchmark?

## Gates

1. **Complete:** pin public ungated Apache-2.0 base/deployment revisions, artifacts, tokenizer/templates, quantization description, LiteRT-LM source/runtime, runner, Android libraries, NDK, and workload hashes.
2. **Complete:** load the exact CPU artifact locally and generate one bounded canonical-short output. Keep all host observations out of the Android registry.
3. **Complete for CPU and the bounded GPU attempt:** acquire the phone lock; verify exact serial/model/SoC/ABI/boot state and available storage; stage only under `/data/local/tmp/vibevoice-0025-gemma-4-e2b-it-android`; verify every remote hash.
4. **Complete:** run one bounded canonical-short CPU smoke and persist/pull its raw evidence before optional telemetry processing. Report the first Android result.
5. **Complete viability milestone:** after a transport-only preflight blocker, the approved generic 2,588,147,712-byte artifact completed a bounded GPU smoke with GPU-only/no-fallback configuration, mapped provider/driver libraries, and `/dev/kgsl-3d0` proof. This smoke is not experiment completion.
6. **Complete:** run the full CPU campaign: one first short request, then five loaded-Engine requests for short, medium, and long, creating a fresh Session before every logical request after the first. Record Session creation separately and exclude it from request timing; do not remap/reload the model or repeat accelerator compilation.
7. **Complete:** after preserving a non-counted missing-cache setup diagnostic, run the matched GPU campaign entirely fresh under the loaded-Engine/fresh-Session contract; all 16 requests completed.
8. **Complete:** pull and hash all raw outputs/results, record exact thermal/memory/runtime limitations, and delete only the exact experiment-owned remote root.
9. Commit owning experiment evidence. Publication/registry work remains separately owned and out of this assignment.

## Stop conditions

Stop and ask before accepting new terms, accounts/logins, proprietary SDK agreements, privilege changes, purchases, or destructive device operations. Stop a route claim on wrong identity, truncation, backend/sampler mismatch, failed KV reset, or unbound raw output. Preserve partial/error evidence. Optional BenchmarkInfo or power telemetry may remain null with explicit reasons.

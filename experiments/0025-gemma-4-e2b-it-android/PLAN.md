# Plan — Gemma 4 E2B IT Android CPU/GPU

## Question

How do the two official LiteRT-LM Android deployment artifacts execute and perform on the authorized Galaxy S23 Ultra under the canonical LLM benchmark?

## Gates

1. **Complete:** pin public ungated Apache-2.0 base/deployment revisions, artifacts, tokenizer/templates, quantization description, LiteRT-LM source/runtime, runner, Android libraries, NDK, and workload hashes.
2. **Complete:** load the exact CPU artifact locally and generate one bounded canonical-short output. Keep all host observations out of the Android registry.
3. **Complete for CPU and the bounded GPU attempt:** acquire the phone lock; verify exact serial/model/SoC/ABI/boot state and available storage; stage only under `/data/local/tmp/vibevoice-0025-gemma-4-e2b-it-android`; verify every remote hash.
4. **Complete:** run one bounded canonical-short CPU smoke and persist/pull its raw evidence before optional telemetry processing. Report the first Android result.
5. **Amended route approved; transport blocked before identity:** the dedicated artifact attempt remains blocked/non-metric under `results/android-gpu-blocker/`. Moritz approved the generic 2,588,147,712-byte artifact with `Backend::GPU`, but its first smoke preflight found the authorized serial absent from the ADB bridge. Once restored, rerun entirely fresh and require authoritative post-compilation GPU provider binding with no CPU fallback.
6. **Complete:** run the full CPU campaign: one first short request, then five loaded-Engine requests for short, medium, and long, creating a fresh Session before every logical request after the first. Record Session creation separately and exclude it from request timing; do not remap/reload the model or repeat accelerator compilation.
7. **Pending provider-bound smoke:** if the amended generic-artifact GPU route binds successfully, run the matched GPU campaign under the loaded-Engine/fresh-Session contract.
8. Pull and hash all raw outputs/results, record exact thermal/memory/runtime limitations, and delete only the exact experiment-owned remote root.
9. Commit owning experiment evidence. Only afterward update and commit the Android-only LLM registry in a separate change.

## Stop conditions

Stop and ask before accepting new terms, accounts/logins, proprietary SDK agreements, privilege changes, purchases, or destructive device operations. Stop a route claim on wrong identity, truncation, backend/sampler mismatch, failed KV reset, or unbound raw output. Preserve partial/error evidence. Optional BenchmarkInfo or power telemetry may remain null with explicit reasons.

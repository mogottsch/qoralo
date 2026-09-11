# AR171 query-prescale: saved CPU numerical evidence

This is one canonical-short171-token, zero-initial-state CPU case, not HTP, AR1/nonzero-state, speed or quality-equivalence evidence. No further execution is authorized by the result.

## Outcome

- Unchanged baseline reused from `query-prescale-20260911T093452Z-73227` after exact graph/data/input/runtime/options/output binding; it was not rerun.
- One derivative call and one debug-baseline call in `query-prescale-20260911T094138Z-78096` completed on CPU only.
- All38 state outputs and22 logit chunks (1,664,000 FP32 values) are finite and bit-for-bit identical. Maximum/mean absolute deltas are zero, argmax597 and all128000 vocabulary ranks are unchanged.
- All60 original debug-baseline outputs matched the unchanged baseline bit-for-bit before using the16 captured query/key operand arrays.
- FLOAT16-boundary proxies with FLOAT32 accumulation differ in8 full-score elements,5 causal/unmasked elements. Maximum absolute delta0.001953125. Query scaling rounds one additional nonzero value to zero in each of layers9/17; no finite-to-infinity overflow in the measured casts. The21888 query and21888 tiled-key ingress zeros in layer2 are shared by both proxies, not relocation-induced.

## Review without execution

- `result.json` is the exact saved worker report, SHA-256 `dcb851892064154930d4de48472b15811353e341f8602deebc80a450b4fa192f`.
- `summary.json` provides a post-run summary and per-site table, not a rerun or substitute for the raw report.
- `raw/prepared.json`: exact original/copy/derivative/debug/source/criteria/input identities and baseline-reuse bindings.
- `raw/{baseline,derivative,debug,inputs}-manifest.json`: every retained array's name, dtype, shape, size and SHA-256.
- `raw/fp16-proxy-00-manifest.json` through `07`: both saved score arrays per site. All arrays and model artifacts remain under the ignored `.local/query-prescale-*` roots.
- `raw/instrumentation-comparison.json`, `raw/all60-comparison.json`, `raw/logit-rankings.json`, `raw/fp16-proxy-*.json`: complete numerical observations, including nonfinite, subnormal, underflow and overflow counts.
- `raw/immutable-after.json`: unchanged-source/copy/input/reused-evidence hashes checked after execution.
- `raw/launcher.command`, `raw/commands.json`, runtime metadata, empty per-worker stderr files and exit records bind execution and options. There is no baseline command in the continuation.
- Source: `../../tools/prescale_ar171_queries.py` replaces exactly eight score-Mul pairs with query-Mul→score-MatMul, preserving initializer/interface bytes; `../../tools/verify_query_prescale_cpu.py` contains the frozen comparison and byte-level signed-zero-aware instrumentation gate.
- Criteria: `../../protocol/query-prescale-numerical-check.json` and storage-only `query-prescale-storage-amendment.json`. The derivative protobuf remains SHA `b93c65c9c419f915bad81046f34c91c632ce6dd1bed4137751f36204d64492a0` across attempts.

Review can inspect source/ONNX protobuf metadata and stream or mmap saved arrays; do not invoke the verifier CLI, load a model session or rerun proxies just to review this package. `SHA256SUMS` covers the small public package only, not the large private arrays, which have their own manifests.

## Boundaries

ORT1.26 CPU, optimizations disabled, sequential execution, intra-op2/inter-op1; OpenMP/BLAS2, nice10, cgroup CPU200%, MemoryMax12GiB and SwapMax0. Each worker had300s and the continuation1180s total (prior18.193s keeps the campaign below1200s). External-data copies are independent regular files with original-before/copy/original-after hash identity. The original failed attempt remains unchanged, without a comparison claim.

The console reports63.044s whole service lifecycle and rounded5G peak cgroup memory, no swap. Exact successful-unit peak bytes are unavailable: the transient unit unloaded before post-exit `systemctl show`. Its default `infinity`/`[not set]` values are not the in-run limits, which are recorded by worker cgroup checks. No performance rate is derived from these lifecycle/resource observations.

FLOAT16 probes round inputs and operation boundaries but accumulate in FLOAT32 NumPy/BLAS. They are not actual HTP fusion, accumulator, rounding or flush-to-zero behavior, and not a full-model FP16 rollout. Full-score metrics include masked cache/future entries; causal metrics are separate. Normal/subnormal and nonzero-to-zero counts are retained even when the final FP32 model outputs agree. These observations require saved numerical review before any separately authorized AOT or device work.

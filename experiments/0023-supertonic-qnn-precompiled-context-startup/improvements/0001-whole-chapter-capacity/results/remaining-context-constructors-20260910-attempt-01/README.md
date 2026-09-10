# Remaining constructor batch — text/vector passed; vocoder failed; stopped

The exact released batch ran **serially: text → vector → vocoder**, one constructor attempt each, **zero Session.Run calls**, no retry. Text and vector produced external contexts with the required I/O. Vocoder failed during QNN graph finalization; the batch stopped. The earlier successful duration context remains unchanged. **Only3/4 larger contexts exist; the whole-long-speech gate is not ready.**

## First outcomes

| Component | Constructor seconds | Worker body seconds | Outer launcher seconds | Process peak `ru_maxrss` KiB | Result |
|---|---:|---:|---:|---:|---|
| Text |61.418342|62.250355|63.952840|1,609,424|I/O/external-context gates passed|
| Vector |178.700869|180.640297|182.876520|5,698,004|I/O/external-context gates passed|
| Vocoder |null: constructor threw|2.096723|3.502388|491,056|QNN finalization failed, code1002|

These are constructor/compiler timings, not neural inference or physical-phone measurements. The sum of outer component timings is250.331748s, not a continuous batch-wall measurement. Memory is the Python worker's own process peak, not whole-container memory; guard `/proc` samples describe the Docker CLI.

Text and vector actual-session I/O exactly matched their requested ordered names/types/shapes. Their descriptor gates passed: one `com.microsoft::EPContext`, no initializers, exact I/O and external `embed_mode=0` binary reference. CPU fallback was disabled; registered CPU provider presence is not execution. Their source/runtime pins were reverified unchanged after construction, and post-close artifact hashes matched.

**Vocoder has no actual-session I/O receipt, descriptor or binary.** Its exception path did not perform post-constructor source/runtime pin verification. Missing observations remain null with reasons in `result.json`; they are not retrofilled from request metadata or later inspection. The raw retention helper's false post-close-hash flag means no artifact comparison was possible, not an observed hash mismatch.

## Protected artifacts — LOCAL-ONLY

| Component/artifact | Bytes | SHA256 |
|---|---:|---|
| Text descriptor |821|`389f5754e60bb3bbf3bd8b7f833d9112f6ea17d78cbe67de013dc56b0ba8cca8`|
| Text context |37,119,616|`45c9a1672ec4521947bc273565331a0cd54aa99050b1969e2ee15fa175de3bc5`|
| Vector descriptor |1,023|`b2938bfe41a8b111ef0a01d74ef737ea930040bf0b51cc8a2dbb2760206f9b1a`|
| Vector context |185,153,584|`d40e5bf8ad96bad04e96f5a4ec27e979b410320b9d000cf2b109f5d92ad6c00f`|

Actual files and any partial outputs remain under `.local/constructor-{text,vector,vocoder}-t2048-l2048-attempt-01/`, each with `PRESERVE.md`. Per-component `local-artifacts.json` records exact paths. Vocoder's artifact list is empty. Preserve actual bytes, not only hashes; no context/model/SDK binaries are Git content.

## Vocoder error class, not root cause

`vocoder/raw/guard/stderr.log:2` reports:

```text
Failed to finalize QNN graph. Error code: 1002
```

`stdout.log` ends after `Completed stage: Graph Optimizations (1395299 us)`. The retained SDK2.49.0 header passages map the code:

- `QnnCommon.h:71`: `#define QNN_MIN_ERROR_COMMON 1000` (spacing preserved in the citation JSON).
- `QnnCommon.h:195–196`: “Memory allocation related error.” / `QNN_COMMON_ERROR_MEM_ALLOC = QNN_MIN_ERROR_COMMON + 2,`
- `QnnGraph.h:44–45`: “General error relating to memory allocation in processing graph API” / `QNN_GRAPH_ERROR_MEM_ALLOC = QNN_COMMON_ERROR_MEM_ALLOC,`

See `vocoder/error-class-citations.json` for exact lines, installed-header identities and raw log passage. Nik independently identified this mapping; Ben retained the bounded saved-log/source citations. Header identities were measured during post-run read-only inspection, not retroactive runtime pin verification. Full proprietary SDK headers were not copied.

This is QNN's reported **memory/resource-allocation error class**. It does **not** prove host RAM or the8GiB cgroup limit was exhausted, identify an operator/tensor, allocation size or internal allocator root cause. No shape change, runtime experiment or retry was performed to explain it. Nik owns the primary root-cause review.

## Boundaries, raw retention and cleanup

Exact batch `4943e159268df867b58adcde0e386a65fe6b0c16b2c29b5f1c4136a82aaf6cde`; worker/launcher and each request/release are copied here. The prior `e4066aa` readiness/source remains frozen. Runtime: ORT1.27.1 / QAIRT2.49.0.260730 / SoC43, same pinned image/options, no CPU fallback. Each component used a fresh container/output/release,520s guard +20s grace/≤600s overall,8GiB/no-extra-swap,4CPU/math environment, network off and four owned disk-scratch variables.

Full raw logs, first outcomes and failure tracebacks were copied before additional saved-result classification. The optional file-mapped-weights warning is retained. Successful compiler DDR summaries are estimates, not physical bandwidth measurements.

PIDs1919623(text),1920253(vector),1922416(vocoder) were reaped; PIDs/groups and containers absent; scratch empty. No forced extra container removal was needed after `--rm`. Name/ownership-label cleanup is non-atomic; no immutable-ID hardening is claimed.

All three releases are consumed. No context reload, forward, duration redo, phone access, pack replacement or push. Constructor compatibility is not execution, fidelity or listening acceptance, and the app's existing canonical T239/L238 WAV remains a separate immutable result.

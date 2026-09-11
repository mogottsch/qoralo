# Full AR1/AR128 post-projection precision island

**Both full DLC conversions and their internal precision gates passed.** Paired-context compilation/inspection and physical validation are separate stages; this result does not claim either.

| Graph | New DLC bytes | SHA-256 | Guard wall time | Ops: prior → new |
|---|---:|---|---:|---:|
| AR128 | 2,356,879,332 | `d9eec6585153928e2f9f2351854849abc458de42d5426788bd22b760d2633052` | 645.22 s | 6842 → 6893 |
| AR1 | 2,356,873,908 | `34402f2990053a879cd67781ba327076ab80a4f64620aca019a029cc3beb858b` | 671.01 s | 6875 → 6935 |

These are host preparation observations, not inference throughput or speed acceptance. Binary models stay private.

## Verified precision path

For **each complete graph**, saved official DLC metadata establishes:

- three selected value-normalization/cache-export paths remain floating after the unchanged quantized V-projection boundary;
- three cache Concats are Float16, with no value-read requantization before their MatMul consumers;
- **56 value MatMuls** (8/8/40 consumers of layers 4/9/14) have Float16 probability/value operands and Float16 output;
- each original quantized probability tensor/signature/grid is retained, with a Convert into the coupled Float16 operand;
- **seven Float16 head-reassembly Concats** collect these outputs, then convert back to the original fixed-point grids before unchanged quantized output-projection signatures;
- active external IO signatures are unchanged.

The required floating head reassembly is explicitly included. This is not a cache-only numerical intervention: normalization, cache representation, value MatMul arithmetic and its coupled reassembly are within scope. Upstream projection weights and probability computation are not silently made floating point.

The original FP16-candidate ONNX graph bytes and parameter encodings were reused. Only the declared activation entries changed: 71 in AR1 and 74 in AR128. Source input and output artifact hashes are retained in the conversion receipts.

## Interface annotation caveat

Explicit FLOAT16 encodings make six selected IO annotations per AR print zero scale/offset placeholders instead of “No encoding info”. These are **inactive quantization metadata on Float16 tensors**, not integer grids or proof of zero-valued tensors. Raw annotations are preserved. The gate ignores only that annotation difference for the selected Float16 caches; shapes, datatypes and all active integer encoding signatures remain checked.

The full core gate, downstream exit gate and actual global/SWA cache names are independently checked. The paired compiler contract accounts for all 30 caches: six global `past_*` outputs and 24 `swa_*` outputs, not only the three selected value caches.

## Resource and evidence boundaries

Conversions were sequential, after other agents released their heavy-host reservations. Both used existing host swap only, low priority and fresh disk-backed storage:

- MemoryHigh 15 GiB / MemoryMax 17 GiB / MemorySwapMax 16 GiB;
- two CPU quota, nice 15; 1800-second outer deadline;
- fresh capacity checks leaving at least 4 GiB available RAM and 8 GiB free swap outside the requested envelope;
- 64 GiB owned allocation cap, disk-free and sustained-pressure stops, scoped child reaping and systemd cgroup cleanup.

Both guards recorded actual child exit 0, no stop reason and no OOM. `resources.jsonl.gz` and the result retain cgroup memory/swap observations. Per-process RSS and cgroup charges are not interchangeable: shared existing file mappings can appear in RSS while being charged outside a later inspection cgroup.

The AR128 bare DLC-info exit code was not independently retained before transient-unit garbage collection; complete fresh CSV and the exact operator/interface checks establish its metadata observations. The AR1 inspection wrapper records its actual child exit 0. Default `systemctl show` success/zero fields on a garbage-collected unit are not used as independent exit evidence. No inspection was repeated merely to fill optional process telemetry.

Raw conversion receipts deliberately retain their original “metadata gate pending” state at conversion return. The later combined precision-validation files and this result establish the completed DLC gates; earlier records are not overwritten.

## Limits

- No complete new context or physical query is claimed here.
- DLC tensor precision is not a map of finalized kernel arithmetic or accumulator precision.
- No numerical-state equality, generated-text improvement, latency, throughput or repetition cause is established.
- FP16 rounding can differ; it is not automatically more accurate than every existing fixed-point grid.
- The prior exact-long negative, canonical campaign, frozen stages and private original evidence remain unchanged.
- This QNN investigation does not diagnose the app’s LiteRT GPU failure.
- No app changes, Nik review, new agents, registry update or push occurred.

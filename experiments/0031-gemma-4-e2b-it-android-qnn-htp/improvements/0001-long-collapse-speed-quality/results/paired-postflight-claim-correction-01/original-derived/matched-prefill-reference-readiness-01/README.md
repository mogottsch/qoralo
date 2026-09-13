# Paired-prefill readiness: captured inputs, independent caches

**The phone observer and host declared-policy reference are prepared and frozen. No phone or full-model execution occurred in this preparation.** A new Pi-granted paired checkpoint can now be scheduled around Janek's playback work, subject to fresh full APK identities and actual user-job quiescence.

This is a reference for the **declared final DLC quantization/precision policy**, not bit-exact emulation of proprietary DSP rounding, fusion, accumulation or transcendental kernels. Unknown historical exporter provenance is not being used as an indefinite blocker.

## One actual final policy

The chosen variant is the existing true-precision-island AR128 DLC used by the source-built selected-ID diagnostic:

- DLC: `d9eec6585153928e2f9f2351854849abc458de42d5426788bd22b760d2633052`
- Compiled context: `27e19e32ef479dfb39b53e6530cd25105c3c8e9ccf9fa4b9e9af4b5d770fabdd`
- Extracted private policy: `7fffebe9208bc5e2b92d80ed6ed01b7b57263e8f23d188188588682754c18b59`

The extraction reads the actual DLC IR: **6,893 operations, 8,317 tensors, 38 inputs, 31 outputs**, every scalar/axis grid and operation attribute, and **1,386 actual static-code blobs totaling 2,284,909,786 bytes**. It does not substitute the original encoding sidecar or plain float ONNX. All 56 coupled FP16 value MatMuls remain represented, with their quantized-probability boundaries, head concatenations and return grids.

All 15 operation families and every concrete shape/topological contract pass the non-executing reference preflight. Existing pinned NumPy 1.26.4 / SciPy 1.15.3 are reused without global environment changes or new dependencies.

The reference evaluates logical operators in F32, then applies each actual output grid or explicit binary16 boundary. Integer output rounding is explicitly nearest-ties-to-even with clipping. Memory operations preserve encoded bytes when policy is unchanged. QNN's declared GELU uses the documented `erf` formula; no tanh approximation is silently substituted. Actual BW4 static weights arrive in int8 containers with low-nibble codes, so decoding sign-extends **the effective signed four-bit width**, not the eight-bit container sign.

These choices make the numerical reference usable and auditable. They do not establish the DSP's hidden arithmetic choices or imply that any future difference is automatically a backend defect.

## Static active-weight mapping completed

The source float ONNX's **764 reachable initializers** are fully accounted for:

- **758 mapped tensors / 2,279,751,714 values**, all equal to the explicit native F32 dequantization/cast/per-head/transpose mapping.
- Six inline structural constants, separately identified.
- Zero missing mappings or mismatching values, including norms, layer scalars, the transposed PLE model projection and full output head.

The original data file SHA is `e156c33d176273555003039959ecb0ae0ddc8a328eceeec1e8f4a6255840e072`. This closes the active-weight mapping gate, not the native BF16/SRQ8 execution-equivalence question. The earlier native argmax 8291 remains a descriptive control, not a defect locator.

## Exact history and independent cache evolution

The prepared ledger binds the frozen **1,929 IDs** to **16 AR128 chunks**: 15 full chunks and a final chunk with nine real rows. Inputs are right-padded; **row 8** is the actual final valid logit row. All 16 step records and SWA gather mappings agree with the retained physical trace.

The ledger preserves:

- Main LUT and raw token-identity PLE, including source-defined UINT8→UINT16 requantization and integer-offset truncation. PLE remains `[1,128,35,256]`; projection/normalization/blending stay inside the graph.
- Global cache slots at the physical append indices and SWA's 512-slot ring, with matching key/value pairs.
- Actual mask codes 0 / 65535 (declared −50 / 0), a 512-token SWA span including the current token, and fully blocked padded rows.
- Both RoPE families, zero padded positions, and the observed cosine-grid quantizer used for **both** sine and cosine. SWA sine's declared offset is −32767 while its host quantizer uses cosine's −32768; this behavior is preserved, not opportunistically corrected.
- Source-defined cache clear word `0x8000`. For the three FP16 global-value inputs that bit pattern is negative zero.
- Thirty explicit cache contracts. The future host runner copies **its own returned cache rows** into the next chunk. It never resets between chunks and never accepts HTP-produced caches.

Host-libm formulas alone do **not** establish identical external input bytes. The executable paired path therefore rejects the source-only ledger until actual captures have been bound.

## Frozen observation-only phone capture

A derivative of the bound source-built Genie adds only two read-only observation sites:

1. After all `setupInput` preparation, save the **eight non-cache input tensors** for each AR128 step.
2. In `getLogits`, after selecting the final valid row but **before Tensor/sampler access**, save all **262,144 raw UINT16 logits**, with dtype, scale/offset and row metadata.

No model-call, sampler, weight, mask, PLE or cache mutation was added. The source patch is invertible to the frozen original. The observer writes flushed begin/complete records and exclusive-create raw files, with CLOEXEC/no-follow descriptors. Failures disable observation and are reported; they do not change native computation or trigger replay.

Capture bounds: **129 payloads, 80 MiB total, 3 MiB per payload, 512 KiB journal**. The expected raw payload is 66,060,288 bytes. No cache tensor is captured.

Native build exited 0:

- `libGenie.so`: **11,636,104 bytes**
- SHA: **`3a61a7ea888e39b54999c25b0644ff068733c343cb693e5eafee9be4538dccc2`**
- AArch64 ELF and observer markers verified; all 103 Genie imports of the unchanged runner resolve. Existing bound Rust/native object inputs are reused. This is a new observer artifact, not a binary-equivalence assertion.

Frozen stage:

- `TRACK/.local/frozen-stages/paired-prefill-capture-stage-01`
- Manifest: **`b99056c1faa1e25823fd9bcda2a0968a0445cb93458dc1069e7d269eb9c54953`**
- 19 files / 4,013,526,340 bytes.

Only the observer library and **both** output-cap controls changed: config and script now cap at one selected token. No AR1 continuation is allowed; future validation requires exactly 16 successful AR128 executions and zero AR1. The canonical 2,048-token campaign is untouched.

`phone_paired_prefill_capture.py` is plan-only by default. Execution additionally requires a fresh one-use phone slot, the reviewed stage digest, fresh full main/test APK hashes, and Pi's actual-job/playback-quiescence attestation. It does not mistake an idle main/Room process for generation. It retains the full `phone.lock` lifecycle, read-only RPC checks, exact PID/starttime/executable/argv cleanup checks, raw pull before deletion and read-only postflight identities. Those PID checks remain non-atomic, not pidfd binding.

Phone process deadline is 300 seconds, with the existing bounded cleanup phases. The model entry sets an **8 GiB virtual-address-space limit**, not an RSS or HTP-private-memory cap. Payload disk growth is bounded by the observer; no phone swap/system setting is changed. There are no APK installs, app-data edits, force-stops or reboot/reset actions.

Pi's latest reported APK prefixes `04d9293b…` / `2dd4e0d8…` supersede the old identities. Full current hashes must accompany the future slot; nothing restores an older pair.

## Binding actual inputs to the host

After successful phone capture and raw-first cleanup, `bind_captured_noncache()` requires all **128 input payloads plus the final logit payload**, checks metadata/grids/shapes/history and rejects extra/cache tensors. It preserves exact captured raw bytes in the host input files. Source-generated arrays are retained only for reporting differences, especially RoPE; they are not substituted into the paired execution.

The host's 30 initial caches come exclusively from the host ledger, and later caches exclusively from the host reference outputs. A synthetic contract test deliberately makes captured values differ from host formulas and confirms that the captured values replace only non-cache inputs while the host initial cache remains unchanged.

The actual phone capture does not exist yet. Thus **the mechanism for identical external inputs is ready, but a completed identical-input comparison is not claimed**.

## Host liveness and finite execution plan

`run_paired_prefill_host.py` is also plan-only. Its execution path requires a new one-use grant, a successful released phone capture, exact input-ID parity and exactly 16 status-0 AR128 records with no AR1 continuation. It binds actual captured inputs before launching the compute child.

| Resource | Bound / policy |
|---|---|
| CPU | 2 cores, two BLAS/OMP threads, low-priority scheduling |
| RAM | 10 GiB high / **12 GiB maximum** cgroup |
| Swap | **2 GiB maximum**, existing swap only |
| Time | **1,800 s total**, 1,770 s work with cleanup reserve |
| New output scratch | **1 GiB**, disk-backed; minimum 64 GiB free |
| Trace | 300,000 events / **64 MiB**; logging failure does not replace computation |
| Static dequant cache | **None**: mmap encoded blobs lazily, decode one operand, release after its consuming operation |
| Initial headroom | At least 16 GiB RAM / 10 GiB swap free; live floors 4 / 8 GiB |

There is no hidden all-F32 graph cache. Such a cache would total **9,123,904,808 bytes**. Instead, dequantization is tiled to 1,048,576 temporary elements; the largest complete F32 operand is the head at **1,610,612,736 bytes**. Shape-only accounting estimates 171,343,872 bytes of conservative encoded liveness and a largest F32 output of 134,217,728 bytes. These figures exclude allocator/BLAS packing overhead; the cgroup cap is the hard bound. Full-model memory and runtime have not been measured for this reference.

The host guard samples owned CPU/I/O and live headroom, terminates/reaps only its own compute child on a bound, retains raw partial evidence, and never automatically retries. No memory-lock admission is used. The phone lease is released **before** the host reference starts, so it does not block Janek throughout host computation.

## Validation and remaining limits

Preparation included bounded static audits, DLC extraction, source build, stage copying, all-op topology/shape preflight, verification of 1,386 private blobs and 158 prepared input/cache files, synthetic arithmetic for all operation families, ring-cache carry tests, raw-capture binding tests, and a tiny C++ observer test. The C++ test verifies unchanged input bytes, flushed records, CLOEXEC and failure isolation. An initial metadata probe's set/list API error was retained and corrected before graph extraction; it was not model execution. A packaging comparison initially failed to follow the original SDK include-directory symlink; following that already-bound symlink verified equal copied headers and exactly the two intended source changes, without rebuilding or replaying inference.

**Ready to schedule:** one phone prefill capture, release, then one bounded host prefill using those actual non-cache inputs and independently evolved caches. A new execution grant is still required. If capture, identity, resource, dtype or policy checks fail, preserve the bounded failure; do not replay or silently fall back.

The comparison will concern one exact history/final position under matched declared policy. DSP rounding/fusion/accumulation remain an explicit interpretation boundary. Neither a match nor a difference alone establishes long-output reliability, generation quality or a particular QNN defect.

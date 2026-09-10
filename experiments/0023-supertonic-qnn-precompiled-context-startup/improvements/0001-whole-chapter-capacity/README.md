# Whole-chapter capacity — four source graphs ready, duration context generated

**T2048/L2048 derivatives were materialized once under Pi's explicit release. The separately released duration constructor generated its external context once, with exact I/O and zero Run calls. Text/vector/vocoder constructors are not yet released. No model forward or phone call has occurred.** New graphs stay LOCAL-ONLY. Original0023 recipes, hashlocks, packs and app paths remain unchanged. Pushes remain held by Pi's separate privacy review.

## Capacity and the actual positional change

T2048 allows2039 normalized/NFKD codepoints before English tags. L2048 allows6,291,456 samples / **142.6634s** at44.1kHz. Text count does not guarantee duration.

The released vector graph contained exactly one INT64 `[1,1000,1]` position initializer equal to `arange(0,1000)`. Its two slices follow the latent-mask and text-mask extents. Cast → divide by **active-mask sums** → multiply the shared theta → Sin/Cos feeds attention blocks3,9,15,21. Thus2048—and the earlier suggested1024—could not be a shape-only change.

The approved derivative changes **only that initializer** to INT64 `arange(0,2048)`, shape `[1,2048,1]`, preserving the original1000-element prefix, exact theta bytes, normalization and every consumer. It also applies the same audited seven-node stable Softplus identity. No learned weights changed. This is an explicit positional extension, **not a neutral reshape or quality proof**.

A separate unchanged-table **T1000/L1000** option would offer991 pre-tag codepoints /69.6599s: a possible **one-minute intermediate**, never two-minute support. It was not materialized.

The complete metadata/constant evidence and initial proposal remain in [`results/host-preparation-20260910/`](results/host-preparation-20260910/). The actual integer sequence—not an unavailable neural Python constructor—establishes its arithmetic identity.

## Released materialization result

All four exact official FP32 ONNX inputs are pinned to revision `724fb5abbf5502583fb520898d45929e62f02c0b`. Structural ONNX shape inference/checking and exhaustive ordered node/initializer hashes passed:

| Graph | Nodes before → after | Original initializers | Allowed changes | Derivative SHA prefix |
|---|---:|---:|---|---|
| Duration |1086→1086|98|I/O shapes only|`394ea3e7…8cbad9`|
| Text |1934→1934|146|I/O shapes only|`6bdf11f5…e14568b`|
| Vector |1004→1010|446|One position initializer; Softplus→7nodes +scalar1|`9b6b2a5e…ae70663`|
| Vocoder |401→401|103|I/O shapes only|`539f8ef7…61df792`|

**All445 other vector initializers, including theta, are byte-identical.** All non-Softplus computation nodes are byte-identical and ordered; other graphs have no initializer or node changes. Graph I/O is `[1,T]` text, `[1,256,T]` embedding, `[1,144,L]` latent and `[1,3072L]` waveform, with unchanged style/mask/step inputs.

The four serial workers completed in **9.446s total**, versus600s allowed; maximum component guard time5.214s versus180s. Vector peak process `ru_maxrss` was1,817,996KiB. These measure **offline materialization**, not inference/setup performance. Actual ONNX protobuf parsing includes embedded initializers; external data was disabled. No Torch or ORT runtime was imported.

[`results/materialization-20260910/`](results/materialization-20260910/) retains the release, commands, logs, exact deltas, hashes and cleanup. The four actual ONNX files live under `.local/materialization-20260910/attempt-01/`; **migrate their bytes, not just hashes**. Logical position storage grows8,000→16,384 bytes, but protobuf wire representation changed, so do not infer a file-size delta from that arithmetic.

## Duration EPContext constructor result and frozen request

`tools/compile_duration_context.py` prepares the **same accepted ORT EP-context constructor route**: ORT1.27.1, QAIRT2.49.0.260730, SoC43, burst, offload-IO-quantization0, CPU fallback disabled, external context generation. It never calls `Session.Run`. Actual session I/O/provider membership, a non-embedded single-EPContext descriptor and its external binary are mandatory gates. CPU may appear in the registered-provider list; that is not CPU execution evidence. Constructor success is not neural/physical execution proof.

The request [`protocol/next-constructor-request-disk-scratch.json`](protocol/next-constructor-request-disk-scratch.json) was separately released and its one attempt is **consumed**. The original request/template retain their historical NOT_APPROVED text; the actual release and outcome are in [`results/duration-context-constructor-20260910-attempt-01/`](results/duration-context-constructor-20260910-attempt-01/). Constructor9.083s, outer launcher11.324s, process peak607,488KiB; descriptor815B and binary6,638,456B remain LOCAL-ONLY. Worker/group/container are absent and scratch empty. Request SHA:

```text
aeee2b8a2e4c1306de6cf3ed84b9364e954347ea077588808630bb0cc842fa19
```

This environment-only revision adds `QAIRT_TMP_DIR`, `TMP` and `TEMP`, each equal to the existing owned disk-backed `TMPDIR`. All other request fields and worker/launcher hashes are unchanged. Original request `588f3a71…1eb38` and its NOT_APPROVED release remain intact.

Reviewable plan, **no Docker/native call**:

```sh
P=experiments/0023-supertonic-qnn-precompiled-context-startup/improvements/0001-whole-chapter-capacity
python "$P/tools/run_duration_constructor.py" --request "$P/protocol/next-constructor-request-disk-scratch.json"
```

A future release must bind the exact request, worker and fresh output path. The launcher pins the existing Docker image by ID, uses read-only repository/SDK mounts plus one owned writable phase,4CPUs/thread limits,8GiB memory/no extra swap, no network,520s worker +20s grace, and bounded owned-container cleanup within the proposed600s envelope. No pull/build or automatic retry. App builds retain priority. Exact revised argv is retained in [`results/constructor-scratch-request-20260910/plan.json`](results/constructor-scratch-request-20260910/plan.json). Cleanup checks a unique container name and its ownership label before removal by name; this check/remove boundary is **not atomic** and retains a name-reuse race. Removal by inspected immutable container ID remains future hardening, not part of this environment-only revision.

This worker now has one real constructor-only result in addition to its fake-runtime tests. **30 focused tests passed**:23 graph/constant/structural cases and7 constructor/transport mock cases. No mock result is native evidence. The duration result is not a reload, model/phone execution, whole-chapter or quality proof. The earlier duration-only *source-derivative* request files are historical NOT_APPROVED templates superseded by the four-graph materialization release; do not execute them.

## Fidelity and comparison boundaries

- Masked padding is demonstrably non-neutral: experiment0022's T235→T239 changed duration15.8623657→15.6378775s and embedding max difference0.1110139. Positional-prefix preservation does not erase that result.
- Preserve app normalization, M1/SID5, five steps, speed1.0 and chapter-seeded xorshift64*/Box–Muller. Future comparisons require **identical prepared masks/noise arrays**, not merely equal text or a textual seed. Upstream8step/1.05/PCG64 defaults differ.
- One logical render remains duration1/text1/vector5/vocoder1 → one naturally trimmed complete-chapter WAV. Never use the auto-chunking `synthesize()` wrapper. Callback counts are not a new fatal profiling gate.
- Larger-shape QNN support, full one/two-minute speech coverage, loaded-route behavior and Moritz's exact-WAV listening verdict remain unproven. Janek's current canonical T239/L238 one-WAV gate is unchanged.
- Shape-based memory examples—not measurements—include8.605× L-linear growth and≈74× attention areas. At2048, app latent/embedding/wave buffers are1.125/2/24MiB. One dense8-head cross-attention score is128MiB per batch; actual source metadata doubles the classifier-free batch. Native fusion/tiling/temporaries and peak memory are unknown.

No private battery or learned charging/sleep-history contents were collected or added here.

# Parity vocoder constructor/export PASS — missing export resolved

**One released constructor, zero Session.Run calls.** The exact reviewed source `5c135922…c8ad07` finalized successfully and produced a valid external EPContext. Together with the separately retained duration/text/vector results, **four larger-route constructor/export pairs are now available and independently reviewed**. This is not context reload, neural/phone execution, fidelity or whole-chapter listening acceptance.

## Exact scope and first outcome

Request `8557ca10877c15718f75fbb6a60b8bd98ba809aec22cf000823432f06daec001`, committed readiness `83eb55e`, retained separately approved release. Unchanged worker `ae827a55…fd6b61`, launcher `13f02b43…e9d27`, guard `33373e74…3705d`; ORT1.27.1/QAIRT2.49.0.260730/SoC43, burst/offload-IO-quantization0/CPU fallback disabled, one fresh network-off Docker container,8GiB/no extra swap/4CPU, ORT intra/inter1 and520s+20s grace/≤600s. Global/session verbose logging and own-cgroup snapshots are unchanged from reviewed v2. No worker/options changes, retry, reload, other graph, phone or pack work.

| Observation | Result |
|---|---:|
| Constructor |39.474873s|
| Native worker |39.928378s|
| External guard |41.238189s|
| Outer launcher |41.328476s|
| Process peak `ru_maxrss` |2,006,548KiB|
| Own-container cgroup peak |1,976,119,296B|
| Own-container limit |8,589,934,592B|
| Limit/OOM event deltas |all zero|
| Constructor / Run count |1 /0|

Process peak RSS and cgroup accounting are different measurements; neither is target VTCM or physical memory bandwidth. Own-container current memory was27,934,720B before and1,496,272,896B after. Scope/read/capture/write errors were absent. Cleanup: PID1949989 reaped, PID/group/container absent, all owned scratch empty. The name/label cleanup boundary remains non-atomic; no immutable-ID hardening is claimed.

## Actual ABI and protected artifacts

Actual session I/O: FLOAT `latent[1,144,2048]` → FLOAT `wav_tts[1,6291456]`, ordered ABI SHA `3e15a281…a34ed6`. Registered providers include QNN and CPU; CPU fallback is disabled by session configuration. Registration is not CPU-execution evidence.

| LOCAL-ONLY artifact | Bytes | SHA256 |
|---|---:|---|
| `vocoder-context.onnx` |733|`67406e4a28119e33907a4c91ab806f9c411a7a413055052562a367e57c8442fc`|
| `vocoder-context_qnn.bin` |69,664,936|`13db6690e22bf4bb2075838f9f0876f6b75bbb9f7b7c11b489a3d7de4cb91482`|

Descriptor gate: one `com.microsoft::EPContext`, no initializers, `embed_mode=0`, exact external reference and public ABI. Post-constructor source/13 selected runtime-pin verification passed; actual post-close descriptor/binary hashes match worker receipts. `local-artifacts.json` gives exact local paths. Preserve actual bytes under `.local/constructor-vocoder-parity-t2048-l2048-attempt-01/data/`, not just hashes. All original source graphs, two failed vocoder attempts and prior three successful contexts remain immutable.

## Compiler evidence, including nonfatal warnings

`compiler-evidence.json` binds the complete4,216,216B verbose stderr and exact line passages:

- Four named parity `DepthWiseConv2d` branches appear in graph composition at30371/30820/35712/36161.
- VTCM remains8,388,608B at47054; no host RAM/VTCM increase was used.
- **Four nonfatal StridedSlice tiler warnings** remain at47124/47128/47266/47270: minimum75,579,392B for `[1,1,6150,256]`. These are compiler warning requirements, not measured live VTCM allocations. They were not hidden or turned into a failure after the actual successful finalization/export.
-48482: `QnnGraph_finalize done. status 0x0`;48561: context binary buffer succeeds.
- The previous fatal untiled-DilatedConv/TCM-migration/Optimize17 chain is absent from this run.

This resolves the **missing vocoder export**. It does not imply warning-free lowering, a universal absence of re-fusion, efficient physical scheduling or native FP16 equivalence. No input arrays were supplied for a model forward and no WAV was generated.

## Evidence and independent review

Raw constructor/result/cgroup/postpin/guard/argv/cleanup receipts were copied before classification. The raw early `constructor-receipt.json` retains its initial `status:started` label by design; actual I/O is captured there before the final successful artifact classification in `raw/data/result.json`.

Nik independently verified the exact request/release/helper/guard/argv, actual descriptor/binary/ABI/SDK build `v2.49.0.260730134355`, postpins, cgroup scope/events and cleanup. His FINAL saved-result verdict: **constructor/export gate closed; missing-export blocker resolved**, no remaining constructor review. Review at `/home/moritz/.cache/nik-podcast-reviews/vocoder-parity-constructor-20260910-attempt-01/` (`review.md`, `independent-audit.json`); no native/Docker/model run by Nik.

The release is consumed. Follow-on context reload, inference, fidelity, complete-chapter WAV generation and phone work require a new Pi scope. The app's canonical T239/L238 result and Moritz-only listening decision remain separate. Push hold remains.

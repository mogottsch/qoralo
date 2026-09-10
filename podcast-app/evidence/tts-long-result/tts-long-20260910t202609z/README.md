# First physical whole-long-text request — render failure, no WAV

**Run:** `tts-long-20260910t202609z`. The new pack staged and all four context initializations returned. One complete noncanonical narration was attempted. Duration/text executed; the first vector invocation failed with ORT/QNN graph-execute error6006. Vocoder was never run. **No audio file exists; no capacity, fidelity, listening or end-to-end success is claimed.**

## Exact request and route

The unchanged approved candidate is `b86008708cc459c855149eee49c58a7468e079d24c9de4842eab56a5bcef325d`, app `e9cc95b76bfbd776a2861ab43dc5fa63805cb0854d1809dcf29175e8745a71be`, test `fc19bf43237949820e7f4cfb83c302287b8ae9585e317a874741447a3cd22c9b`. Caller `a87b3f358f9efff213beeed3261f651620e5763c0f3b022718190860740815a4` and privacy dependency `a62d204c380a5b2d0c8f7c5bd94729b6f823e18200feed2ebe24fa73962bec3c` are unchanged. The explicitly approved guard is `5ca6be91be151acd2937b5e65871a40361f9bae99ae444880eae0e29b6f2c425`, overriding only the historical host-guard reference via sidecar `60dd58885efdc8406049365d92c26838fdedf4db99f568638479a1f71e1b046d`.

Contract `66f8dcd5e753acabd4f69040496ef476b709c2317ebc41a5d5d926b13c353a87`; new pack manifest `116fda95a907f6dc35bfe7c2144fe2818ed438cc109c1faa3f95cafc2fc84066`. M1/SID5, T2048/L2048/144 channels, nominal5steps/speed1.0 and unchanged native9/seed algorithm. A five-step configuration is not evidence of five successful vector executions.

Actual whole input:1327 bytes/227 words, SHA `f25655b54ad4e8d5e782dedf069867d6c201f1ea48327724527356d0f35aea37`. Actual normalized text:1324 codepoints, SHA `7add3140f7c8d871d0291e30ac1ca79546ad5fec9792ef78428e7eda9484c8b9`. Tags yield1333 active positions/715 padding. Full source/indexer reconstruction is retained and explicitly not native-buffer capture. Approximately90 seconds was only a prose-length target; no emitted duration is available. No text/audio chunks, stretching, fallback, Gemma or retry.

## Actual execution versus metadata

| Graph | ORT Node invocations | Successful typed RPC/cycle evidence |
| --- | ---: | --- |
| Duration | 1 | RPC535,779µs; accelerator836,379,701cycles |
| Text | 1 | RPC5,148,862µs; accelerator5,974,079,122cycles |
| Vector | 1, **failed** | No successful ROOT RPC-execute/cycle rows |
| Vocoder | 0 | Load-only metadata |

All four ORT Session initializations returned. Those records are not four-graph execution proof. The vector Node event (~2.897s) records a failed invocation, not success. Planned1/1/5/1 did not complete.

`device/service-result.json` records `tts_failed`, stage `render`, PID8003 and the complete exception chain. The first reported ORT error is graphExecute6006. Nik's pinned-header audit maps it to `QNN_GRAPH_ERROR_SET_PROFILE` (“Failure to set profile”). The following cDSP user-PD TLBMISS/BadVA0x40 report and cleanup-side chronology are retained in his separately labelled excerpt; the exact internal cause remains unproven. Do not infer OOM, tensor incompatibility or a guaranteed profiling change fix from this code alone. Empty native stdout/stderr are retained unchanged rather than replaced with imagined verbose logs.

The generation process subsequently logged FastRPC teardown errors and `qnn_interface.contextFree()` error handle1003. **Native teardown was not clean**, even though host settings/PID/scratch cleanup completed. Labelled PID/tag-filtered logcat excerpts bind the private complete original and retain exact source line numbers; they are not raw global logcat.

The load-stage event span is3585ms (elapsedRealtime start→complete, not isolated adapter timing). Driver terminal collection took13,863ms; controller exit/collection success does not mean successful synthesis. No complete render latency, emitted duration, RTF or warm median is available.

## Guard, staging and cleanup

The separate authorized setup receipt `../pre-run-20260910t202606z/` found all three actual package process names absent; no package needed stopping and no data was cleared. The new guard admitted known terminal FAILED history while retaining active/unknown-state rejection. All three physical startup checkpoints completed with matching read-only DB snapshots and exact identity/hash checks.

Only the fresh long namespace was staged. The accepted old pack manifest was checked before/after; no old pack replacement or full post-run old-file rehash is claimed. Host cleanup reports `errors:[]`, `settingsErrors:[]`, all three actual PIDs absent and owned transfer scratch removed. Packages, new pack and original data remain. Settings readback and lock release completed. No follow-on model/device operation or retry was performed.

## Retention and boundaries

`retained-manifest.json` binds344 public files/1,629,031 bytes: safe host captures, exact app-owned archive members, approved candidate/override and labelled derived observations. Ten complete condition/DB/global-logcat originals (2,939,836 bytes) remain private and hash-bound. No private database contents or full conditions/global logcat were copied here. The separate setup receipt binds55 originals/6,832 bytes.

Original pre-run stops and frozen candidates/packs are unchanged. The accepted canonical short WAV/listening verdict is unaffected. This failure belongs in one status-board line, **not a no-audio listening page**. Only a real exact-hash WAV can receive a listening handoff. Pushes/external publication remain held. **[Nik FINAL audit](nik-review.md): valid collection, failed first vector invocation, no WAV.** Exact bindings, source attribution and host cleanup are independently verified; native teardown is not clean. His report, machine audit and narrow DSP-crash excerpt are copied unchanged and bound by `nik-review-retention.json`; initial raw/derived records remain unchanged.

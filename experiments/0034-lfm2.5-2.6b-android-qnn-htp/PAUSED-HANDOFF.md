# Jens / LFM paused handoff — 2026-09-11

**Moritz paused this track. No new investigation, build, model call or phone run until he resumes it.** Only packaging of already completed evidence followed the pause. Push/history-rewrite hold remains; no agents may be spawned.

## Last assessed / completed results

- Pi independently accepted the source and single canonical171/zero-state **CPU** comparison: all60 outputs finite and byte-identical, including signed-zero semantics. His review did not independently rescan the large FP16 proxy arrays. That is not general HTP/AR1/nonzero-state/quality equivalence.
- The reviewed query-prescale derivative compiled after one retained12GiB OOM and one memory-only16GiB iteration. Ordinary context `62ad1261…15243`, matching ordered41input/60output ABI;1542/1542 optimized nodes delegated, zero unsupported. Pi confirmed this completed milestone; stale start messages must not trigger a replay.
- Physical pair `prefill-pair-20260911T110729Z-1476558` then completed: one baseline-first and one candidate-second fresh process, one AR171 call each, **no AR1**. All41 actual pre-call input buffers equal each other and frozen host inputs; all60 outputs are finite and bit-identical (1,664,000 FP32 values/route). Full vocabulary ranks match; endpoint597 both.
- Descriptive API times:6.451538331s baseline /5.581822238s candidate. Accelerator cycles:3,364,707,232 /2,932,203,396; named scale-node cycles:650,131,353 /907,740. Both per-node sums match their totals. This is **one ordered pair**, not general/warm/statistical throughput or attributable full-request speedup. Setup/cache/thermal/order effects remain.
- **New correct-input shared fidelity risk:** physical versus CPU has only3/60 tensors within descriptive0.02/0.02 tolerance; max abs10,594.696502685547 at `present.2.key`, max logit-chunk abs7.209851264953613,127990 vocabulary-rank changes although argmax597 matches. Both physical variants share this drift; it is not introduced by prescaling. Do not rehabilitate historical wrong-position evidence. Root cause was **not investigated** before pause.

Physical data is owner-verified and saved for later review; do not relabel it as an independent Pi numerical review.

## Commits (all local, no push)

- `1ae2f82cbb45a5623deeb9f7f79e85f44f3ed66f`: first CPU attempt; baseline outputs retained, derivative rejected external-data symlink containment before execution.
- `1b69a181eebdffe348b3b78a2b3b9f5930d5f258`: independent data copies, exact baseline reuse, complete CPU/proxy evidence.
- `70ca07f6183fad702ef48388ad3d06eddf623de1`: first AOT12GiB OOM, partial trace only/no context.
- `d586edefbdc59489059c89d689a653809bb975b6`: memory-only16GiB readiness.
- `19b3fa6b81f243aba5b8fc2cd3d64319973fad73`: successful prepare-only context/ABI/mappings.
- `58b11ffea33c15322aae4e902ebcb2e7a97f0643`: native buffer capture/paired phone readiness;67 tests at that checkpoint.
- `f8ec117dda8978184f06b601865a59cfb4d04bfc`: bind endpoint bytes to own saved logits;68 tests passed.
- `535591f361b30a89ada78d90f72fee8eb0c8d716`: preserve first phone preflight and accept Toybox's valid `timeout --help` exit125 without removing the device timeout bound.
- This handoff and completed physical package are in the final pause-closeout commit reported to Pi/Kate.

The first malformed monitoring-tool request never launched a process/ADB/lock. The subsequent real preflight `prefill-pair-20260911T110306Z-3963969` held/released the lock but stopped before remote mkdir/staging/model execution because valid timeout help returned125. Both facts are separate from the successful fresh pair.

## Exact evidence / assets

Under `experiments/0034-lfm2.5-2.6b-android-qnn-htp/`:

- `results/query-prescale-prefill-pair-attempt-2-success/result.json`: exact saved pair analysis, SHA `61abf2c460cd73d154729836abca3f2c989a80d03c02a5deef555af063c98ccb`.
- `results/query-prescale-prefill-pair-attempt-2-success/physical-vs-cpu.json`: already-computed shared-drift comparison, SHA `fed28fc3f971da4135cf894777f7b8c4712b021e116942841291ae70e412d57d`.
- The package includes per-phase native manifests, endpoint bytes, profile/runner/memory logs, cleanup receipts, and **labelled core telemetry only**. Full battery/thermal originals remain private and hash-bound in `private-retention.json`; never copy their learned histories into Git or silently call extracts raw.
- Private physical run: `.local/prefill-pair-phone-runs/prefill-pair-20260911T110729Z-1476558/`; all native arrays are under `baseline/native/` and `candidate/native/`, full telemetry under `private/`.
- Candidate context: `.local/query-prescale-aot-20260911T102346Z-120375/compiled/context_qnn.bin`,1,602,644,544 bytes, SHA `62ad1261fd3181d5e4a3d8832d3bfd553d9d9e44aa4597face98b5268f315243`.
- Baseline context: `.local/qnn-prefill/ar171/compiled/context_qnn.bin`, SHA `d5ca624cc71a173c7de969fac777e2ce136db3b502e04c2991651b510dabba5a`.
- Frozen phone stage: `.local/prefill-pair-stage-20260911T105155Z-802274/`; metadata SHA `94d564554fd4f4d9508dd8ee8561100cd1f95c75834ab86d0f18cc9fb23cf957`, manifest SHA `284630971b02f44a8f11a66408b2dd0f8f09bbe2a729cd20b7cf4eea862e7c35`.
- Android runner SHA `b0028439163d0b8f9ac32ffa85a52d50cdba38d823643ab215e9f180f0fa0cbf`; host runner SHA `06650dd67661d20f7e9e0065da631562f6a36f12dc0c8e96caadcec064656ab0`. Build logs: `.local/prefill-pair-runner-final-20260911T105122Z-802274/`.
- CPU reference/derivative/debug arrays: `.local/query-prescale-20260911T094138Z-78096/`; prior baseline run `.local/query-prescale-20260911T093452Z-73227/` remains unchanged.

Runtime remains QAIRT2.49.40.260810 / build `v2.49.40.260810104044`; NDK28.1.13356709. Use the experiment `.local/venv/bin/python` only after resume if further work is assigned. No SDK/model assets belong in Git.

## Cleanup and interrupted step

- Physical pair launcher exited0. Both saved `process-after.txt` files are empty with successful checks; `cleanup-status.txt` is `absent`; `lock-status.txt` is `released`. Janek/Pi/Kate received the actual release before the pause. No app stop/install/data/settings/audio changes.
- AOT/native builds and offline analysis processes had already exited. The two finite shell sessions had exited125/0; cleanup found both background session IDs already removed. No owned job was killed during pause because none was active. No new ADB/process probing was performed after pause.
- No model execution was interrupted. Evidence packaging was the only unfinished step, completed by this handoff/commit. Reservations/resources are released on closeout.
- Last full test suite:68 passed before the timeout-help correction. Corrected shell syntax and the actual physical pair passed. **No new tests/builds were run after pause.**

## Next step NOT started

After Moritz resumes the track, assess the saved shared CPU-versus-HTP drift before broader fidelity/quality claims or rollout. Start from retained source/arrays if useful; do not assume a normalization/rotary/precision cause without evidence. No such investigation, AR1/integrated follow-on, repeated pair, new AOT or campaign has started. Phone work must still be scheduled with Pi/Janek and use full `phone.lock`; never race or disturb an active user/app job. Nik reviews only Janek. Historical0029/0033 and all prior0034 evidence remain untouched.

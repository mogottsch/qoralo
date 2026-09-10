# Improvement 0001: long-output fidelity and speed

## Boundary

This is a new improvement track. It does not modify, replace, or relabel the completed canonical campaign in commit `37a2953` or its publication in `e91b3f5`.

The accepted route remains the baseline. Any new conversion, host diagnostic, hybrid, or phone run must use a distinct artifact identity and run ID. A hybrid must select and label its backend before a complete logical request; hidden tensor- or provider-level fallback is forbidden.

## Current host status — 2026-09-10

**The paired DLCs compile into one SM8550/v73 context, and a separate frozen Genie stage/config is now hash-verified for review. All 30 cache contracts and 120 flat-buffer boundaries are verified in host metadata. No candidate Genie runtime load/query or phone run has occurred; placement and fidelity remain unvalidated.** The first three retained launches diagnosed two missing loader-path prerequisites and an unexecuted patch assumption (AR1 has six explicit selected cache encodings; AR128 has only three input entries). Existing host libraries were reused without installation or SDK changes.

Attempt 04 prepared both FP16 global-value-cache ONNX variants and passed independent scope checks. Pi then requested STOP → TERM to release app resources before a DLC was produced. It remains **an app-priority interruption, not a model or numerical failure** at [`results/global-value-fp16-attempt-04/`](results/global-value-fp16-attempt-04/result.json).

After a separate release, attempt 05 used the unchanged recipe. AR1 converted to a 2,356,848,948-byte DLC (`4e67d80e…a6cc`). Official DLC CSV inspection proves Float_16 on all three selected global value-cache **inputs and outputs**, unchanged dimensions, and unchanged signatures on every other public interface. Operator count is 6,875; Convert count remains 31→31, so the hoped-for conversion-count reduction is not demonstrated. Converter float-precision fallback warnings rise from 75 to 81 (three global concatenations plus three output Casts); these are not evidence of CPU provider fallback or of full HTP delegation.

Sequential AR128 conversion failed with **Errno 28** while dumping external data to the 16 GiB `/tmp` tmpfs. The owned partial scratch file was hashed and that directory alone removed. A first read-only inspector timed out after 90 seconds with empty logs; a separately retained guarded inspection completed. No conversion retry occurred. See [`results/global-value-fp16-attempt-05/result.json`](results/global-value-fp16-attempt-05/result.json), including losslessly compressed candidate/baseline CSVs.

After separate review/release, attempt 06 used disk-backed owned `QAIRT_TMP_DIR` and converted **only AR128**, reusing the exact hash-verified attempt-05 AR1 file without rewriting or reconverting it. The new AR128 DLC is 2,356,859,020 bytes, SHA-256 `48fc15f0cbec88963f7b4d0f9007b82ca5a1e1d812ca320ceec776e00a917b64`. Official CSV inspection confirms selected Float_16 inputs/outputs, unchanged unselected public signatures and dimensions, and matching datatype/encoding on **all 30 four-way AR1/AR128 cache contracts**.

AR128 operator count increases **6,830→6,842**, including **Convert 30→36**, three added Casts and three Dequantize ops. Its converter float-precision warnings increase **15→21** (15 RmsNorm plus three global Concats and three output Casts); reused AR1 remains 75→81 with Convert 31→31. These observations show no count-based speed win and do not imply CPU fallback or full HTP delegation. See [`results/global-value-fp16-attempt-06/result.json`](results/global-value-fp16-attempt-06/result.json).

The SDK removed all scratch files; the empty owned scratch root was removed and all owned processes exited. [Disk-backed scratch/reuse notes](DISK-SCRATCH-READINESS.md) record that conversion-stage environment change.

A separately authorized context-compile attempt then executed the exact hash-pinned accepted compiler recipe, substituting only the paired DLC paths/hashes and fresh storage paths. The context is **1,186,430,976 bytes**, SHA-256 `1d80d01637f032ab0c5ec3135e9458c648b4c18e034574a56d42dbfbdbdca9f8`, 61,440 bytes larger than baseline. Metadata confirms backend 6 / soc43 / v73 target markers, original graph aliases and 38-input/31-output interfaces, all 30 matching active cache signatures, and all **120 cache tensor boundaries FLAT_BUFFER**. Only the selected global value-cache types/quantization differ. See [`results/global-value-fp16-context-attempt-01/result.json`](results/global-value-fp16-context-attempt-01/result.json).

[Genie source notes and compatibility risks](GENIE-FP16-CACHE-SOURCE-NOTES.md) explain byte-copy support, key-derived clear mode (FP16 negative zero), NativeKV's uint8-only restriction and quant-dependent cache-export paths that were not used. These are source rationale, not runtime semantic proof. The exhaustive unsupported-operator count is null because native compiler logging can be suppressed at the accepted verbosity; no extra compile was run for logs. Full physical HTP/neural CPU-free placement, runtime loading, fidelity and speed improvements remain **unmeasured**. The owned compile scratch and processes are cleaned up. Stop for separate review before runtime/fidelity or phone work. Completed campaign and registry evidence are unchanged.

## Frozen stage and phone-return plan

[`results/frozen-genie-stage-readiness/result.json`](results/frozen-genie-stage-readiness/result.json) binds independent private payload copies totaling 4,003,855,761 bytes. The frozen manifest SHA-256 is `584841604ecf97a1a916c9a7f765e49ff9f7a2ee751a61fda9e9e6588f02fe25`; `bin/genie-app` is read-only executable **0555**, other inputs read-only, and private directories 0700. Baseline files/inodes/config were not modified. Context, libraries, LUTs, tokenizer, BOS suppression and exact short/long input bytes are pinned; the config remains byte-identical to the accepted baseline.

The only included execution script is one **engineering/noncanonical short query capped at 16 tokens**, with fresh dialog, verbose logging, output streaming/flush and separate setup/request profiles. It was not executed. Long inputs are frozen, but no long script exists. The later exact-long comparison must preserve the 2,048-token ceiling and receive separate review/permission.

The [phone-return diagnostic plan](PHONE-RETURN-DIAGNOSTIC-PLAN.md) specifies raw-first/error/partial retention, nullable optional metrics, exact device and manifest checks, one complete phone-lock lifecycle, scoped-PID timeout cleanup and separate approval gates. No ADB, runtime/model load, fidelity, compilation, APK or phone-lock acquisition occurred in that lightweight stage preparation.

A separately prepared [candidate controller](PHONE-RETURN-CONTROLLER-READINESS.md) now implements plan-only-default orchestration with fake-transport tests. Execution requires the exact stage digest, a fresh actual Pi slot, full lock coverage, strict device/build/full hashes and fresh output paths. It has host and remote deadlines, PID/starttime/executable/argv rechecks, raw-before-optional-metrics capture and explicit retained-root status when identity or raw pull is incomplete. Signals remain numeric-PID operations after sequential checks, **not atomic/pidfd identity binding**; that residual race is a review limitation. Neither the frozen stage nor the old baseline runner was changed. No real ADB, repository phone-lock use, model/runtime loading, long script, or phone execution occurred in controller preparation. Source/mock readiness does not grant a physical slot.

The separately documented [request-level routing recommendation](REQUEST-ROUTING.md) remains an unmeasured integration policy, not a new campaign.

## Goal

Improve both practical completion speed and long-output fidelity while preserving exact workload identity and honest provider boundaries.

## Plan

1. **Baseline localization — complete.** Quantify repetition onset and periodic structure in all retained QNN long outputs, compare accepted LiteRT GPU/CPU trajectories on the same rendered bytes, and rank causes/candidates without inferring numerical state from text.
2. **Fallback-free HTP precision probe.** Rebuild the narrowest candidate first: identical FP16 value-cache I/O for the three global-attention layers in both AR variants, leaving all compute on HTP. Inspect datatype contracts, conversion count, context size, compilation time, and any host-executable trajectory evidence. Expand to all 15 value caches only if the global-only candidate is insufficient.
3. **Explicit request-level hybrid design.** Specify short/medium on accepted QNN HTP and long on accepted LiteRT GPU. Bind both route setups, tokenizers, memory costs, and provider proof separately. This is a request-level product policy, not fallback.
4. **Divergence instrumentation.** Design bounded capture around generated tokens 64–128 and the stable periodic-loop onset near token 478. Prefer logits or state hashes; do not claim internal divergence from decoded text.
5. **Reviewed physical gate.** Only after a host candidate is committed and reviewed, request phone priority for a distinct bounded run. Preserve every failed attempt and cleanup proof.

## First milestone

[`results/long-collapse-baseline/result.json`](results/long-collapse-baseline/result.json) records:

- all five QNN long outputs are byte-identical and retokenize to the profiled 2,048 tokens;
- the first 128-token window with four-gram unique ratio at or below 0.25 begins at generated token 84;
- an exact nine-token periodic suffix starts at generated token 479 and covers the final 1,570 tokens (174 full cycles plus four tokens);
- the dominant phrase pattern occurs 215 times;
- accepted LiteRT GPU and CPU outputs both EOS-stop at 756 tokens, have no repeated periodic suffix, and pass sanity;
- QNN and LiteRT differ at the first common output word, while LiteRT GPU and CPU emitted-token trajectories differ at token 6 despite both staying coherent. Therefore text alone cannot localize a numerical logit/state divergence;
- collapse starts around absolute context position 2,012 and stable periodic looping around 2,407, while generation ends at 3,977. Crossing the 4,096 boundary is not the trigger.

## Candidate order

1. **Request-level hybrid:** HTP for short/medium, LiteRT GPU for long. Existing accepted medians predict no short/medium regression and a 59.1% lower long completion time (59.147%), while replacing the repetitive 2,048-token output with a sensible 756-token EOS response. Total completion reflects different stop/output counts, and prefill/TTFT use route-native tokenizers. QNN decode is retained only as a raw Genie observation because first-token inclusion is unspecified; it is not strictly normalized against LiteRT and no decode-rate delta is used for the decision. The cost is a second explicit route setup and memory footprint.
2. **HTP-only global-value FP16:** change only `past_value_{4,9,14}` cache I/O to identical FP16 across AR1/AR128. Storage width remains 16 bits and conversion removal could avoid a speed penalty, but this is a hypothesis requiring measurement.
3. **HTP-only all-value FP16:** broaden to all 15 value caches if necessary.
4. **Normalization/fusion variant:** investigate the expanded float normalization components and value conversion path if cache precision alone does not fix the trajectory.

No phone access or model conversion occurred in the first milestone. The later interrupted conversion above is a separate attempt, not a revision of that observation.

## Safe restart after release

Do not run until Pi releases the app-priority hold. Use a fresh run ID/directory, never overwrite a retained attempt. `tools/convert_global_value_fp16.py` requires `--run-dir`; `tools/run_host_guarded.py` creates that directory exclusively and retains command, stdout/stderr, 10-second pressure samples, and exit status. Its `STOP` file terminates/reaps its own process group and never automatically retries.

The environment needs both QAIRT `2.49.40.260810/bin/envsetup.sh` and the already-established experiment `.local/host-libs` prepended to `LD_LIBRARY_PATH`. That directory resolves managed Python `3.10.18` and `/usr/lib/libunwind.so.8`; exact paths/hashes and pybind `ldd` output are retained in attempt 04. SDK envsetup alone was insufficient.

`--reuse-ar1-dlc <attempt05-ar1.dlc>` verifies the accepted result/size/hash before QAIRT import and converts only AR128 in a fresh attempt. Reused AR1 provenance stays separate from newly converted artifacts; it is never overwritten or counted as a new conversion. This support was exercised in attempt 06 after explicit release.

Run only after release, at low CPU/I/O priority with swap allowed and app work prioritized. After conversion, use official `qairt-dlc-info --save` CSVs and `tools/inspect_global_value_dlc.py` to reject inherited quantized outputs or changes to unselected interfaces. `require_cache_pair` requires passed actual AR1 and AR128 comparisons plus matching four-way signatures on all 30 caches before a compilation handoff. Its legacy runtime letters are not full HTP delegation proof. No compilation, fidelity run or phone access is authorized by this preparation.

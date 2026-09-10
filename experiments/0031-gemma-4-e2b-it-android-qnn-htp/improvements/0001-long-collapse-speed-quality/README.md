# Improvement 0001: long-output fidelity and speed

## Boundary

This is a new improvement track. It does not modify, replace, or relabel the completed canonical campaign in commit `37a2953` or its publication in `e91b3f5`.

The accepted route remains the baseline. Any new conversion, host diagnostic, hybrid, or phone run must use a distinct artifact identity and run ID. A hybrid must select and label its backend before a complete logical request; hidden tensor- or provider-level fallback is forbidden.

## Current host status — 2026-09-10

**Attempt 05: AR1 DLC/interface gate passed; AR128 blocked by tmpfs exhaustion. No restart authorized.** The first three retained launches diagnosed two missing loader-path prerequisites and an unexecuted patch assumption (AR1 has six explicit selected cache encodings; AR128 has only three input entries). Existing host libraries were reused without installation or SDK changes.

Attempt 04 prepared both FP16 global-value-cache ONNX variants and passed independent scope checks. Pi then requested STOP → TERM to release app resources before a DLC was produced. It remains **an app-priority interruption, not a model or numerical failure** at [`results/global-value-fp16-attempt-04/`](results/global-value-fp16-attempt-04/result.json).

After a separate release, attempt 05 used the unchanged recipe. AR1 converted to a 2,356,848,948-byte DLC (`4e67d80e…a6cc`). Official DLC CSV inspection proves Float_16 on all three selected global value-cache **inputs and outputs**, unchanged dimensions, and unchanged signatures on every other public interface. Operator count is 6,875; Convert count remains 31→31, so the hoped-for conversion-count reduction is not demonstrated. Converter float-precision fallback warnings rise from 75 to 81 (three global concatenations plus three output Casts); these are not evidence of CPU provider fallback or of full HTP delegation.

Sequential AR128 conversion failed with **Errno 28** while dumping external data to the 16 GiB `/tmp` tmpfs. The owned partial scratch file was hashed and that directory alone removed. A first read-only inspector timed out after 90 seconds with empty logs; a separately retained guarded inspection completed. No conversion retry occurred. See [`results/global-value-fp16-attempt-05/result.json`](results/global-value-fp16-attempt-05/result.json), including losslessly compressed candidate/baseline CSVs.

No AR128 DLC or matched two-graph cache contract exists. Compilation, full HTP delegation, runtime unsupported/fallback counts, fidelity and speed improvements remain **unmeasured**. [Disk-backed scratch readiness](DISK-SCRATCH-READINESS.md) proposes a host-environment-only fix for a new explicitly approved attempt. Completed campaign and registry evidence are unchanged.

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

Source-only preparation now permits `--reuse-ar1-dlc <attempt05-ar1.dlc>` to verify the accepted result/size/hash before QAIRT import and convert only AR128 in a fresh attempt. Reused AR1 provenance stays separate from newly converted artifacts; it is never overwritten or counted as a new conversion. This support has not been run against the model.

Run only after release, at low CPU/I/O priority with swap allowed and app work prioritized. After conversion, use official `qairt-dlc-info --save` CSVs and `tools/inspect_global_value_dlc.py` to reject inherited quantized outputs or changes to unselected interfaces. `require_cache_pair` requires passed actual AR1 and AR128 comparisons plus matching four-way signatures on all 30 caches before a compilation handoff. Its legacy runtime letters are not full HTP delegation proof. No compilation, fidelity run or phone access is authorized by this preparation.

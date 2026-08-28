# LFM 0034 shutdown handover — 2026-08-28

## Last accepted milestone

- Owner commit: `17a27122e8fd25f1f2a892ecbe6af21ebb3bbb4f`
- Publication commit currently above it: `e5c7942`
- Evidence: physical AR1 max16 resume from retained physical AR171 state; one context/graph loaded once, 16 in-process HTP calls, exact CPU physical-state token sequence, coherent partial output.
- Accepted boundaries: setup 3.80356 s, first resumed token 1.11786 s, total max16 17.4183 s; excludes prefill/phase bridge. No raw state/logit serialization, explicit finite scan, or detailed serialized profile. Severe original AR171 state drift remains. Tests at acceptance: 35/35; evidence hashes 29/29.

## Shutdown state / current work

The next host-only task was an integrated single-logical-request runner:

1. CPU-dequantize all 171 prompt embeddings inside the measured boundary.
2. Load/execute AR171 once with all 60 requested outputs finite-scanned.
3. Extract a detailed QNN event stream, free AR171, and reset the detailed profile.
4. Convert all 38 states in memory into the AR1 cache contract.
5. Load AR1 once and generate max16 with all state/logit outputs finite-scanned and all 38 states retained in process.
6. Emit separate backend setup, context-load, CPU-input, graph, argmax, bridge, AR1-load, first-token, decode, and total-request timings.

Only this tracked owner file is currently modified and intentionally uncommitted:

- `experiments/0034-lfm2.5-2.6b-android-qnn-htp/phone/direct_lfm2_qnn_runner.cpp`

Changes currently present include output finite scanning, recursive detailed-profile event logging, deferred/single-context loading, profile reset, `RunPrefill171`, in-memory AR171→AR1 state conversion, and a new `--integrated` CLI path.

No coherent integrated-runner milestone was committed. The first host/Android build attempt failed with a duplicate `offset` declaration in `RunPrefill171`; that source error was corrected, but shutdown was ordered before rebuilding. Therefore the current source is **uncompiled and untested** after the fix. Existing ignored runner binaries remain the previously accepted resume binaries, not integrated binaries.

## Completed evidence relevant to restart

- `0f4aaf6022bec4d55a2b0fb04edbc0acc7d09511`: physical explicit AR171→CPU bridge→AR1 one-token phase switch.
- `fc54da2a616378ae6e9396c1a52d93d8eb661711`: max16 resume readiness and CPU divergence.
- `17a27122e8fd25f1f2a892ecbe6af21ebb3bbb4f`: accepted physical max16 resume.
- Physical-state CPU max16 sequence:
  `[4695,10966,622,310,5272,267,2014,116311,9516,28817,374,278,2909,19260,1703,2165]`
- CPU AR171/sequential-AR1 sequence diverges at decode index 4 (`1561` versus physical-state `5272`).
- Severe prefill-state fidelity risk remains: physical-vs-CPU pre-bridge 3/38 allclose, max abs 10586.69; localized layer 2/head 5/token position 76 outliers.

## External ignored artifacts to preserve

All remain outside Git under the experiment `.local/` tree:

- AR171 context: `.local/qnn-prefill/ar171/compiled/context_qnn.bin`
  - SHA-256 `d5ca624cc71a173c7de969fac777e2ce136db3b502e04c2991651b510dabba5a`
- AR1 context: `.local/qnn-monolithic-one-token/compiled/context_qnn.bin`
  - SHA-256 `76ba15e7fd95e5e13e92be0e88e8e6bbd3123f2b993b6986c9dac8800a9bf212`
- Accepted max16 resume stage: `.local/qnn-prefill/resume-max16-phone-stage/`
  - stage SHA-256 `c77ed599e25e913a93fe53c0cbea15977ce306d76d02d74130e78da6fdf4f88e`
  - manifest SHA-256 `be9eaff06ea5846794b2ea6b689d2accba88ff0ce50835aa67395eed7dc72ea6`
  - 53 payloads / 1,932,854,438 bytes
- Explicit phase-switch stage: `.local/qnn-prefill/phase-switch/phone-stage/`
  - stage SHA-256 `4be7fb1dd02ee5ab7e154705bef4bbf273dd8affeeeae4f9cc479907b2d5f17d`
  - manifest SHA-256 `98bdc0fc20085bc30473865b4db72db9bc4eef44e65c1bd0eadcc022bd01effe`
- Existing accepted resume runner binaries (not integrated):
  - Android `.local/direct-qnn-android/direct_lfm2_qnn_runner`, SHA-256 `659fa97a84d789d0630051d5ff0031d494820de6517e34cccfcb6d116edf9758`
  - host `.local/direct-qnn-host/direct_lfm2_qnn_runner`, SHA-256 `d5c3846e4b847e7552d692986550a9bbbe9afbb4238f4d280627f8698e059c7a`

Do not overwrite or identify those old binaries as integrated builds until new builds pass.

## Combined-context assessment

- Ordinary simultaneous AR171+AR1 duplicates about 3.19 GB constants; combined context binaries are 3,202,476,296 bytes plus 276 MB IO and 568 MB spill/fill metadata. Concurrent loading is unmeasured/high risk.
- Qualcomm shared-weight multi-graph format is not a current claim or candidate: x86 rejected the format and the physical shared-resource route failed context creation. Do not revive it without materially new Qualcomm-supported evidence.
- Current integrated design is one explicit phase transition, not per-token streaming and not dual-loaded residency.

## Exact restart steps

From repository root, after confirming aggregate host memory is available:

```bash
E="$PWD/experiments/0034-lfm2.5-2.6b-android-qnn-htp"
QAIRT_ROOT="$HOME/opt/qairt/2.49.40.260810" "$E/tools/build_direct_qnn_host_runner.sh"
QAIRT_ROOT="$HOME/opt/qairt/2.49.40.260810" "$E/tools/build_direct_qnn_runner.sh"
```

Then:

1. Fix any remaining compile errors; do not use the old binary hashes as success.
2. Add a host integrated stage containing both exact contexts, full embedding assets, QAIRT 2.49.40 libraries, and the 171-token canonical-short IDs.
3. Because AR171 x86 HTP exceeds 1800 s, do not attempt integrated max16 x86 HTP. Use static/build checks plus the existing CPU semantic evidence; optionally verify only the AR1 resume path already bounded by max1 if needed.
4. Validate that detailed profile extraction is phase-separated and that finite scanning covers all 60 AR171 outputs and every 60-output AR1 call.
5. Verify timing definitions carefully: logical request TTFT must include the prefill-context load if it is not persistent, CPU prompt embedding, AR171 graph, and global argmax; total must disclose profile-dump overhead. Do not label it canonical TTFT until a reviewed physical run includes the full boundary.
6. Re-run the 0034 owner tests and add readiness tests/evidence before committing.
7. Request Pi review and explicit phone priority; no ADB before that.

## Blockers / risks / claim boundary

- Integrated code is currently uncompiled after the last source fix.
- x86 AR171 HTP execution is impractical (>1800 s), so host runtime completion is not available.
- Detailed recursive profile output may be large and must be tested for correctness/overhead.
- Physical AR171 state has severe localized numerical outliers; token coherence does not establish equivalence.
- No integrated physical execution, finite-output proof, end-to-end TTFT, statistical campaign, or registry result exists.

## Process and phone cleanup

- No 0034 compiler, Python verifier, qnn-net-run, ADB, or runner process remains.
- The process list contains other agents’ 0032/Qwen jobs; do not stop them.
- Last 0034 physical run verified the scoped remote root absent and process absent; `phone.lock` was released.
- No phone access occurred after accepted commit `17a2712`.

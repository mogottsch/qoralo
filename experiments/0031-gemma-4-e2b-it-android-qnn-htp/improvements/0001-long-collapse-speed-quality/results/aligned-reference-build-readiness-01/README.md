# Aligned GPU reference: compiled, staged and guarded

**Ready for one coordinated phone slot; no Android access or model inference has occurred in this package.** This is a diagnostic reference, not a canonical campaign refresh.

## Build outcome

The source-ready derivative from `f1d8038c` compiled and linked successfully with the existing NDK28.1.13356709, targeting Android31/AArch64. Its source remains SHA256 `bd3e22b740fcfca317434f1e31a0f23e01af3bd8784aaeb6874a1a30f1e138d6`, derived only from the maintained5148aec2 runner.

- Binary:24,827,856 bytes; SHA256 `de02e7b9cbf36f2b6c5fbcf6cee4ee5f9bb5b7a6f65897bd616213b9d3ceff09`.
- Actual compiler and linker exits:0;9.006s compilation and1.001s linking;19.869s complete preparation/build/check sequence.
- Service receipt:19.939s,14.237s CPU,2.8GiB peak memory, no swap.
-2,351 independently copied inputs are hash-bound. Only the frontend object was rebuilt; the cached core objects/archives were reused. The core source snapshot is pinned at `924e79c91542761242244e4f1651851f822e4cbb`.
- Actual ELF inspection confirms AArch64/API31, the intended `$ORIGIN/../lib` runpath, no missing LiteRt API exports, and a dependency closure covered by the staged libraries or Android31 NDK system stubs. This is not Android execution proof.

Two failures are preserved, not overwritten: attempt01 failed before compilation because the cached Android-NDK path was absent; the correction explicitly bound the existing matching installed NDK static archives. Attempt02 failed compilation on a generated LiteRT header; the correction added the generated LiteRT and all protobuf virtual-include roots found in the retained dependency inventory. Attempt03 succeeded. There was no model conversion, dependency resolution/download, Bazel server or SDK mutation.

The current cached core object hashes and source snapshot are bound, but their original compilation inputs are not independently attested. This does not prove equivalence to every object of the historical GPU executable. The different old frontend source/binary was not reused.

## Frozen stage and guard

Stage `aligned-gpu-20260912T094856Z-01` has13 independent read-only files totaling2,690,668,105 bytes. Manifest SHA256:

`247493005323235fac12203085f5d07599f179249bbbde908d4c17c288678e92`

The generic model and all eight runtime/provider libraries match the successful0025 GPU campaign's recorded hashes, including model `18193810…9a63c` and the actual built `libLiteRt.so` `3fdbf643…ea1b74`. The cache's similarly named **prebuilt** LiteRt library is different and was not substituted. Staging completed with actual exit0 under1GiB/no-swap/1CPU/240s limits.

`phone_aligned_litert_reference.py` retains the pinned full-lock lifecycle and direct detached launcher. Count-checked, exactly invertible changes bind the new executable, its twelve NUL-separated argv fields, stage, scope and namespace. The guard checks current app/test hashes `e1b33f…`/`060edd…` and target-process absence, rechecks quiescence before launch, and creates a fresh real cache. No app changes, force-stop, name-wide signals or automatic replay are available. PID/starttime/executable/argv checks precede signals but remain non-atomic, not pidfd-based.

The only request uses GPU, a fresh Session, context8192 and max2048. Before its sole `RunPrefill`, the runtime saves and compares every effective input ID to the frozen1929 single-BOS vector. Mismatch stops before submitting that logical request. No rewind, `:nocache`, alternate backend/cap, short smoke, EOS sweep or fallback request is allowed.

## Bounds, evidence and interpretation

Build limits: MemoryHigh3GiB/MemoryMax4GiB/MemorySwapMax1GiB,2CPU,nice15, idle I/O,1800s deadline,30s stop grace. Launch required12GiB available RAM/12GiB free swap/100GiB free disk; live floors were4GiB RAM/8GiB swap/64GiB disk, with a16GiB copied-input cap. No global tuning or retired heavy-RAM lock was used.

Six focused build/stage/argv/shell tests and the full host/source/saved-evidence suite pass; exact counts and exits are in the retained test logs. Raw/compiler/controller-source receipts are included. Restricted binaries and cached source copies remain private. Historical Bazel Java logs contain environment secrets and are deliberately excluded; new compiler commands use an explicit credential-free environment.

The future physical request has one1800s process deadline and independent bounded capture/cleanup. All ADB requires an actual one-use Pi slot and the full `artifacts/locks/phone.lock`. Complete raw evidence is pulled before root deletion; incomplete capture or unknown process identity retains the owned root. Optional telemetry and terminal-token gaps remain nullable.

Input alignment removes the proven extra-BOS confound, not the remaining frontend/artifact/quantization/context/stop-policy differences. A sensible aligned GPU response would not identify a particular QNN defect; a collapsed or failed reference would require interpreting its actual evidence, not automatically rerunning it. No normalized speed or commercial/source binary-equivalence claim is made.

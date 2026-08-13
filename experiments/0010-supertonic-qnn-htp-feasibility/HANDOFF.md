# Experiment 0010 handoff — paused for tomorrow

## Current status

Work is paused after host preflight and a successful reusable Android ONNX Runtime + QNN build. **No QNN graph has run on the phone, no HTP execution has been proven, and no speedup is claimed.**

The canonical machine checkpoint is [`results/host-checkpoint.json`](results/host-checkpoint.json).

## Completed

- Re-anchored the track to the exact experiment 0008 Supertonic 3 assets and Galaxy S23 Ultra baseline.
- Captured deterministic CPU fixtures for the frozen transcript and M1 voice with seed `20260813`.
- Captured the exact experiment-0008 vocoder deployment shape: input `[1,144,238]`, output `[1,731136]`.
- Built and retained a fixed-I/O-shape derivative of the released vocoder.
- Proved that disabling CPU fallback works as a negative control: the released fixed vocoder did not fully assign to QNN CPU and session creation failed.
- Retained host HTP attempts. They loaded QAIRT 2.49 backend/system interfaces but produced no output and zero-byte ORT profiles, so they do not count as HTP proof.
- Rejected a Q8 per-tensor re-quantized vocoder derivative on host numerical evidence: cosine was about `0.03` and SNR about `-8 dB` against the references.
- Captured the phone's non-destructive identity: `SM-S918B`, `SM8550`, arm64, Android 16/API 36. No model ran on it.
- Completed a clean Android arm64 build of ONNX Runtime `v1.27.1` with QAIRT `2.49.0.260730` QNN static integration. `libonnxruntime.so` is 22,399,512 bytes with SHA-256 `643c6f6fd3d2b375ca8f2407a1695acaf55320b8e947adc4284665640fdc3ae9`.

## Local reusable build cache

The source and build trees were moved out of `/tmp` and retained under ignored paths:

- `.local/onnxruntime-v1.27.1-source/`
- `.local/ort-v1.27.1-qnn-2.49.0-android-arm64/`

The generated QNN/ORT binaries, QAIRT libraries, fixtures, profiles, and model derivatives remain ignored and local-only. Their critical hashes and paths are in the checkpoint JSON. Do not delete the build tree or run the earlier `rm -rf "$BUILD"` command for ordinary iterations.

The broad build compiled 1,863 Ninja steps, including test targets, because `onnxruntime_BUILD_UNIT_TESTS` remained enabled even though tests were not run. For later code changes, reuse the tree and build only the required target. A typical container invocation should mount the preserved source at `/src` and build tree at `/build`, then use:

```bash
cmake --build /build/Release --target onnxruntime -j8
```

Runner-only changes should link against the existing library and must not rebuild ONNX Runtime.

## Exact next step

1. Reconfirm phone use after resuming and acquire `artifacts/locks/phone.lock`.
2. Hash-check and stage the built Android `libonnxruntime.so` plus the minimal QAIRT 2.49 Android/HTP-v73 runtime set in ignored storage.
3. Run a tiny QDQ-add control on the S23 Ultra with CPU fallback disabled and detailed QNN profiling.
4. Require positive HTP profile evidence. A successful process or plausible output is not sufficient.
5. Only then run the fixed released vocoder. Do **not** use the failed Q8 re-quantized derivative.
6. Compare with thresholds frozen before seeing phone outputs, then decide whether the vector estimator and end-to-end path are justified.

## Safety and publication

- No root, system tuning, or system-library mutation.
- No Qualcomm proprietary binaries, headers, license text, profiles, or generated contexts are committed or published.
- A new or changed terms/consent prompt still requires Moritz.
- Experiment 0009 released the phone; the stale lock was removed during shutdown.

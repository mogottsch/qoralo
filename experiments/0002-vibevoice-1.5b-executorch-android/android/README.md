# Minimal Android ExecuTorch runner

This debug-only app provides a simple decoder probe, a segmented streaming probe, and a one-step/ten-step diffusion probe. It has no product UI.

The app uses `org.pytorch:executorch-android:1.2.0`, matching the exporter/runtime that produced the passing host artifact. Large models, fixtures, APKs, outputs, and logs stay under ignored `artifacts/`.

## Run

From the repository root, with an authorized Galaxy S23 Ultra attached:

```bash
experiments/0002-vibevoice-1.5b-executorch-android/android/run-decoder-probe.sh
```

The harness:

1. serializes the captured `[1,64,1]` FP32 input as little-endian floats;
2. builds and installs the debuggable APK;
3. pushes the 1.375 GB PTE temporarily over ADB;
4. copies it into app-private storage with `run-as` rather than embedding it in the APK;
5. executes the XNNPACK module with memory mapping;
6. retrieves the result JSON and raw `[1,1,3200]` output;
7. compares the Android floats with the saved PyTorch reference.

Defaults assume:

- Android SDK: `/home/moritz/Android/Sdk`;
- Gradle 8.10.2: `artifacts/tools/gradle-8.10.2`;
- model: `artifacts/0002/acoustic-decoder-xnnpack-rewrite-1.2.pte`;
- reference: the matching `.reference.pt` file;
- Python: `.venv/bin/python`.

Override `ANDROID_HOME`, `GRADLE`, `MODEL`, `REFERENCE`, or `PYTHON` when needed.

## Streaming run

```bash
experiments/0002-vibevoice-1.5b-executorch-android/android/run-streaming-decoder-probe.sh
```

This harness incrementally pushes eight first-entry and eight cached-entry PTEs to world-readable test storage, outside the APK. `StreamingProbeActivity` loads and destroys one segment at a time, saves all 34 call-0 caches in app-private storage, feeds those actual device tensors to call 1, and repeats the sequence for cold/warm-page-cache measurements. It retrieves both PCM chunks and all cache outputs for host comparison. The PTEs remain under `/data/local/tmp/vibevoice-streaming-decoder` so reruns skip unchanged multi-gigabyte transfers; remove that directory with ADB when no longer needed.

## Diffusion run

```bash
experiments/0002-vibevoice-1.5b-executorch-android/android/run-diffusion-probe.sh
```

`DiffusionProbeActivity` consumes the real four-input diffusion fixture, records the first call and two warm repeats, then runs two ten-step loops. `DpmSolverMultistepScheduler` owns the FP32 DPM-Solver++ order-two midpoint state in Java; each tensor-heavy prediction remains one call to the unchanged PTE. The harness generates the ignored host loop fixture, transfers inputs and PTE through ADB, retrieves both raw outputs, and enforces the documented tensor tolerance.

The installed test app and its private outputs are retained for follow-up tests. Uninstall `dev.moket.vibevoiceprobe` to remove the app-private files.

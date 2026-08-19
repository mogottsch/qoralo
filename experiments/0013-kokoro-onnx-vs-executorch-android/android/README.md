# Experiment 0013 Android harness

Headless arm64 app for the fixed exact-source-derived FP32 ONNX CPU route. It:

- accepts only the frozen text/model/voice/token/lexicon/policy hashes;
- reconstructs token IDs from UTF-8 text and the real pinned lexicon at runtime;
- selects `af_heart[123]` from the lossless official float32 voice asset;
- creates ORT 1.23.2 with explicit CPU EP, sequential execution, and one inter/intra-op thread;
- requests profiling, runs one first plus five warm complete generations, and records phase timings, RTF, output shapes/hashes/validity, and process memory high-water;
- writes no audio until the complete run passes and never plays audio.

Build user-locally with the pinned Gradle/SDK paths recorded in `results/source-inventory.json`:

```sh
cd experiments/0013-kokoro-onnx-vs-executorch-android/android
../.local/toolchain/gradle-8.10.2/bin/gradle --no-daemon testDebugUnitTest assembleDebug
```

The APK contains only `libonnxruntime.so` and `libonnxruntime4j_jni.so` for arm64; no QNN library is packaged.

## Physical-run outcome

Android 15 scoped storage did not expose shell-owned files in the app-specific external directory as regular files to the target-SDK-35 app. After Moritz authorized further retries, the runner switched inputs to app-owned internal storage: `adb shell` reads only the unique, already hash-verified experiment stage, while debug `run-as` writes each file as the app UID. The app then independently verifies canonical containment, byte length, and SHA-256 before ORT initialization. Outputs remain app-created under its scoped external result directory for pulling.

The canonical fixed-phone run passed: ORT 1.23.2, explicit sequential one-thread CPU, first total `7.4639 s`, warm median `7.4478 s`, valid 7.6-second WAV, and all 18,612 profiled node events on `CPUExecutionProvider`. See `../results/phone-onnx-cpu-checkpoint.json`; historical pre-runtime failures remain in `../results/phone-onnx-bootstrap-checkpoint.json`.

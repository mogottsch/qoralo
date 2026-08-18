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

The app never reached ORT. Android 15 scoped storage did not expose shell-copied files in the app-specific external directory as regular files to the target-SDK-35 app. The single authorized corrected rerun preserved canonical containment but still reported `regular=false`. An app-owned internal copy or `run-as` staging mechanism was not attempted after the stop instruction. See `../results/phone-onnx-bootstrap-checkpoint.json`.

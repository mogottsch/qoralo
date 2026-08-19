# Instrumented official Android ONNX Runtime example

This project is copied from `examples/android_onnx_runtime` at the pinned official OpenMOSS source revision recorded in [`../results/source-inventory.json`](../results/source-inventory.json), then modified for experiment 0018.

The experiment changes are deliberately limited to:

- replacing the two pre-tokenized demo prompts with the reproducibly generated IDs in `BenchmarkPrompt.kt`;
- running a fixed benchmark/profile entry point from intent extras;
- measuring session setup, end-to-end and component latency, RTF, first decoded PCM, process threads, and process memory;
- optionally enabling one ORT JSON profile per component;
- writing machine-readable results and a mono PCM16 listening WAV to a unique app-internal run directory.

The model files remain outside the APK. [`../device/run_phone_cpu.sh`](../device/run_phone_cpu.sh) installs the debug APK, hash-verifies unique `/data/local/tmp` uploads, copies them into the unique app-internal run directory, executes the benchmark and separate profile run, pulls evidence, verifies cleanup, and uninstalls the APK.

Build with:

```bash
ANDROID_HOME=/home/moritz/opt/android-sdk \
ANDROID_SDK_ROOT=/home/moritz/opt/android-sdk \
JAVA_HOME=/home/moritz/opt/jdk-17 \
./gradlew --no-daemon :app:assembleDebug
```

The Maven dependency is `com.microsoft.onnxruntime:onnxruntime-android:1.20.0`. No non-CPU execution provider is registered. Provider assignment is checked from the separate ORT profiles; profiling is not HTP evidence.

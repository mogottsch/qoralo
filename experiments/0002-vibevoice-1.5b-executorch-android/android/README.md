# Minimal Android ExecuTorch runner

This debug-only app loads a `.pte` and one FP32 input from app-private storage, runs `forward`, and writes raw FP32 output plus structured metrics. It has no product UI.

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

Override `ANDROID_HOME`, `GRADLE`, `MODEL`, `REFERENCE`, or `PYTHON` when needed. The installed test app and its app-private PTE are intentionally retained for follow-up streaming tests; uninstall `dev.moket.vibevoiceprobe` to remove them.

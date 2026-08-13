# Safe host device runner

`../run-device.py` separates read-only readiness, APK/model staging, and individual model runs. Every operation takes `artifacts/locks/phone.lock` non-blockingly before invoking ADB. It then requires exactly one online, authorized, unlocked, fully booted arm64 `SM-S918B`. A failed gate or lock conflict performs no device mutation.

## Commands

```sh
EXP=experiments/0008-sherpa-onnx-android-tts-benchmark
python "$EXP/run-device.py" ready
python "$EXP/run-device.py" stage \
  --apk "$EXP/android/app/build/outputs/apk/debug/app-debug.apk" \
  --apk-sha256 <verified-apk-sha256> \
  --model-id complete --inventory deployment-inventory.json \
  --model-dir artifacts/0008/device-stage/files --app-files-root
python "$EXP/run-device.py" run --candidate pocket \
  --descriptor models/pocket/descriptor.json --descriptor-sha256 <verified-descriptor-sha256> \
  --baseline-c 32.0
```

Staging verifies the complete local inventory before ADB, checks a two-times storage allowance, installs the APK, uploads each file under app-specific external storage using a unique temporary name, verifies its device-side SHA-256, and only then renames it into place. `--app-files-root` is for a complete deployment inventory whose paths already include `models/`, descriptors, and `protocol/`; without it, the legacy per-model destination is `models/<model-id>`.

A successful device preflight is normalized into the small committed [`../preflight/galaxy-s23-ultra.json`](../preflight/galaxy-s23-ultra.json) manifest. APKs, staged model files, the full staging receipt, and raw thermal observations remain under ignored artifact paths.

A run waits for protocol thermal eligibility without changing device configuration, force-stops `dev.moket.ttsbench`, launches `BenchmarkActivity` in a fresh process with a pinned descriptor and random write-once campaign ID, and samples process memory, battery, and thermal data. Logcat is retained. Timeout, process death, OOM evidence, crash evidence, malformed JSON, missing result, pull failure, and hash mismatch produce a schema-compatible `failure.json`; partial evidence is not deleted. Run directories include UTC time plus random entropy and are created exclusively, and pulled artifacts are written through temporary files without overwrite.

Raw run directories belong under ignored `artifacts/0008/device-runs`. Small normalized evidence can be promoted only after independent validation.

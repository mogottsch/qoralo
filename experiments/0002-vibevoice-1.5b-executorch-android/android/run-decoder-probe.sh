#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
ANDROID_DIR="$ROOT/experiments/0002-vibevoice-1.5b-executorch-android/android"
EXPORT_DIR="$ROOT/experiments/0002-vibevoice-1.5b-executorch-android/export"
ARTIFACT_DIR="$ROOT/artifacts/0002/android-decoder-probe"
MODEL=${MODEL:-"$ROOT/artifacts/0002/acoustic-decoder-xnnpack-rewrite-1.2.pte"}
REFERENCE=${REFERENCE:-"$ROOT/artifacts/0002/acoustic-decoder-xnnpack-rewrite-1.2.reference.pt"}
PYTHON=${PYTHON:-"$ROOT/.venv/bin/python"}
GRADLE=${GRADLE:-"$ROOT/artifacts/tools/gradle-8.10.2/bin/gradle"}
export ANDROID_HOME=${ANDROID_HOME:-/home/moritz/Android/Sdk}
export ANDROID_SDK_ROOT="$ANDROID_HOME"
PACKAGE=dev.moket.vibevoiceprobe
COMPONENT="$PACKAGE/.ProbeActivity"
REMOTE_TMP=/data/local/tmp/vibevoice-decoder-probe.pte

mkdir -p "$ARTIFACT_DIR"
"$PYTHON" "$EXPORT_DIR/android_io.py" prepare "$REFERENCE" "$ARTIFACT_DIR/input.f32le" \
  >"$ARTIFACT_DIR/input-metadata.json"

(
  cd "$ANDROID_DIR"
  "$GRADLE" --no-daemon :app:assembleDebug
) | tee "$ARTIFACT_DIR/build.log"
APK="$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk"
adb install -r -t "$APK" | tee "$ARTIFACT_DIR/install.log"

adb push "$MODEL" "$REMOTE_TMP" | tee "$ARTIFACT_DIR/push-model.log"
adb shell chmod 0644 "$REMOTE_TMP"
adb shell run-as "$PACKAGE" mkdir -p files
adb shell run-as "$PACKAGE" rm -f files/result.json files/output.f32le
adb shell run-as "$PACKAGE" cp "$REMOTE_TMP" files/decoder.pte
adb shell rm -f "$REMOTE_TMP"
adb push "$ARTIFACT_DIR/input.f32le" /data/local/tmp/vibevoice-decoder-input.f32le >/dev/null
adb shell chmod 0644 /data/local/tmp/vibevoice-decoder-input.f32le
adb shell run-as "$PACKAGE" cp /data/local/tmp/vibevoice-decoder-input.f32le files/input.f32le
adb shell rm -f /data/local/tmp/vibevoice-decoder-input.f32le

"$PYTHON" - <<'PY' >"$ARTIFACT_DIR/device-properties.json"
import json, subprocess
def prop(name):
    return subprocess.check_output(["adb", "shell", "getprop", name], text=True).strip()
print(json.dumps({
    "manufacturer": prop("ro.product.manufacturer"),
    "model": prop("ro.product.model"),
    "device": prop("ro.product.device"),
    "soc": prop("ro.soc.model"),
    "android_release": prop("ro.build.version.release"),
    "api_level": int(prop("ro.build.version.sdk")),
    "abi": prop("ro.product.cpu.abi"),
}, indent=2))
PY

adb logcat -c
adb shell am force-stop "$PACKAGE"
adb shell am start -W -n "$COMPONENT" | tee "$ARTIFACT_DIR/activity-start.log"
COMPLETE=false
for _ in $(seq 1 180); do
  if adb shell run-as "$PACKAGE" test -f files/result.json; then
    COMPLETE=true
    break
  fi
  sleep 1
done
adb logcat -d -s VibeVoiceProbe:V ExecuTorch:V '*:S' >"$ARTIFACT_DIR/logcat.txt" || true
if [[ "$COMPLETE" != true ]]; then
  echo "Probe did not produce result.json within 180 seconds" >&2
  exit 1
fi
adb exec-out run-as "$PACKAGE" cat files/result.json >"$ARTIFACT_DIR/device-result.json"
cat "$ARTIFACT_DIR/device-result.json"
if [[ $("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$ARTIFACT_DIR/device-result.json") != passed ]]; then
  echo "Android probe reported failure; see $ARTIFACT_DIR/logcat.txt" >&2
  exit 1
fi
adb exec-out run-as "$PACKAGE" cat files/output.f32le >"$ARTIFACT_DIR/output.f32le"
"$PYTHON" "$EXPORT_DIR/android_io.py" compare \
  "$REFERENCE" "$ARTIFACT_DIR/device-result.json" "$ARTIFACT_DIR/output.f32le" \
  "$ARTIFACT_DIR/comparison.json" --device-properties "$ARTIFACT_DIR/device-properties.json"

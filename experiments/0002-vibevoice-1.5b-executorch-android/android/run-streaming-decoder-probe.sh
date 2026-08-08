#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
ANDROID_DIR="$ROOT/experiments/0002-vibevoice-1.5b-executorch-android/android"
EXPORT_DIR="$ROOT/experiments/0002-vibevoice-1.5b-executorch-android/export"
ARTIFACT_DIR="$ROOT/artifacts/0002/android-streaming-decoder-probe"
FIRST_DIR=${FIRST_DIR:-"$ROOT/artifacts/0002/acoustic-decoder-streaming-first-segments-1.2"}
CACHED_DIR=${CACHED_DIR:-"$ROOT/artifacts/0002/acoustic-decoder-streaming-cached-segments-1.2"}
PYTHON=${PYTHON:-"$ROOT/artifacts/venv-executorch-1.2/bin/python"}
GRADLE=${GRADLE:-"$ROOT/artifacts/tools/gradle-8.10.2/bin/gradle"}
export ANDROID_HOME=${ANDROID_HOME:-/home/moritz/Android/Sdk}
export ANDROID_SDK_ROOT="$ANDROID_HOME"
PACKAGE=dev.moket.vibevoiceprobe
COMPONENT="$PACKAGE/.StreamingProbeActivity"
REMOTE_ROOT=/data/local/tmp/vibevoice-streaming-decoder

mkdir -p "$ARTIFACT_DIR/input" "$ARTIFACT_DIR/device-output"
"$PYTHON" "$EXPORT_DIR/streaming_android_io.py" prepare \
  "$FIRST_DIR" "$CACHED_DIR" "$ARTIFACT_DIR/input" >"$ARTIFACT_DIR/input-metadata.json"

(
  cd "$ANDROID_DIR"
  "$GRADLE" --no-daemon :app:assembleDebug
) | tee "$ARTIFACT_DIR/build.log"
APK="$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk"
adb install -r -t "$APK" | tee "$ARTIFACT_DIR/install.log"

adb shell mkdir -p "$REMOTE_ROOT/first" "$REMOTE_ROOT/cached"
adb shell chmod 0755 "$REMOTE_ROOT" "$REMOTE_ROOT/first" "$REMOTE_ROOT/cached"
for entry in first cached; do
  source_dir="$FIRST_DIR"
  [[ "$entry" == cached ]] && source_dir="$CACHED_DIR"
  for segment in $(seq 0 7); do
    source_file="$source_dir/segment-$segment.pte"
    remote_file="$REMOTE_ROOT/$entry/segment-$segment.pte"
    local_bytes=$(stat -c %s "$source_file")
    remote_bytes=$(adb shell stat -c %s "$remote_file" 2>/dev/null | tr -d '\r' || true)
    if [[ "$local_bytes" != "$remote_bytes" ]]; then
      echo "Uploading $entry segment $segment ($local_bytes bytes)"
      adb push "$source_file" "$remote_file" | tee "$ARTIFACT_DIR/push-$entry-segment-$segment.log"
    else
      echo "Reusing $remote_file ($remote_bytes bytes)"
    fi
    adb shell chmod 0644 "$remote_file"
  done
done

adb shell run-as "$PACKAGE" mkdir -p files/streaming-input
adb shell run-as "$PACKAGE" rm -rf files/streaming-output files/streaming-result.json
for call in 0 1; do
  temporary="/data/local/tmp/vibevoice-streaming-call-$call.f32le"
  adb push "$ARTIFACT_DIR/input/call-$call.f32le" "$temporary" >/dev/null
  adb shell chmod 0644 "$temporary"
  adb shell run-as "$PACKAGE" cp "$temporary" "files/streaming-input/call-$call.f32le"
  adb shell rm -f "$temporary"
done

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
for _ in $(seq 1 1800); do
  if adb shell run-as "$PACKAGE" test -f files/streaming-result.json; then
    COMPLETE=true
    break
  fi
  sleep 1
done
adb logcat -d -s VibeVoiceStreaming:V ExecuTorch:V '*:S' >"$ARTIFACT_DIR/logcat.txt" || true
if [[ "$COMPLETE" != true ]]; then
  echo "Streaming probe did not produce result.json within 1800 seconds" >&2
  exit 1
fi
adb exec-out run-as "$PACKAGE" cat files/streaming-result.json >"$ARTIFACT_DIR/device-result.json"
cat "$ARTIFACT_DIR/device-result.json"
if [[ $("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$ARTIFACT_DIR/device-result.json") != passed ]]; then
  echo "Android probe reported failure; see $ARTIFACT_DIR/logcat.txt" >&2
  exit 1
fi
rm -rf "$ARTIFACT_DIR/device-output"
mkdir -p "$ARTIFACT_DIR/device-output"
adb exec-out run-as "$PACKAGE" tar -C files/streaming-output -cf - . \
  | tar -C "$ARTIFACT_DIR/device-output" -xf -
"$PYTHON" "$EXPORT_DIR/streaming_android_io.py" compare \
  "$FIRST_DIR" "$CACHED_DIR" \
  "$ARTIFACT_DIR/device-result.json" "$ARTIFACT_DIR/device-output" \
  "$ARTIFACT_DIR/comparison.json" \
  --device-properties "$ARTIFACT_DIR/device-properties.json" \
  | tee "$ARTIFACT_DIR/comparison.log"

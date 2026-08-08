#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
ANDROID_DIR="$ROOT/experiments/0002-vibevoice-1.5b-executorch-android/android"
EXPORT_DIR="$ROOT/experiments/0002-vibevoice-1.5b-executorch-android/export"
ARTIFACT_DIR=${ARTIFACT_DIR:-"$ROOT/artifacts/0002/lane-b/diffusion-android"}
MODEL=${MODEL:-"$ROOT/artifacts/0002/lane-b/diffusion-head/diffusion-step-xnnpack.pte"}
REFERENCE=${REFERENCE:-"${MODEL%.pte}.reference.pt"}
LOOP_REFERENCE=${LOOP_REFERENCE:-"$ARTIFACT_DIR/diffusion-loop.reference.pt"}
PYTHON=${PYTHON:-"$ROOT/.venv/bin/python"}
EXECUTORCH_PYTHON=${EXECUTORCH_PYTHON:-"$ROOT/artifacts/venv-executorch-1.2/bin/python"}
GRADLE=${GRADLE:-"$ROOT/artifacts/tools/gradle-8.10.2/bin/gradle"}
export ANDROID_HOME=${ANDROID_HOME:-/home/moritz/Android/Sdk}
export ANDROID_SDK_ROOT="$ANDROID_HOME"
PACKAGE=dev.moket.vibevoiceprobe
COMPONENT="$PACKAGE/.DiffusionProbeActivity"
REMOTE_TMP=/data/local/tmp/vibevoice-diffusion.pte

mkdir -p "$ARTIFACT_DIR"
if [[ ! -f "$LOOP_REFERENCE" ]]; then
  "$EXECUTORCH_PYTHON" "$EXPORT_DIR/validate_diffusion_loop.py" "$MODEL" \
    --reference "$REFERENCE" --fixture-output "$LOOP_REFERENCE" \
    --result-output "$ARTIFACT_DIR/host-loop-result.json" \
    | tee "$ARTIFACT_DIR/host-loop.log"
fi
"$PYTHON" "$EXPORT_DIR/diffusion_android_io.py" prepare \
  "$REFERENCE" "$LOOP_REFERENCE" "$ARTIFACT_DIR"

(
  cd "$ANDROID_DIR"
  "$GRADLE" --no-daemon :app:assembleDebug
) | tee "$ARTIFACT_DIR/build.log"
APK="$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk"
adb install -r -t "$APK" | tee "$ARTIFACT_DIR/install.log"

adb push "$MODEL" "$REMOTE_TMP" | tee "$ARTIFACT_DIR/push-model.log"
adb shell chmod 0644 "$REMOTE_TMP"
adb shell run-as "$PACKAGE" mkdir -p files
adb shell run-as "$PACKAGE" rm -f files/diffusion-result.json files/one-step-output.f32le files/loop-output.f32le
adb shell run-as "$PACKAGE" cp "$REMOTE_TMP" files/diffusion.pte
adb shell rm -f "$REMOTE_TMP"
for input in latent.f32le positive-condition.f32le negative-condition.f32le timesteps.f32le sigmas.f32le; do
  adb push "$ARTIFACT_DIR/$input" "/data/local/tmp/$input" >/dev/null
  adb shell chmod 0644 "/data/local/tmp/$input"
  adb shell run-as "$PACKAGE" cp "/data/local/tmp/$input" "files/$input"
  adb shell rm -f "/data/local/tmp/$input"
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
for _ in $(seq 1 600); do
  if adb shell run-as "$PACKAGE" test -f files/diffusion-result.json; then
    COMPLETE=true
    break
  fi
  sleep 1
done
adb logcat -d -s VibeVoiceDiffusion:V ExecuTorch:V '*:S' >"$ARTIFACT_DIR/logcat.txt" || true
if [[ "$COMPLETE" != true ]]; then
  echo "Diffusion probe did not finish within 600 seconds" >&2
  exit 1
fi
adb exec-out run-as "$PACKAGE" cat files/diffusion-result.json >"$ARTIFACT_DIR/device-result.json"
cat "$ARTIFACT_DIR/device-result.json"
if [[ $("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$ARTIFACT_DIR/device-result.json") != passed ]]; then
  echo "Android diffusion probe reported failure; see $ARTIFACT_DIR/logcat.txt" >&2
  exit 1
fi
adb exec-out run-as "$PACKAGE" cat files/one-step-output.f32le >"$ARTIFACT_DIR/one-step-output.f32le"
adb exec-out run-as "$PACKAGE" cat files/loop-output.f32le >"$ARTIFACT_DIR/loop-output.f32le"
"$PYTHON" "$EXPORT_DIR/diffusion_android_io.py" compare \
  "$REFERENCE" "$LOOP_REFERENCE" "$ARTIFACT_DIR/device-result.json" \
  "$ARTIFACT_DIR/one-step-output.f32le" "$ARTIFACT_DIR/loop-output.f32le" \
  "$ARTIFACT_DIR/comparison.json" --device-properties "$ARTIFACT_DIR/device-properties.json"

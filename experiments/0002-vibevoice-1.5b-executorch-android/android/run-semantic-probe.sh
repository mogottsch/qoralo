#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
BASE="$ROOT/experiments/0002-vibevoice-1.5b-executorch-android"
ANDROID_DIR="$BASE/android"
MODEL_DIR=${MODEL_DIR:-"$ROOT/artifacts/0002/lane-b/semantic-encoder"}
CONNECTOR_DIR=${CONNECTOR_DIR:-"$ROOT/artifacts/0002/lane-b/connectors"}
FIXTURE_DIR=${FIXTURE_DIR:-"$ROOT/artifacts/0002/lane-b/semantic-android-fixture"}
ARTIFACT_DIR=${ARTIFACT_DIR:-"$ROOT/artifacts/0002/lane-b/semantic-android"}
PYTHON=${PYTHON:-"$ROOT/artifacts/venv-executorch-1.2/bin/python"}
GRADLE=${GRADLE:-"$ROOT/artifacts/tools/gradle-8.10.2/bin/gradle"}
export ANDROID_HOME=${ANDROID_HOME:-/home/moritz/Android/Sdk}
export ANDROID_SDK_ROOT="$ANDROID_HOME"
PACKAGE=dev.moket.vibevoiceprobe
COMPONENT="$PACKAGE/.SemanticProbeActivity"

FIRST="$MODEL_DIR/semantic-encoder-first-xnnpack.pte"
CACHED="$MODEL_DIR/semantic-encoder-cached-xnnpack.pte"
CONNECTOR="$CONNECTOR_DIR/connectors-xnnpack.pte"
SEMANTIC_FIXTURE="$MODEL_DIR/capture-1/fixture.pt"
CONNECTOR_FIXTURE="$CONNECTOR_DIR/capture-1/fixture.pt"
mkdir -p "$ARTIFACT_DIR" "$FIXTURE_DIR"
for file in "$FIRST" "$CACHED" "$CONNECTOR" "$SEMANTIC_FIXTURE" "$CONNECTOR_FIXTURE"; do
  [[ -s "$file" ]] || { echo "Missing required artifact: $file" >&2; exit 2; }
done

mapfile -t ADB_ROWS < <(adb devices | awk 'NR > 1 && NF {print $1 " " $2}')
[[ ${#ADB_ROWS[@]} -eq 1 && "${ADB_ROWS[0]}" == *" device" ]] || {
  printf 'phone preflight failed: expected one authorized device, got %s\n' "${ADB_ROWS[*]:-none}" >&2; exit 2;
}
[[ $(adb shell getprop ro.product.model | tr -d '\r') == SM-S918B ]] || { echo "wrong target device" >&2; exit 2; }

"$PYTHON" "$BASE/export/semantic_android_io.py" prepare "$FIXTURE_DIR" \
  --semantic-fixture "$SEMANTIC_FIXTURE" --connector-fixture "$CONNECTOR_FIXTURE" --connector-pte "$CONNECTOR" \
  > "$ARTIFACT_DIR/prepare.log"
(cd "$ANDROID_DIR" && "$GRADLE" --no-daemon :app:assembleDebug) | tee "$ARTIFACT_DIR/build.log"
adb install -r -t "$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk" | tee "$ARTIFACT_DIR/install.log"
adb shell run-as "$PACKAGE" mkdir -p files/semantic-models files/semantic-input
adb shell run-as "$PACKAGE" rm -f 'files/run-*-call-*.f32le' files/semantic-result.json

push_private() {
  local source=$1
  local destination=$2
  local temporary="/data/local/tmp/semantic-$(basename "$destination")"
  adb push "$source" "$temporary" >/dev/null
  adb shell chmod 0644 "$temporary"
  adb shell run-as "$PACKAGE" cp "$temporary" "$destination"
  adb shell rm -f "$temporary"
}
push_private "$FIRST" files/semantic-models/semantic-encoder-first-xnnpack.pte
push_private "$CACHED" files/semantic-models/semantic-encoder-cached-xnnpack.pte
push_private "$CONNECTOR" files/semantic-models/connectors-xnnpack.pte
push_private "$FIXTURE_DIR/call-0-audio.f32le" files/semantic-input/call-0-audio.f32le
push_private "$FIXTURE_DIR/call-1-audio.f32le" files/semantic-input/call-1-audio.f32le
push_private "$FIXTURE_DIR/acoustic.f32le" files/semantic-input/acoustic.f32le

"$PYTHON" - <<'PY' > "$ARTIFACT_DIR/device-properties.json"
import json,subprocess
def p(name): return subprocess.check_output(["adb","shell","getprop",name],text=True).strip()
print(json.dumps({"manufacturer":p("ro.product.manufacturer"),"model":p("ro.product.model"),
 "device":p("ro.product.device"),"soc":p("ro.soc.model"),"android_release":p("ro.build.version.release"),
 "api_level":int(p("ro.build.version.sdk")),"abi":p("ro.product.cpu.abi"),
 "build_fingerprint":p("ro.build.fingerprint"),"kernel":subprocess.check_output(
 ["adb","shell","uname","-a"],text=True).strip()},indent=2))
PY
adb shell svc power stayon usb >/dev/null
adb logcat -c
adb shell am force-stop "$PACKAGE"
adb shell am start -W -n "$COMPONENT" | tee "$ARTIFACT_DIR/activity-start.log"
complete=false
for _ in $(seq 1 900); do
  if adb shell run-as "$PACKAGE" test -f files/semantic-result.json; then complete=true; break; fi
  sleep 1
done
adb logcat -d -s VibeVoiceSemantic:V ExecuTorch:V '*:S' > "$ARTIFACT_DIR/logcat.txt" || true
[[ "$complete" == true ]] || { echo "semantic probe timed out" >&2; exit 4; }
adb exec-out run-as "$PACKAGE" cat files/semantic-result.json > "$ARTIFACT_DIR/device-result.json"
cat "$ARTIFACT_DIR/device-result.json"
[[ $("$PYTHON" -c 'import json,sys;print(json.load(open(sys.argv[1]))["status"])' "$ARTIFACT_DIR/device-result.json") == passed ]] || exit 5
for run in 0 1; do
  for call in 0 1; do
    for kind in features embedding; do
      adb exec-out run-as "$PACKAGE" cat "files/run-$run-call-$call-$kind.f32le" > "$ARTIFACT_DIR/run-$run-call-$call-$kind.f32le"
    done
    for cache in $(seq -w 0 33); do
      adb exec-out run-as "$PACKAGE" cat "files/run-$run-call-$call-cache-$cache.f32le" > "$ARTIFACT_DIR/run-$run-call-$call-cache-$cache.f32le"
    done
  done
done
RESULT="$BASE/results/semantic-path-android.json"
"$PYTHON" "$BASE/export/semantic_android_io.py" compare "$FIXTURE_DIR" "$ARTIFACT_DIR" \
  "$ARTIFACT_DIR/device-result.json" "$ARTIFACT_DIR/device-properties.json" "$RESULT" \
  --implementation-commit "$(git rev-parse HEAD)"
cp "$RESULT" "$ARTIFACT_DIR/comparison.json"

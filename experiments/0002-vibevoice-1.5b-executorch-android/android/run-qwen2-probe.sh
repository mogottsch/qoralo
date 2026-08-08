#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
BASE="$ROOT/experiments/0002-vibevoice-1.5b-executorch-android"
ANDROID_DIR="$BASE/android"
EXPORT_DIR="$BASE/export"
PACKAGE_DIR=${PACKAGE_DIR:-"$ROOT/artifacts/0002/lane-c/qwen2-prefill-android-package"}
FIXTURE_DIR=${FIXTURE_DIR:-"$ROOT/artifacts/0002/lane-c/qwen2-fixtures"}
ARTIFACT_DIR=${ARTIFACT_DIR:-"$ROOT/artifacts/0002/lane-c/qwen2-prefill-android"}
PYTHON=${PYTHON:-"$ROOT/.venv/bin/python"}
GRADLE=${GRADLE:-"$ROOT/artifacts/tools/gradle-8.10.2/bin/gradle"}
export ANDROID_HOME=${ANDROID_HOME:-/home/moritz/Android/Sdk}
export ANDROID_SDK_ROOT="$ANDROID_HOME"
PACKAGE=dev.moket.vibevoiceprobe
COMPONENT="$PACKAGE/.Qwen2PrefillProbeActivity"
MIN_MEMORY_BYTES=2800000000

mkdir -p "$ARTIFACT_DIR"
# Fail before building or transferring 6.18 GB. An unauthorized/locked phone is a
# physical-input blocker, not something this long-running probe should retry.
mapfile -t ADB_ROWS < <(adb devices | awk 'NR > 1 && NF {print $1 " " $2}')
[[ ${#ADB_ROWS[@]} -eq 1 && "${ADB_ROWS[0]}" == *" device" ]] || {
  printf 'phone preflight failed: expected exactly one authorized device, got: %s\n' "${ADB_ROWS[*]:-none}" >&2
  exit 2
}
[[ $(adb shell getprop ro.product.model | tr -d '\r') == SM-S918B ]] || {
  echo "phone preflight failed: target is not the pinned Galaxy S23 Ultra (SM-S918B)" >&2
  exit 2
}
WINDOW_STATE=$(adb shell dumpsys window | tr -d '\r')
if grep -Eq 'mDreamingLockscreen=true|mShowingLockscreen=true|isStatusBarKeyguard=true' <<<"$WINDOW_STATE"; then
  echo "phone preflight blocked: unlock the Galaxy S23 Ultra, then rerun" >&2
  exit 2
fi
[[ -f "$PACKAGE_DIR/manifest.json" ]] || { echo "Missing host-validated package manifest" >&2; exit 2; }
"$PYTHON" - "$PACKAGE_DIR/manifest.json" <<'PY'
import hashlib,json,pathlib,sys
p=pathlib.Path(sys.argv[1]); d=json.loads(p.read_text())
assert d["status"] == "passed" and d["stage_count"] == 60
assert d["host_revalidation"]["prefill"]["acceptance"]["bounded_xnnpack_accepted"]
assert d["host_revalidation"]["decode_from_prefill_outputs"]["acceptance"]["bounded_xnnpack_accepted"]
assert d["host_revalidation"]["decode_from_prefill_outputs"]["cache_source"] == "packaged_prefill_stage_outputs"
for stage in d["stages"]:
 f=p.parent/stage["file"]
 assert f.stat().st_size == stage["bytes"]
 assert hashlib.sha256(f.read_bytes()).hexdigest() == stage["sha256"]
print(f"host package accepted: {d['total_bytes']} bytes; largest stage {d['largest_stage_bytes']} bytes")
PY
"$PYTHON" "$EXPORT_DIR/qwen2_android_io.py" prepare "$FIXTURE_DIR" "$ARTIFACT_DIR"

adb get-state >/dev/null
# This probe can run for many minutes; USB-powered stay-awake avoids a suspended
# activity turning a valid but slow full prefill into an apparent timeout.
adb shell svc power stayon usb >/dev/null
PACKAGE_BYTES=$("$PYTHON" -c 'import json,sys;print(json.load(open(sys.argv[1]))["total_bytes"])' "$PACKAGE_DIR/manifest.json")
DEVICE_FREE=$(adb shell df -k /data/user/0 | tail -1 | awk '{print $4 * 1024}')
MEM_AVAILABLE=$(adb shell cat /proc/meminfo | tr -d '\r' | awk '/MemAvailable:/{print $2 * 1024}')
if (( DEVICE_FREE < PACKAGE_BYTES + 1000000000 )); then echo "storage preflight failed" >&2; exit 3; fi
if (( MEM_AVAILABLE < MIN_MEMORY_BYTES )); then echo "memory preflight failed: unlock/close apps; MemAvailable=$MEM_AVAILABLE" >&2; exit 4; fi
printf '{"package_bytes":%s,"device_free_bytes":%s,"mem_available_bytes":%s,"minimum_mem_available_bytes":%s}\n' \
  "$PACKAGE_BYTES" "$DEVICE_FREE" "$MEM_AVAILABLE" "$MIN_MEMORY_BYTES" > "$ARTIFACT_DIR/preflight.json"

(cd "$ANDROID_DIR" && "$GRADLE" --no-daemon :app:assembleDebug) | tee "$ARTIFACT_DIR/build.log"
adb install -r -t "$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk" | tee "$ARTIFACT_DIR/install.log"
adb shell run-as "$PACKAGE" mkdir -p files/qwen2-package
adb shell run-as "$PACKAGE" rm -f 'files/qwen2-package/*' 'files/prefill-output-*.f32le' 'files/decode-output-*.f32le' files/qwen2-decode-result.json
for model in prepare.pte layer-{00..27}.pte final.pte decode-prepare.pte decode-layer-{00..27}.pte decode-final.pte; do
  adb push "$PACKAGE_DIR/$model" "/data/local/tmp/$model" > "$ARTIFACT_DIR/push-$model.log"
  adb shell chmod 0644 "/data/local/tmp/$model"
  adb shell run-as "$PACKAGE" cp "/data/local/tmp/$model" "files/qwen2-package/$model"
  adb shell rm -f "/data/local/tmp/$model"
done
adb push "$PACKAGE_DIR/manifest.json" /data/local/tmp/qwen2-package-manifest.json >/dev/null
adb shell chmod 0644 /data/local/tmp/qwen2-package-manifest.json
adb shell run-as "$PACKAGE" cp /data/local/tmp/qwen2-package-manifest.json files/qwen2-package/manifest.json
adb shell rm -f /data/local/tmp/qwen2-package-manifest.json
for input in prefill-inputs-embeds.f32le prefill-attention-mask.i64le prefill-position-ids.i64le prefill-cache-position.i64le decode-inputs-embeds.f32le decode-attention-mask.i64le decode-position-ids.i64le decode-cache-position.i64le; do
  adb push "$ARTIFACT_DIR/$input" "/data/local/tmp/$input" >/dev/null
  adb shell chmod 0644 "/data/local/tmp/$input"
  adb shell run-as "$PACKAGE" cp "/data/local/tmp/$input" "files/$input"
  adb shell rm -f "/data/local/tmp/$input"
done

"$PYTHON" - <<'PY' > "$ARTIFACT_DIR/device-properties.json"
import json,subprocess
def p(n): return subprocess.check_output(["adb","shell","getprop",n],text=True).strip()
print(json.dumps({"manufacturer":p("ro.product.manufacturer"),"model":p("ro.product.model"),
 "device":p("ro.product.device"),"soc":p("ro.soc.model"),"android_release":p("ro.build.version.release"),
 "api_level":int(p("ro.build.version.sdk")),"abi":p("ro.product.cpu.abi"),
 "build_fingerprint":p("ro.build.fingerprint"),"kernel":subprocess.check_output(
 ["adb","shell","uname","-a"],text=True).strip()},indent=2))
PY
adb logcat -c
adb shell am force-stop "$PACKAGE"
adb shell am start -W -n "$COMPONENT" | tee "$ARTIFACT_DIR/activity-start.log"
COMPLETE=false
for _ in $(seq 1 3600); do
  if adb shell run-as "$PACKAGE" test -f files/qwen2-decode-result.json; then COMPLETE=true; break; fi
  sleep 1
done
adb logcat -d -s VibeVoiceQwen2:V ExecuTorch:V '*:S' > "$ARTIFACT_DIR/logcat.txt" || true
[[ "$COMPLETE" == true ]] || { echo "Qwen2 probe timed out" >&2; exit 5; }
adb exec-out run-as "$PACKAGE" cat files/qwen2-decode-result.json > "$ARTIFACT_DIR/device-result.json"
cat "$ARTIFACT_DIR/device-result.json"
[[ $("$PYTHON" -c 'import json,sys;print(json.load(open(sys.argv[1]))["status"])' "$ARTIFACT_DIR/device-result.json") == passed ]] || exit 6
for phase in prefill decode; do
  for index in $(seq -w 0 57); do
    adb exec-out run-as "$PACKAGE" cat "files/$phase-output-$index.f32le" > "$ARTIFACT_DIR/$phase-output-$index.f32le"
  done
done
RESULT="$BASE/results/qwen2-decode-android.json"
"$PYTHON" "$EXPORT_DIR/qwen2_android_io.py" compare "$FIXTURE_DIR" "$ARTIFACT_DIR" \
  "$ARTIFACT_DIR/device-result.json" "$RESULT" \
  --package-manifest "$PACKAGE_DIR/manifest.json" \
  --device-properties "$ARTIFACT_DIR/device-properties.json" \
  --preflight "$ARTIFACT_DIR/preflight.json" \
  --implementation-commit "$(git rev-parse HEAD)"
cp "$RESULT" "$ARTIFACT_DIR/comparison.json"

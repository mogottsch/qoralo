#!/usr/bin/env bash
set -euo pipefail
[[ ${PHONE_USE_CONFIRMED:-} == yes ]] || { echo 'PHONE_USE_CONFIRMED=yes is required' >&2; exit 2; }
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
EXP="$REPO/experiments/0013-kokoro-onnx-vs-executorch-android"
ADB="/mnt/c/Users/mgottschling/AppData/Local/Android/platform-tools-pi/platform-tools/adb.exe"
SERIAL=R5CW81PR8SY
PACKAGE=dev.moket.kokorocompare
ACTIVITY="$PACKAGE/.BenchmarkActivity"
MODEL="$EXP/.local/derived/kokoro-official-v1.0-fp32-controlled-t125.onnx"
VOICE="$EXP/.local/derived/af_heart.f32"
ROOT="$EXP/.local/source/sherpa/extracted/kokoro-multi-lang-v1_0"
APK="$EXP/android/app/build/outputs/apk/debug/app-debug.apk"
RUN_ID="onnx-cpu-$(date -u +%Y%m%dT%H%M%SZ)-$$"
REMOTE="/data/local/tmp/experiment-0013-kokoro-$RUN_ID"
EXTERNAL="/sdcard/Android/data/$PACKAGE/files"
OUT="$EXP/work/phone/$RUN_ID"
mkdir -p "$OUT" "$REPO/artifacts/locks"
[[ -x "$ADB" ]] || { echo "missing Windows adb.exe: $ADB" >&2; exit 2; }

exec 9>"$REPO/artifacts/locks/phone.lock"
echo "$(date -u +%FT%TZ) waiting" >"$OUT/lock-state.txt"
flock -w 1800 9 || { echo "phone lock timeout" >&2; exit 3; }
echo "$(date -u +%FT%TZ) acquired" >>"$OUT/lock-state.txt"
export ADB_LIBUSB=1
adb(){ "$ADB" -s "$SERIAL" "$@" </dev/null 9>&-; }
cleanup(){
  local rc=$?;set +e
  adb shell "am force-stop '$PACKAGE' >/dev/null 2>&1 || true; run-as '$PACKAGE' rm -rf files/input >/dev/null 2>&1 || true; rm -rf '$REMOTE' '$EXTERNAL'" >"$OUT/cleanup.stdout.log" 2>"$OUT/cleanup.stderr.log"
  local cleanup_rc=$?
  adb uninstall "$PACKAGE" >>"$OUT/cleanup.stdout.log" 2>>"$OUT/cleanup.stderr.log"
  local uninstall_rc=$?
  adb shell "test ! -e '$REMOTE' && test ! -e '$EXTERNAL' && ! pm path '$PACKAGE' 2>/dev/null | grep -q '^package:'" >>"$OUT/cleanup.stdout.log" 2>>"$OUT/cleanup.stderr.log"
  local verify_rc=$?
  printf 'command_rc=%s\ncleanup_rc=%s\nuninstall_rc=%s\nverify_absent_rc=%s\n' "$rc" "$cleanup_rc" "$uninstall_rc" "$verify_rc" >"$OUT/cleanup-status.txt"
  echo "$(date -u +%FT%TZ) released" >>"$OUT/lock-state.txt"
  exit "$rc"
}
trap cleanup EXIT INT TERM

"$ADB" devices -l 9>&- >"$OUT/devices.txt"
mapfile -t devices < <("$ADB" devices 9>&- | tr -d '\r' | awk 'NR>1 && $2=="device" {print $1}')
[[ ${#devices[@]} == 1 && ${devices[0]} == "$SERIAL" ]] || { echo "authorized phone is not the sole connected device" >&2; exit 4; }
{
  echo "serial=$(adb get-serialno | tr -d '\r')"
  echo "model=$(adb shell getprop ro.product.model | tr -d '\r')"
  echo "soc=$(adb shell getprop ro.soc.model | tr -d '\r')"
  echo "abi=$(adb shell getprop ro.product.cpu.abi | tr -d '\r')"
  echo "boot=$(adb shell getprop sys.boot_completed | tr -d '\r')"
} >"$OUT/identity.txt"
grep -Fxq "serial=$SERIAL" "$OUT/identity.txt"
grep -Fxq 'model=SM-S918B' "$OUT/identity.txt"
grep -Fxq 'soc=SM8550' "$OUT/identity.txt"
grep -Fxq 'abi=arm64-v8a' "$OUT/identity.txt"
grep -Fxq 'boot=1' "$OUT/identity.txt"

sha256sum "$MODEL" "$VOICE" "$ROOT/tokens.txt" "$ROOT/lexicon-us-en.txt" "$EXP/protocol/transcript.txt" "$EXP/protocol/deployment-fidelity-policy.json" "$APK" >"$OUT/host-stage-sha256.txt"
adb shell "mkdir '$REMOTE'"
adb push "$APK" "$REMOTE/app-debug.apk" >"$OUT/push-apk.log"
adb push "$MODEL" "$REMOTE/model.onnx" >"$OUT/push-model.log"
adb push "$VOICE" "$REMOTE/af_heart.f32" >"$OUT/push-voice.log"
adb push "$ROOT/tokens.txt" "$REMOTE/tokens.txt" >"$OUT/push-tokens.log"
adb push "$ROOT/lexicon-us-en.txt" "$REMOTE/lexicon-us-en.txt" >"$OUT/push-lexicon.log"
adb push "$EXP/protocol/transcript.txt" "$REMOTE/transcript.txt" >"$OUT/push-transcript.log"
adb push "$EXP/protocol/deployment-fidelity-policy.json" "$REMOTE/deployment-fidelity-policy.json" >"$OUT/push-policy.log"
adb shell "cd '$REMOTE' && sha256sum app-debug.apk model.onnx af_heart.f32 tokens.txt lexicon-us-en.txt transcript.txt deployment-fidelity-policy.json" >"$OUT/remote-stage-sha256.txt"
adb install -r -t "$APK" >"$OUT/install.log"
APP_DATA="$(adb shell "run-as '$PACKAGE' pwd" | tr -d '\r')"
case "$APP_DATA" in
  "/data/user/0/$PACKAGE"|"/data/data/$PACKAGE") ;;
  *) echo "unexpected run-as data directory: $APP_DATA" >&2; exit 7;;
esac
printf 'app_data=%s\nstaging=adb-shell-read-to-run-as-app-owned-internal-write\n' "$APP_DATA" >"$OUT/app-owned-staging.txt"
adb shell "run-as '$PACKAGE' mkdir -p '$APP_DATA/files/input'"
stage_app_owned(){
  local remote_file=$1 name=$2
  # The shell reads only this experiment's already hash-verified staging file;
  # run-as performs the write as the debug app UID into its internal directory.
  adb shell "cat '$remote_file' | run-as '$PACKAGE' sh -c 'umask 077; cat > \"$APP_DATA/files/input/$name\"'"
}
stage_app_owned "$REMOTE/model.onnx" model.onnx
stage_app_owned "$REMOTE/af_heart.f32" af_heart.f32
stage_app_owned "$REMOTE/tokens.txt" tokens.txt
stage_app_owned "$REMOTE/lexicon-us-en.txt" lexicon-us-en.txt
stage_app_owned "$REMOTE/transcript.txt" transcript.txt
stage_app_owned "$REMOTE/deployment-fidelity-policy.json" deployment-fidelity-policy.json
adb shell "run-as '$PACKAGE' sh -c 'cd \"$APP_DATA/files/input\" && sha256sum model.onnx af_heart.f32 tokens.txt lexicon-us-en.txt transcript.txt deployment-fidelity-policy.json'" >"$OUT/app-input-sha256.txt"

adb shell "am force-stop '$PACKAGE'; am start -W -n '$ACTIVITY' --es campaign_id '$RUN_ID' --es route onnx" >"$OUT/am-start.txt"
complete=0
for _ in $(seq 1 450); do
  if adb shell "test -f '$EXTERNAL/results/$RUN_ID/result.json' -o -f '$EXTERNAL/results/$RUN_ID/failure.json'"; then complete=1;break;fi
  sleep 2
done
[[ $complete == 1 ]] || { echo "phone benchmark timeout" >&2; exit 5; }
mkdir -p "$OUT/pulled"
adb pull "$EXTERNAL/results/$RUN_ID/." "$OUT/pulled/" >"$OUT/pull.log"
[[ -f "$OUT/pulled/result.json" ]] || { echo "phone benchmark produced failure" >&2; [[ -f "$OUT/pulled/failure.json" ]] && cat "$OUT/pulled/failure.json" >&2; exit 6; }
python -m json.tool "$OUT/pulled/result.json" >/dev/null
grep -Fq '"status": "passed"' "$OUT/pulled/result.json"
sha256sum "$OUT/pulled/"* >"$OUT/pulled-sha256.txt"
printf '%s\n' "$RUN_ID" >"$EXP/.local/latest-phone-run-id.txt"
echo "phone ONNX CPU route passed: $OUT"

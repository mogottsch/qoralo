#!/usr/bin/env bash
set -euo pipefail
[[ ${PHONE_USE_CONFIRMED:-} == yes && ${PHONE_COORDINATION_CLEARED:-} == yes ]] || {
  echo set_PHONE_USE_CONFIRMED_and_PHONE_COORDINATION_CLEARED >&2
  exit 2
}
ARM=${ARM:-}
PHYSICAL_PROOF=${PHYSICAL_PROOF:-no}
[[ $ARM == source || $ARM == context ]] || { echo ARM_must_be_source_or_context >&2; exit 2; }
[[ $PHYSICAL_PROOF == yes || $PHYSICAL_PROOF == no ]] || exit 2
SERIAL=R5CW81PR8SY
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
EXP="$ROOT/experiments/0024-pocket-tts-qnn-precompiled-context-startup"
STAGE="$EXP/.local/android-stage-$ARM"
MANIFEST="$EXP/.local/android-stage-$ARM.sha256"
ADB=${ADB:-/usr/bin/adb}
EXPECTED_ADB_SHA256=506163fd859265bc895b64eeba28252fb0f7864decf8b42dac3cbf9711240f9f
[[ $ADB == /usr/bin/adb && -f $ADB && -x $ADB && ! -L $ADB && $(realpath "$ADB") == "$ADB" ]] || {
  echo authorized_native_adb_identity_failed >&2
  exit 2
}
[[ $(sha256sum "$ADB" | awk '{print $1}') == "$EXPECTED_ADB_SHA256" ]] || {
  echo authorized_native_adb_hash_failed >&2
  exit 2
}
unset ADB_LIBUSB
ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
TAG=$ARM
[[ $PHYSICAL_PROOF == yes ]] && TAG="$ARM-proof"
REMOTE="/data/local/tmp/experiment-0024-pocket-context-$TAG-$ID"
OUT="$EXP/work/phone-$TAG-$ID"
mkdir -p "$OUT" "$ROOT/artifacts/locks"
exec 9>>"$ROOT/artifacts/locks/phone.lock"
flock -n 9 || { echo phone_lock_busy >&2; exit 3; }
"$ADB" version </dev/null 9>&- >"$OUT/adb-version.txt"
grep -Fxq 'Android Debug Bridge version 1.0.41' "$OUT/adb-version.txt"
grep -Fxq 'Version 37.0.0-android-tools' "$OUT/adb-version.txt"
grep -Fxq 'Installed as /usr/bin/adb' "$OUT/adb-version.txt"
adb(){ "$ADB" -s "$SERIAL" "$@" </dev/null 9>&-; }
cleanup(){
  local rc
  if adb shell "rm -rf '$REMOTE'" >"$OUT/cleanup.stdout" 2>"$OUT/cleanup.stderr"; then rc=0; else rc=$?; fi
  printf '%s\n' "$rc" >"$OUT/cleanup.exit"
  return 0
}
verify_cleanup(){
  local transport_rc exists_rc status
  if adb get-state >"$OUT/cleanup-transport.stdout" 2>"$OUT/cleanup-transport.stderr"; then transport_rc=0; else transport_rc=$?; fi
  exists_rc=99
  if [[ $transport_rc == 0 ]]; then
    if adb shell test -e "$REMOTE" >"$OUT/cleanup-exists.stdout" 2>"$OUT/cleanup-exists.stderr"; then exists_rc=0; else exists_rc=$?; fi
  fi
  printf '%s\n' "$transport_rc" >"$OUT/cleanup-transport.exit"
  printf '%s\n' "$exists_rc" >"$OUT/cleanup-exists.exit"
  if status=$(python3 "$EXP/tools/classify_cleanup_status.py" "$transport_rc" "$exists_rc"); then :; else :; fi
  printf '%s\n' "$status" >"$OUT/cleanup-status.txt"
  case "$status" in
    verified_absent) echo cleanup_ok >"$OUT/cleanup-proof.txt"; return 0 ;;
    remote_present) echo cleanup_failed_remote_present >&2; return 5 ;;
    pending_device_reconnect) echo cleanup_pending_device_reconnect >"$OUT/cleanup-pending.txt"; return 6 ;;
    *) echo cleanup_verification_error >&2; return 7 ;;
  esac
}
on_exit(){
  local original_rc=$? verify_rc
  trap - EXIT
  cleanup
  if verify_cleanup; then verify_rc=0; else verify_rc=$?; fi
  if [[ $original_rc != 0 ]]; then exit "$original_rc"; fi
  exit "$verify_rc"
}
trap on_exit EXIT

LIST=$("$ADB" devices -l 9>&- | tr -d '\r')
printf '%s\n' "$LIST" >"$OUT/devices.txt"
mapfile -t DEVICES < <(printf '%s\n' "$LIST" | awk 'NR>1&&$2=="device"{print $1}')
[[ ${#DEVICES[@]} == 1 && ${DEVICES[0]} == "$SERIAL" ]] || exit 4
{
  echo serial=$(adb get-serialno | tr -d '\r')
  echo manufacturer=$(adb shell getprop ro.product.manufacturer | tr -d '\r')
  echo model=$(adb shell getprop ro.product.model | tr -d '\r')
  echo device=$(adb shell getprop ro.product.device | tr -d '\r')
  echo soc=$(adb shell getprop ro.soc.model | tr -d '\r')
  echo abi=$(adb shell getprop ro.product.cpu.abi | tr -d '\r')
  echo boot=$(adb shell getprop sys.boot_completed | tr -d '\r')
  echo verified_boot=$(adb shell getprop ro.boot.verifiedbootstate | tr -d '\r')
  echo flash_locked=$(adb shell getprop ro.boot.flash.locked | tr -d '\r')
} >"$OUT/identity.txt"
grep -Fxq serial=$SERIAL "$OUT/identity.txt"
grep -Fxq manufacturer=samsung "$OUT/identity.txt"
grep -Fxq model=SM-S918B "$OUT/identity.txt"
grep -Fxq device=dm3q "$OUT/identity.txt"
grep -Fxq soc=SM8550 "$OUT/identity.txt"
grep -Fxq abi=arm64-v8a "$OUT/identity.txt"
grep -Fxq boot=1 "$OUT/identity.txt"
grep -Fxq verified_boot=green "$OUT/identity.txt"
grep -Fxq flash_locked=1 "$OUT/identity.txt"
adb shell dumpsys thermalservice >"$OUT/thermal-before.txt" || true
adb shell "dumpsys battery | head -n 25" >"$OUT/battery-before.txt" || true

cp "$MANIFEST" "$OUT/local-stage-sha256.txt"
adb shell "mkdir -p '$REMOTE/outputs' '$REMOTE/profiles'"
adb push "$STAGE/." "$REMOTE/" >"$OUT/push.stdout" 2>"$OUT/push.stderr"
adb shell "chmod 755 '$REMOTE/pocket_context_benchmark_runner'; cd '$REMOTE'; find . -type f -exec sha256sum {} + | sort" | tr -d '\r' >"$OUT/remote-stage-sha256.txt"
diff -u "$OUT/local-stage-sha256.txt" "$OUT/remote-stage-sha256.txt"
if [[ $ARM == context ]]; then
  find "$STAGE/model" -maxdepth 1 -type f -printf '%f %s\n' | sort >"$OUT/context-model-inventory.txt"
  awk '$1 ~ /\.onnx$/ && $2 >= 65536 {exit 1} END {if (NR != 16) exit 1}' "$OUT/context-model-inventory.txt"
fi

PROFILE=-
WARM_RUNS=5
[[ $PHYSICAL_PROOF == yes ]] && { PROFILE="$REMOTE/profiles"; WARM_RUNS=0; }
BACKEND="$REMOTE/lib/libQnnHtp.so"
ENVIRONMENT="export LD_LIBRARY_PATH='$REMOTE/lib' ADSP_LIBRARY_PATH='$REMOTE/lib;/vendor/lib/rfsa/adsp;/vendor/dsp/cdsp;/system/lib/rfsa/adsp;/vendor/dsp'"
set +e
timeout 7200 "$ADB" -s "$SERIAL" shell "cd '$REMOTE' && $ENVIRONMENT && ./pocket_context_benchmark_runner '$REMOTE/model' '$REMOTE/assets/alba-flow-cache-v1.f32' '$REMOTE/assets/canonical-token-ids-64.i64' '$REMOTE/assets/numpy-randomstate-seed0-temp0p3-292x32.f32' '$REMOTE/outputs' '$PROFILE' '$BACKEND' 0.3 292 pocket-fixed-alba-text64-cache512-canonical-v2-0024-reconstruction-derivative '$WARM_RUNS' 160 163 '$ARM' >'$REMOTE/result.json' 2>'$REMOTE/result.stderr'" </dev/null 9>&-
run_rc=$?
set -e
printf '%s\n' "$run_rc" >"$OUT/runner.exit"
adb shell "cd '$REMOTE'; find outputs profiles -type f -exec sha256sum {} + | sort; sha256sum result.json result.stderr" | tr -d '\r' >"$OUT/remote-output-sha256.txt" || true
adb pull "$REMOTE/result.json" "$OUT/result.json" >/dev/null 2>&1 || true
adb pull "$REMOTE/result.stderr" "$OUT/result.stderr" >/dev/null 2>&1 || true
adb pull "$REMOTE/outputs" "$OUT/" >/dev/null 2>&1 || true
[[ $PHYSICAL_PROOF == yes ]] && adb pull "$REMOTE/profiles" "$OUT/" >/dev/null 2>&1 || true
adb shell dumpsys thermalservice >"$OUT/thermal-after.txt" || true
adb shell "dumpsys battery | head -n 25" >"$OUT/battery-after.txt" || true
trap - EXIT
cleanup
verify_cleanup
printf '%s\n' "$OUT"
[[ $run_rc == 0 ]] || exit "$run_rc"

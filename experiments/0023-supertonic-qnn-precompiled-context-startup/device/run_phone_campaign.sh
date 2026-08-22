#!/usr/bin/env bash
set -euo pipefail
[[ ${PHONE_CAMPAIGN_APPROVED:-no} == yes ]] || { echo "set PHONE_CAMPAIGN_APPROVED=yes only after preparation commit review" >&2; exit 2; }
ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0023-supertonic-qnn-precompiled-context-startup"
STAGE="$EXP/.local/phone-stage"
ADB=/usr/bin/adb
SERIAL=R5CW81PR8SY
EXPECTED_ADB_SHA=506163fd859265bc895b64eeba28252fb0f7864decf8b42dac3cbf9711240f9f
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
REMOTE="/data/local/tmp/vibevoice-0023-$RUN_ID"
OUT="$EXP/work/phone-$RUN_ID"
REMOTE_CREATED=0
mkdir -p "$OUT" "$ROOT/artifacts/locks"
exec 9>"$ROOT/artifacts/locks/phone.lock"
flock -n 9 || { echo "phone.lock unavailable" >&2; exit 3; }
unset ADB_LIBUSB
adb(){ "$ADB" -s "$SERIAL" "$@" </dev/null 9>&-; }
cleanup(){
  set +e
  if [[ $REMOTE_CREATED == 1 ]]; then
    adb shell "rm -rf '$REMOTE'" >"$OUT/cleanup.stdout.log" 2>"$OUT/cleanup.stderr.log"
    echo $? >"$OUT/cleanup.exit-code.txt"
    if adb shell "test ! -e '$REMOTE'" >"$OUT/cleanup-verify.stdout.log" 2>"$OUT/cleanup-verify.stderr.log"; then
      echo passed >"$OUT/cleanup-verification.txt"
    else
      echo failed >"$OUT/cleanup-verification.txt"
    fi
  else
    echo not_created >"$OUT/cleanup-verification.txt"
  fi
}
trap cleanup EXIT

[[ -x $ADB ]] || { echo "missing Linux adb" >&2; exit 4; }
[[ $(sha256sum "$ADB" | awk '{print $1}') == "$EXPECTED_ADB_SHA" ]] || { echo "adb hash mismatch" >&2; exit 4; }
[[ -f "$STAGE/stage-manifest.sha256" && -x "$STAGE/runner" ]] || { echo "phone stage absent" >&2; exit 5; }
if git status --porcelain --untracked-files=all -- "$EXP" | grep -q .; then
  echo "0023 tracked preparation is not committed/clean" >&2
  exit 6
fi
{
  echo "start_utc=$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
  echo "commit=$(git rev-parse HEAD)"
  echo "adb_sha256=$EXPECTED_ADB_SHA"
  "$ADB" version
} >"$OUT/campaign-start.txt"
"$ADB" devices -l 9>&- >"$OUT/devices.txt"
mapfile -t authorized < <("$ADB" devices 9>&- | awk 'NR>1 && NF>=2 && $2=="device" {print $1}')
mapfile -t any_devices < <("$ADB" devices 9>&- | awk 'NR>1 && NF>=2 {print $1":"$2}')
[[ ${#authorized[@]} == 1 && ${authorized[0]} == "$SERIAL" && ${#any_devices[@]} == 1 ]] || {
  printf 'device gate failed: authorized=%s all=%s\n' "${authorized[*]-}" "${any_devices[*]-}" >&2
  exit 7
}
{
  echo "serial=$(adb get-serialno | tr -d '\r')"
  echo "manufacturer=$(adb shell getprop ro.product.manufacturer | tr -d '\r')"
  echo "model=$(adb shell getprop ro.product.model | tr -d '\r')"
  echo "device=$(adb shell getprop ro.product.device | tr -d '\r')"
  echo "soc=$(adb shell getprop ro.soc.model | tr -d '\r')"
  echo "abi=$(adb shell getprop ro.product.cpu.abi | tr -d '\r')"
  echo "android_release=$(adb shell getprop ro.build.version.release | tr -d '\r')"
  echo "api=$(adb shell getprop ro.build.version.sdk | tr -d '\r')"
  echo "boot_completed=$(adb shell getprop sys.boot_completed | tr -d '\r')"
  echo "verified_boot=$(adb shell getprop ro.boot.verifiedbootstate | tr -d '\r')"
  echo "flash_locked=$(adb shell getprop ro.boot.flash.locked | tr -d '\r')"
} >"$OUT/identity.txt"
grep -Fxq "serial=$SERIAL" "$OUT/identity.txt"
grep -Fxq manufacturer=samsung "$OUT/identity.txt"
grep -Fxq model=SM-S918B "$OUT/identity.txt"
grep -Fxq device=dm3q "$OUT/identity.txt"
grep -Fxq soc=SM8550 "$OUT/identity.txt"
grep -Fxq abi=arm64-v8a "$OUT/identity.txt"
grep -Fxq android_release=16 "$OUT/identity.txt"
grep -Fxq api=36 "$OUT/identity.txt"
grep -Fxq boot_completed=1 "$OUT/identity.txt"
grep -Fxq verified_boot=green "$OUT/identity.txt"
grep -Fxq flash_locked=1 "$OUT/identity.txt"

stage_bytes=$(du -sb "$STAGE" | awk '{print $1}')
available_kb=$(adb shell df -Pk /data/local/tmp | awk 'END {print $4}' | tr -d '\r')
[[ $available_kb =~ ^[0-9]+$ ]] || { echo "cannot parse phone free space" >&2; exit 8; }
required_kb=$((stage_bytes / 1024 + 524288))
{
  echo "stage_bytes=$stage_bytes"
  echo "available_kb=$available_kb"
  echo "required_kb=$required_kb"
} >"$OUT/space-gate.txt"
(( available_kb >= required_kb )) || { echo "insufficient phone staging space" >&2; exit 8; }

adb shell "mkdir '$REMOTE'"
REMOTE_CREATED=1
adb push "$STAGE/." "$REMOTE/" >"$OUT/push.stdout.log" 2>"$OUT/push.stderr.log"
adb shell "cd '$REMOTE' && sha256sum -c stage-manifest.sha256" >"$OUT/remote-stage-verification.txt" 2>"$OUT/remote-stage-verification.stderr.log"
! grep -Fq FAILED "$OUT/remote-stage-verification.txt"
adb shell "chmod 755 '$REMOTE/runner' '$REMOTE/lib/'*.so"
adb shell dumpsys thermalservice >"$OUT/thermal-campaign-before.txt"
adb shell dumpsys battery >"$OUT/battery-campaign-before.txt"

run_native(){
  local label=$1 arm=$2 action=$3
  local remote_out="$REMOTE/evidence/$label"
  local profile_args="" output_args=""
  [[ $action == proof ]] && profile_args="--profile-dir '$remote_out/profiles'"
  [[ $action != setup ]] && output_args="--output-wav '$remote_out/output.wav' --output-raw '$remote_out/output.raw'"
  local arm_args
  if [[ $arm == source ]]; then
    arm_args="--source-root '$REMOTE/source-models'"
  else
    arm_args="--context-root '$REMOTE/contexts'"
  fi
  local runner="./runner --arm '$arm' --action '$action' --asset-root '$REMOTE/assets' $arm_args --transcript '$REMOTE/transcript.txt' --backend '$REMOTE/lib/libQnnHtp.so' $profile_args $output_args"
  local command="cd '$REMOTE' || exit 91; mkdir -p '$remote_out/profiles' || exit 92; export LD_LIBRARY_PATH='$REMOTE/lib' ADSP_LIBRARY_PATH='$REMOTE/lib;/vendor/lib/rfsa/adsp;/vendor/dsp/cdsp;/system/lib/rfsa/adsp;/vendor/dsp'; $runner >'$remote_out/stdout.json' 2>'$remote_out/stderr.log' & pid=\$!; peak_pss=0; peak_hwm=0; while kill -0 \$pid 2>/dev/null; do pss=\$(awk '/^Pss:/{print \$2}' /proc/\$pid/smaps_rollup 2>/dev/null); pss=\${pss:-0}; hwm=\$(awk '/^VmHWM:/{print \$2}' /proc/\$pid/status 2>/dev/null); hwm=\${hwm:-0}; [ \$pss -gt \$peak_pss ] && peak_pss=\$pss; [ \$hwm -gt \$peak_hwm ] && peak_hwm=\$hwm; sleep 0.1; done; wait \$pid; rc=\$?; printf 'peak_sampled_pss_kb=%s\\npeak_observed_vmhwm_kb=%s\\nrunner_exit_code=%s\\n' \$peak_pss \$peak_hwm \$rc >'$remote_out/memory.txt'; exit \$rc"
  mkdir -p "$OUT/commands"
  printf '%s\n' "$command" >"$OUT/commands/$label.txt"
  local start end rc
  start=$(date +%s.%N)
  set +e
  timeout --signal=TERM --kill-after=30 2400 "$ADB" -s "$SERIAL" shell "$command" </dev/null 9>&- >"$OUT/$label.adb.stdout.log" 2>"$OUT/$label.adb.stderr.log"
  rc=$?
  set -e
  end=$(date +%s.%N)
  printf '%s\n' "$rc" >"$OUT/$label.adb-exit-code.txt"
  python3 -c "print(float('$end')-float('$start'))" >"$OUT/$label.adb-wall-seconds.txt"
  [[ $rc == 0 ]]
  adb shell "grep -F '\"result\": \"passed\"' '$remote_out/stdout.json'"
}

capture_arm_context(){
  local arm=$1 when=$2
  adb shell dumpsys thermalservice >"$OUT/thermal-$arm-$when.txt"
  adb shell dumpsys battery >"$OUT/battery-$arm-$when.txt"
}

capture_arm_context source before
for index in 1 2 3; do sleep 30; run_native "source-setup-$index" source setup; done
sleep 30
run_native source-e2e source e2e
capture_arm_context source after
adb shell "rm -rf '$REMOTE/source-models' && test ! -e '$REMOTE/source-models'"
adb shell "find '$REMOTE' -path '$REMOTE/contexts' -prune -o -name 'duration_predictor.onnx' -print | grep -q . && exit 1 || exit 0"
echo passed >"$OUT/context-source-unavailable-gate.txt"

capture_arm_context context before
for index in 1 2 3; do sleep 30; run_native "context-setup-$index" context setup; done
sleep 30
run_native context-e2e context e2e
sleep 30
run_native context-proof context proof
capture_arm_context context after
adb shell dumpsys thermalservice >"$OUT/thermal-campaign-after.txt"
adb shell dumpsys battery >"$OUT/battery-campaign-after.txt"
mkdir -p "$OUT/device-evidence"
adb pull "$REMOTE/evidence/." "$OUT/device-evidence/" >"$OUT/pull.stdout.log" 2>"$OUT/pull.stderr.log"
python3 "$EXP/tools/validate_phone_campaign.py" --campaign "$OUT" --output "$OUT/phone-result.json"
{
  echo "end_utc=$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
  echo "result=passed"
} >"$OUT/campaign-end.txt"
echo "passed: $OUT"

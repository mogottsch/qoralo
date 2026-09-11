#!/usr/bin/env bash
# One scheduled standalone full render; all evidence and content stays private.
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
E="$ROOT/experiments/0036-supertonic-whole-chapter-cpu-htp/htp"
STAGE=${1:?private stage required}
L=${2:?common latent extent required}
OUT=${3:?fresh private output required}
WAIT_SECONDS=${NATIVE_WAIT_SECONDS:-1840}
[[ $WAIT_SECONDS =~ ^[0-9]+$ && $WAIT_SECONDS -ge 180 && $WAIT_SECONDS -le 1840 ]] || exit 2
[[ $STAGE == "$E/.local/"* && $OUT == "$E/.local/"* && ! -e $OUT && $L =~ ^[0-9]+$ ]] || exit 2
[[ ${PHONE_SLOT_SCHEDULED:-no} == yes ]] || { echo 'Pi must schedule the shared-phone slot'; exit 3; }
SERIAL=R5CW81PR8SY
REMOTE="/data/local/tmp/supertonic-0036-htp-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$OUT"
exec 9>"$ROOT/artifacts/locks/phone.lock"
flock -n 9 || { echo 'phone.lock busy'; exit 4; }
unset ADB_LIBUSB
adb(){ timeout -k 5 60 /usr/bin/adb -s "$SERIAL" "$@" </dev/null 9>&-; }
created=no
cleanup(){
  local rc=$?
  trap - EXIT
  set +e
  if [[ $created == yes ]]; then
    # Only stop the exact owned executable if a transport timeout left it alive.
    adb shell "if [ -f '$REMOTE/evidence/runner.pid' ]; then p=\$(cat '$REMOTE/evidence/runner.pid'); if [ \"\$(readlink /proc/\$p/exe)\" = '$REMOTE/runner' ]; then kill -TERM \$p; sleep 2; [ \"\$(readlink /proc/\$p/exe)\" != '$REMOTE/runner' ] || kill -KILL \$p; fi; fi" >"$OUT/owned-process-cleanup.log" 2>&1
    adb pull "$REMOTE/evidence" "$OUT/" >"$OUT/pull.log" 2>&1
    adb shell "rm -rf '$REMOTE'; test ! -e '$REMOTE'" >"$OUT/remote-cleanup.log" 2>&1
    echo $? >"$OUT/remote-cleanup-exit.txt"
  fi
  printf '%s\n' "$rc" >"$OUT/command-exit.txt"
  exit "$rc"
}
trap cleanup EXIT
(cd "$STAGE" && sha256sum -c stage-manifest.sha256) >"$OUT/local-stage-verification.txt"
[[ $(adb get-serialno | tr -d '\r') == "$SERIAL" ]]
{
  for property in ro.product.model ro.soc.model ro.product.cpu.abi ro.build.version.release ro.build.version.sdk; do
    printf '%s=' "$property"; adb shell getprop "$property"
  done
} >"$OUT/device.txt"
adb shell 'df -Pk /data/local/tmp; head -6 /proc/meminfo' >"$OUT/device-resources-before.txt"
adb shell dumpsys thermalservice >"$OUT/thermal-before.txt"
adb shell 'ps -A -o ARGS' >"$OUT/processes-before.txt"
if grep -Eq '/data/local/tmp/[^ ]*/runner|llama-bench|qnn-net-run' "$OUT/processes-before.txt"; then echo 'another benchmark process is live'; exit 5; fi
memory_available=$(adb shell "awk '/^MemAvailable:/{print \$2}' /proc/meminfo" | tr -d '\r')
# Capture only current numeric temperature, not raw battery state/history.
battery_temperature=$(adb shell "dumpsys battery | awk '/^[[:space:]]*temperature:/{print \$2; exit}'" | tr -d '\r')
printf 'MemAvailable_kib=%s\nbattery_temperature_tenths_C=%s\n' "$memory_available" "$battery_temperature" >"$OUT/preflight-bounds.txt"
[[ $memory_available =~ ^[0-9]+$ && $memory_available -ge 3145728 && $battery_temperature =~ ^[0-9]+$ && $battery_temperature -lt 420 ]] || { echo 'memory/thermal preflight bound failed'; exit 6; }
available=$(adb shell df -Pk /data/local/tmp | awk 'END{print $4}' | tr -d '\r')
needed=$(( $(du -sb "$STAGE" | awk '{print $1}') / 1024 + 524288 ))
[[ $available =~ ^[0-9]+$ && $available -ge $needed ]]
adb shell "mkdir '$REMOTE'"
created=yes
adb push "$STAGE/." "$REMOTE/" >"$OUT/push.log" 2>&1
adb shell "cd '$REMOTE' && sha256sum -c stage-manifest.sha256 && chmod 755 runner run_remote.sh" >"$OUT/remote-stage-verification.txt"
start=$(date +%s.%N)
set +e
timeout -k 20 "$WAIT_SECONDS" /usr/bin/adb -s "$SERIAL" shell "cd '$REMOTE' && sh ./run_remote.sh '$L'" </dev/null 9>&- >"$OUT/adb-stdout.log" 2>"$OUT/adb-stderr.log"
rc=$?
set -e
end=$(date +%s.%N)
python -c "import json;print(json.dumps({'adb_exit':$rc,'adb_wall_seconds':float('$end')-float('$start')}))" >"$OUT/transport.json"
adb shell dumpsys thermalservice >"$OUT/thermal-after.txt"
# No all-app logcat or raw battery/charging-history collection; profiling is off.
exit "$rc"

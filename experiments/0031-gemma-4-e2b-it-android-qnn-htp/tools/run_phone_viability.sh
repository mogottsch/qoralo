#!/usr/bin/env bash
set -euo pipefail
EXP=$(cd "$(dirname "$0")/.." && pwd)
REPO=$(cd "$EXP/../.." && pwd)
ADB=${ADB:-adb}
SERIAL=${SERIAL:-R5CW81PR8SY}
STAGE=${STAGE:-$EXP/.local/phone-stage}
RUN_ID=${RUN_ID:-viability-$(date -u +%Y%m%dT%H%M%SZ)-$$}
REMOTE="/data/local/tmp/vibevoice-0031-gemma4-qnn-$RUN_ID"
OUT="$EXP/.local/phone-runs/$RUN_ID"
mkdir -p "$OUT"
exec 9>"$REPO/artifacts/locks/phone.lock"
flock -n 9 || { echo "phone lock busy" >&2; exit 75; }
adb_cmd() { "$ADB" -s "$SERIAL" "$@" 9>&-; }
cleanup() {
  set +e
  adb_cmd shell "rm -rf '$REMOTE'" >"$OUT/cleanup.stdout" 2>"$OUT/cleanup.stderr"
  adb_cmd shell "test ! -e '$REMOTE'" && echo absent >"$OUT/cleanup-status.txt" || echo present >"$OUT/cleanup-status.txt"
}
trap cleanup EXIT

adb_cmd get-state | tr -d '\r' | tee "$OUT/adb-state.txt" | grep -Fx device
{
  echo "serial=$(adb_cmd get-serialno | tr -d '\r')"
  echo "manufacturer=$(adb_cmd shell getprop ro.product.manufacturer | tr -d '\r')"
  echo "model=$(adb_cmd shell getprop ro.product.model | tr -d '\r')"
  echo "device=$(adb_cmd shell getprop ro.product.device | tr -d '\r')"
  echo "soc=$(adb_cmd shell getprop ro.soc.model | tr -d '\r')"
  echo "abi=$(adb_cmd shell getprop ro.product.cpu.abi | tr -d '\r')"
  echo "release=$(adb_cmd shell getprop ro.build.version.release | tr -d '\r')"
  echo "sdk=$(adb_cmd shell getprop ro.build.version.sdk | tr -d '\r')"
  echo "fingerprint=$(adb_cmd shell getprop ro.build.fingerprint | tr -d '\r')"
  echo "boot=$(adb_cmd shell getprop sys.boot_completed | tr -d '\r')"
  echo "verified_boot=$(adb_cmd shell getprop ro.boot.verifiedbootstate | tr -d '\r')"
  echo "flash_locked=$(adb_cmd shell getprop ro.boot.flash.locked | tr -d '\r')"
} | tee "$OUT/identity.txt"
for required in serial=$SERIAL manufacturer=samsung model=SM-S918B device=dm3q soc=SM8550 abi=arm64-v8a boot=1 verified_boot=green flash_locked=1; do
  grep -Fx "$required" "$OUT/identity.txt" >/dev/null || { echo "identity mismatch: $required" >&2; exit 3; }
done
adb_cmd shell dumpsys battery >"$OUT/battery-before.txt" 2>"$OUT/battery-before.stderr" || true
adb_cmd shell dumpsys thermalservice >"$OUT/thermal-before.txt" 2>"$OUT/thermal-before.stderr" || true
adb_cmd shell df -k /data/local/tmp >"$OUT/storage-before.txt"
available=$(awk 'NR==2{print $4}' "$OUT/storage-before.txt")
(( available > 6*1024*1024 )) || { echo "less than 6 GiB free on /data/local/tmp" >&2; exit 4; }

(cd "$STAGE" && sha256sum -c SHA256SUMS) >"$OUT/local-hash-check.txt"
adb_cmd shell "mkdir -p '$REMOTE'"
adb_cmd push "$STAGE/." "$REMOTE/" >"$OUT/push.txt" 2>&1
adb_cmd shell "cd '$REMOTE' && sha256sum -c SHA256SUMS" >"$OUT/remote-hash-check.txt" 2>"$OUT/remote-hash-check.stderr"
required_runtime=(
  bin/genie-app lib/libGenie.so lib/libQnnHtp.so lib/libQnnSystem.so
  lib/libQnnHtpV73Stub.so lib/libQnnHtpV73Skel.so lib/libQnnHtpNetRunExtensions.so
  htp_backend_ext_config.json
)
for required in "${required_runtime[@]}"; do
  [[ -s "$STAGE/$required" ]] || { echo "missing local runtime dependency: $required" >&2; exit 7; }
  adb_cmd shell "test -s '$REMOTE/$required'" || { echo "missing remote runtime dependency: $required" >&2; exit 8; }
done
printf '%s\n' "${required_runtime[@]}" >"$OUT/runtime-completeness.txt"
adb_cmd shell "chmod 700 '$REMOTE/bin/genie-app'; rm -f '$REMOTE/viability-output.txt' '$REMOTE/viability-profile.json' '$REMOTE/genie-verbose.log'"

set +e
timeout 1800 "$ADB" -s "$SERIAL" shell "cd '$REMOTE' && export LD_LIBRARY_PATH='$REMOTE/lib' ADSP_LIBRARY_PATH='$REMOTE/lib' QNN_LOG_LEVEL=verbose && ./bin/genie-app -s viability.script" 9>&- >"$OUT/runner.stdout" 2>"$OUT/runner.stderr" &
run_pid=$!
(
  while kill -0 "$run_pid" 2>/dev/null; do
    now=$(date +%s%N)
    pid=$(adb_cmd shell pidof genie-app 2>/dev/null | tr -d '\r' | awk '{print $1}')
    if [[ "$pid" =~ ^[0-9]+$ ]]; then
      echo "timestamp_ns=$now pid=$pid"
      adb_cmd shell "cat /proc/$pid/status | grep -E '^(VmHWM|VmRSS|RssAnon|RssFile|RssShmem):'" 2>/dev/null | tr -d '\r'
      adb_cmd shell dumpsys meminfo "$pid" 2>/dev/null | tr -d '\r' | grep -E 'TOTAL PSS:|TOTAL RSS:'
    else
      echo "timestamp_ns=$now pid=null"
    fi
    sleep 0.5
  done
) >"$OUT/memory-samples.txt" 2>"$OUT/memory-samples.stderr" &
sampler_pid=$!
wait "$run_pid"; run_code=$?
wait "$sampler_pid" || true
set -e
printf '%s\n' "$run_code" >"$OUT/exit-code.txt"

for file in viability-output.txt viability-profile.json genie-verbose.log; do
  adb_cmd pull "$REMOTE/$file" "$OUT/$file" >"$OUT/pull-$file.txt" 2>&1 || true
done
adb_cmd shell dumpsys battery >"$OUT/battery-after.txt" 2>"$OUT/battery-after.stderr" || true
adb_cmd shell dumpsys thermalservice >"$OUT/thermal-after.txt" 2>"$OUT/thermal-after.stderr" || true
adb_cmd shell "pidof genie-app || true" >"$OUT/process-after.txt"
# Raw evidence is already retained above. Validation happens only after capture.
[[ "$run_code" == 0 ]] || { echo "runner failed: $run_code" >&2; exit "$run_code"; }
[[ -s "$OUT/viability-output.txt" ]] || { echo "missing viability output" >&2; exit 5; }
[[ -s "$OUT/viability-profile.json" ]] || { echo "missing viability profile" >&2; exit 6; }
echo "$RUN_ID"

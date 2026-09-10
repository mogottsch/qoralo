#!/usr/bin/env bash
# Planned bounded integrated AR171→AR1 diagnostic. Do not run without Pi priority.
set -euo pipefail
EXP=$(cd "$(dirname "$0")/.." && pwd)
REPO=$(cd "$EXP/../.." && pwd)
ADB=${ADB:-adb}
SERIAL=${SERIAL:-R5CW81PR8SY}
STAGE=${STAGE:?set STAGE}
RUN_ID=${RUN_ID:-integrated-$(date -u +%Y%m%dT%H%M%SZ)-$$}
REMOTE="/data/local/tmp/vibevoice-0034-$RUN_ID"
OUT="$EXP/.local/integrated-qnn-phone-runs/$RUN_ID"
mkdir -p "$OUT"
python3 "$EXP/tools/verify_android_stage_elf.py" "$STAGE" >"$OUT/local-elf-preflight.txt"
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
  for item in \
    'manufacturer ro.product.manufacturer' 'model ro.product.model' 'device ro.product.device' \
    'soc ro.soc.model' 'abi ro.product.cpu.abi' 'release ro.build.version.release' \
    'sdk ro.build.version.sdk' 'boot sys.boot_completed' \
    'verified_boot ro.boot.verifiedbootstate' 'flash_locked ro.boot.flash.locked'; do
    set -- $item; echo "$1=$(adb_cmd shell getprop "$2" | tr -d '\r')"
  done
} | tee "$OUT/identity.txt"
for value in serial=$SERIAL manufacturer=samsung model=SM-S918B device=dm3q soc=SM8550 abi=arm64-v8a boot=1 verified_boot=green flash_locked=1; do
  grep -Fx "$value" "$OUT/identity.txt" >/dev/null || exit 3
done
adb_cmd shell dumpsys battery >"$OUT/battery-before.txt" 2>"$OUT/battery-before.stderr" || true
adb_cmd shell dumpsys thermalservice >"$OUT/thermal-before.txt" 2>"$OUT/thermal-before.stderr" || true
adb_cmd shell df -k /data/local/tmp >"$OUT/storage-before.txt"
available=$(awk 'NR==2{print $4}' "$OUT/storage-before.txt")
(( available > 5*1024*1024 )) || exit 4
(cd "$STAGE" && sha256sum -c SHA256SUMS) >"$OUT/local-hash-check.txt"
adb_cmd shell "mkdir -p '$REMOTE'"
adb_cmd push "$STAGE/." "$REMOTE/" >"$OUT/push.txt" 2>&1
adb_cmd shell "cd '$REMOTE' && sha256sum -c SHA256SUMS" >"$OUT/remote-hash-check.txt" 2>"$OUT/remote-hash-check.stderr"
adb_cmd shell "chmod 700 '$REMOTE/direct_lfm2_qnn_runner'"
set +e
timeout 600 "$ADB" -s "$SERIAL" shell \
  "cd '$REMOTE' && export LD_LIBRARY_PATH='$REMOTE' ADSP_LIBRARY_PATH='$REMOTE' && ./direct_lfm2_qnn_runner '$REMOTE' --integrated '$REMOTE/short.int32le' 16 '$REMOTE/output.int32le'" \
  9>&- >"$OUT/runner.stdout" 2>"$OUT/runner.stderr" &
runner_pid=$!
(
  while kill -0 "$runner_pid" 2>/dev/null; do
    now=$(date +%s%N)
    pid=$(adb_cmd shell pidof direct_lfm2_qnn_runner 2>/dev/null | tr -d '\r' | awk '{print $1}')
    if [[ "$pid" =~ ^[0-9]+$ ]]; then
      echo "timestamp_ns=$now pid=$pid"
      adb_cmd shell "cat /proc/$pid/status | grep -E '^(VmHWM|VmRSS|RssAnon|RssFile|RssShmem):'" 2>/dev/null | tr -d '\r'
    else
      echo "timestamp_ns=$now pid=null"
    fi
    sleep 0.5
  done
) >"$OUT/memory-samples.txt" 2>"$OUT/memory-samples.stderr" &
sampler_pid=$!
wait "$runner_pid"; runner_code=$?
wait "$sampler_pid" || true
set -e
printf '%s\n' "$runner_code" >"$OUT/exit-code.txt"
adb_cmd pull "$REMOTE/output.int32le" "$OUT/output.int32le" >"$OUT/pull-output.txt" 2>&1 || true
adb_cmd shell dumpsys battery >"$OUT/battery-after.txt" 2>"$OUT/battery-after.stderr" || true
adb_cmd shell dumpsys thermalservice >"$OUT/thermal-after.txt" 2>"$OUT/thermal-after.stderr" || true
adb_cmd shell "pidof direct_lfm2_qnn_runner || true" >"$OUT/process-after.txt"
[[ "$runner_code" == 0 ]] || exit "$runner_code"
echo "$RUN_ID"

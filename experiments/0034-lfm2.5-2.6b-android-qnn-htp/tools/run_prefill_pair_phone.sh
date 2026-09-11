#!/usr/bin/env bash
# Scheduled standalone pair only; never stop/install/clear an app or change settings.
set -euo pipefail
EXP=$(cd "$(dirname "$0")/.." && pwd)
REPO=$(cd "$EXP/../.." && pwd)
ADB=${ADB:-adb}
SERIAL=${SERIAL:-R5CW81PR8SY}
STAGE=${STAGE:?set the fresh reviewed pair stage}
[[ ${PHONE_SLOT_CONFIRMED:-0} == 1 ]] || { echo 'A clear Janek/Ben resource handoff is required' >&2; exit 75; }
RUN_ID=${RUN_ID:-prefill-pair-$(date -u +%Y%m%dT%H%M%SZ)-$$}
[[ "$RUN_ID" =~ ^prefill-pair-[A-Za-z0-9-]+$ ]] || exit 2
REMOTE="/data/local/tmp/vibevoice-0034-$RUN_ID"
OUT="$EXP/.local/prefill-pair-phone-runs/$RUN_ID"
mkdir -p "$(dirname "$OUT")"
mkdir "$OUT"
mkdir "$OUT/private"
python3 "$EXP/tools/verify_android_stage_elf.py" "$STAGE" >"$OUT/local-elf-preflight.txt"
(cd "$STAGE" && sha256sum -c SHA256SUMS) >"$OUT/local-hash-check.txt"
source "$EXP/tools/phone_evidence_guard.sh"
exec 9>"$REPO/artifacts/locks/phone.lock"
flock -n 9 || { echo 'phone.lock busy; do not race/retry' >&2; exit 75; }
printf 'held\n' >"$OUT/lock-status.txt"
printf 'phone_lock_acquired run_id=%s\n' "$RUN_ID"
adb_cmd() { "$ADB" -s "$SERIAL" "$@" 9>&-; }
remote_owned=0
retain_remote=0
process_absence=0
phase_started=-1
cleanup() {
  local status=$?
  trap - EXIT
  set +e
  # A lost ADB transport may return before the device-side timeout. Keep the lock
  # through that independent120s+5s kill bound before one final PID verification.
  if [[ "$remote_owned" == 1 && "$process_absence" == 0 && "$phase_started" -ge 0 ]]; then
    local remaining=$((130 - (SECONDS - phase_started)))
    if (( remaining > 0 )); then sleep "$remaining"; fi
    if phone_capture_process_after "$ADB" "$SERIAL" direct_lfm2_qnn_runner "$OUT/process-after-timeout-grace.txt" "$OUT/process-after-timeout-grace.stderr"; then
      process_absence=1
    fi
  fi
  if [[ "$remote_owned" == 1 && "$retain_remote" == 0 && "$process_absence" == 1 ]]; then
    phone_cleanup_remote "$ADB" "$SERIAL" "$REMOTE" "$OUT"
    if ! grep -Fxq absent "$OUT/cleanup-status.txt"; then status=7; fi
  elif [[ "$remote_owned" != 0 || "$retain_remote" == 1 ]]; then
    printf 'retained_remote=%s ownership=%s pid_absence=%s\n' "$REMOTE" "$remote_owned" "$process_absence" >"$OUT/cleanup-status.txt"
    [[ "$status" != 0 ]] || status=7
  else
    echo 'not_created_no_remote_cleanup_attempted' >"$OUT/cleanup-status.txt"
  fi
  printf 'app_stop_install_or_data_changes=false\nandroid_settings_modified=false\n' >"$OUT/settings-boundary.txt"
  flock -u 9
  echo 'released' >"$OUT/lock-status.txt"
  exit "$status"
}
trap cleanup EXIT
adb_cmd get-state | tr -d '\r' | tee "$OUT/adb-state.txt" | grep -Fx device
{
  echo "serial=$(adb_cmd get-serialno | tr -d '\r')"
  for item in 'manufacturer ro.product.manufacturer' 'model ro.product.model' 'device ro.product.device' 'soc ro.soc.model' 'abi ro.product.cpu.abi' 'release ro.build.version.release' 'sdk ro.build.version.sdk' 'fingerprint ro.build.fingerprint' 'boot sys.boot_completed'; do
    set -- $item; echo "$1=$(adb_cmd shell getprop "$2" | tr -d '\r')"
  done
} >"$OUT/identity.txt"
for value in serial=$SERIAL manufacturer=samsung model=SM-S918B device=dm3q soc=SM8550 abi=arm64-v8a release=16 sdk=36 fingerprint=samsung/dm3qxeea/dm3q:16/BP4A.251205.006/S918BXXSAFZG1:user/release-keys boot=1; do
  grep -Fxq "$value" "$OUT/identity.txt" || exit 3
done
if ! phone_capture_process_after "$ADB" "$SERIAL" direct_lfm2_qnn_runner "$OUT/process-before.txt" "$OUT/process-before.stderr"; then
  echo 'existing or unknown standalone runner; no staging' >&2; exit 4
fi
process_absence=1
adb_cmd shell 'timeout --help' >"$OUT/device-timeout-help.txt" 2>"$OUT/device-timeout-help.stderr"
grep -Fq -- '-k' "$OUT/device-timeout-help.txt" || { echo 'device timeout kill-after unsupported' >&2; exit 4; }
adb_cmd shell df -k /data/local/tmp >"$OUT/storage-before.txt"
available=$(awk 'NR==2{print $4}' "$OUT/storage-before.txt" | tr -d '\r')
[[ "$available" =~ ^[0-9]+$ ]] && (( available > 6*1024*1024 )) || exit 4
remote_owned=unknown
if ! adb_cmd shell "mkdir '$REMOTE'" >"$OUT/mkdir.stdout" 2>"$OUT/mkdir.stderr"; then
  retain_remote=1; exit 5
fi
remote_owned=1
adb_cmd push "$STAGE/." "$REMOTE/" >"$OUT/push.txt" 2>&1
adb_cmd shell "cd '$REMOTE' && sha256sum -c SHA256SUMS" >"$OUT/remote-hash-check.txt" 2>"$OUT/remote-hash-check.stderr"
adb_cmd shell "chmod 700 '$REMOTE/direct_lfm2_qnn_runner'"
capture_telemetry() {
  local tag=$1 battery_rc thermal_rc
  set +e
  adb_cmd shell dumpsys battery >"$OUT/private/$tag-battery.txt" 2>"$OUT/private/$tag-battery.stderr"; battery_rc=$?
  adb_cmd shell dumpsys thermalservice >"$OUT/private/$tag-thermal.txt" 2>"$OUT/private/$tag-thermal.stderr"; thermal_rc=$?
  set -e
  python3 "$EXP/tools/extract_core_phone_telemetry.py" --battery "$OUT/private/$tag-battery.txt" --thermal "$OUT/private/$tag-thermal.txt" --battery-exit "$battery_rc" --thermal-exit "$thermal_rc" --output "$OUT/$tag-core-telemetry.json"
}
for phase in baseline candidate; do
  mkdir "$OUT/$phase"
  capture_telemetry "$phase-before"
  process_absence=0
  phase_started=$SECONDS
  printf 'phase_start=%s run_id=%s\n' "$phase" "$RUN_ID"
  set +e
  timeout --signal=TERM --kill-after=5s 180s "$ADB" -s "$SERIAL" shell \
    "cd '$REMOTE' && export LD_LIBRARY_PATH='$REMOTE' ADSP_LIBRARY_PATH='$REMOTE' && timeout -k 5 120 ./direct_lfm2_qnn_runner '$REMOTE' --prefill-diagnostic '$REMOTE/contexts/$phase.bin' '$REMOTE/short.int32le' '$REMOTE/$phase'; code=\$?; echo \$code > '$REMOTE/$phase-exit.txt'; exit \$code" \
    9>&- >"$OUT/$phase/runner.stdout" 2>"$OUT/$phase/runner.stderr" &
  runner_pid=$!
  (
    while kill -0 "$runner_pid" 2>/dev/null; do
      now=$(date +%s%N)
      pid=$(timeout 3s "$ADB" -s "$SERIAL" shell pidof direct_lfm2_qnn_runner 9>&- 2>/dev/null | tr -d '\r' | awk '{print $1}')
      if [[ "$pid" =~ ^[0-9]+$ ]]; then
        echo "timestamp_ns=$now pid=$pid"
        timeout 3s "$ADB" -s "$SERIAL" shell "grep -E '^(VmHWM|VmRSS|RssAnon|RssFile|RssShmem):' /proc/$pid/status" 9>&- 2>/dev/null | tr -d '\r'
      else
        echo "timestamp_ns=$now pid=unobserved"
      fi
      sleep 0.5
    done
  ) >"$OUT/$phase/memory-samples.txt" 2>"$OUT/$phase/memory-samples.stderr" &
  sampler_pid=$!
  wait "$runner_pid"; runner_code=$?
  wait "$sampler_pid" || true
  set -e
  printf '%s\n' "$runner_code" >"$OUT/$phase/exit-code.txt"
  if ! adb_cmd pull "$REMOTE/$phase" "$OUT/$phase/native" >"$OUT/$phase/pull.txt" 2>&1; then retain_remote=1; fi
  adb_cmd pull "$REMOTE/$phase-exit.txt" "$OUT/$phase/device-exit-code.txt" >"$OUT/$phase/pull-exit.txt" 2>&1 || retain_remote=1
  capture_telemetry "$phase-after"
  if phone_capture_process_after "$ADB" "$SERIAL" direct_lfm2_qnn_runner "$OUT/$phase/process-after.txt" "$OUT/$phase/process-after.stderr"; then
    process_absence=1
  else
    retain_remote=1
  fi
  [[ "$retain_remote" == 0 ]] || exit 6
  [[ "$runner_code" == 0 ]] || exit "$runner_code"
  grep -Fxq 'qnn_backend_build_id=v2.49.40.260810104044' "$OUT/$phase/runner.stderr" || exit 8
  printf 'phase_complete=%s run_id=%s\n' "$phase" "$RUN_ID"
done
printf '%s\n' "$RUN_ID"

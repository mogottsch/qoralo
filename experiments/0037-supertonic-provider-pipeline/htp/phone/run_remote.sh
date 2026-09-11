#!/system/bin/sh
# Parent owns phone.lock for preflight/stage/run/pull/cleanup, never touches app data.
set -u
ROOT=$(pwd)
case "$ROOT" in /data/local/tmp/supertonic-0037-htp-*) ;; *) exit 90;; esac
[ ! -e evidence ] || exit 91
mkdir evidence || exit 92
export LD_LIBRARY_PATH="$ROOT/lib"
export ADSP_LIBRARY_PATH="$ROOT/lib;/vendor/lib/rfsa/adsp;/vendor/dsp/cdsp;/system/lib/rfsa/adsp;/vendor/dsp"
log_start=$(date '+%m-%d %H:%M:%S.000')
./runner "$ROOT/contexts" "$ROOT/bundle" "$ROOT/evidence/run" "$ROOT/lib/libQnnHtp.so" >evidence/stdout.log 2>evidence/stderr.log &
pid=$!
echo "$pid" >evidence/runner.pid
stop_owned() {
  if [ "$(readlink /proc/$pid/exe)" = "$ROOT/runner" ]; then
    kill -TERM "$pid" 2>/dev/null
    sleep 2
    [ "$(readlink /proc/$pid/exe)" != "$ROOT/runner" ] || kill -KILL "$pid" 2>/dev/null
  fi
}
trap 'stop_owned' HUP INT TERM
peak=0
pss_peak=0
reason=none
while kill -0 "$pid" 2>/dev/null; do
  rss=$(awk '/^VmRSS:/{print $2}' /proc/$pid/status 2>/dev/null)
  hwm=$(awk '/^VmHWM:/{print $2}' /proc/$pid/status 2>/dev/null)
  pss=$(awk '/^Pss:/{print $2}' /proc/$pid/smaps_rollup 2>/dev/null)
  rss=${rss:-0}; hwm=${hwm:-0}; pss=${pss:-0}
  [ "$hwm" -gt "$peak" ] && peak=$hwm
  [ "$pss" -gt "$pss_peak" ] && pss_peak=$pss
  available=$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)
  temperature=$(dumpsys battery | awk '/^[[:space:]]*temperature:/{if(!found){t=$2;found=1}} END{print t}')
  available=${available:-0}; temperature=${temperature:-999}
  printf '%s %s %s %s %s %s\n' "$(date +%s)" "$rss" "$hwm" "$pss" "$available" "$temperature" >>evidence/memory-samples.txt
  if [ "$rss" -gt 3145728 ] || [ "$available" -lt 614400 ] || [ "$temperature" -ge 450 ]; then
    reason=rss_over_3GiB_or_available_below_600MiB_or_battery_at_45C_or_missing_measurement
    stop_owned
    break
  fi
  sleep 0.5
done
wait "$pid"
rc=$?
# Owned PID/time-window only; never clear all-app logs or enable profiling.
timeout 5 logcat -d --pid "$pid" -T "$log_start" -v threadtime >evidence/native-pid-logcat.txt 2>evidence/native-pid-logcat.stderr
printf 'runner_exit_code=%s\npeak_observed_vmhwm_kib=%s\npeak_sampled_pss_kib=%s\nguard_reason=%s\n' "$rc" "$peak" "$pss_peak" "$reason" >evidence/memory.txt
echo "$rc" >evidence/exit-code
exit "$rc"

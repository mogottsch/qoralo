#!/system/bin/sh
# Run only from a new0036-owned stage; parent holds the full phone.lock.
set -u
L=$1
ROOT=$(pwd)
case "$ROOT" in /data/local/tmp/supertonic-0036-htp-*) ;; *) exit 90;; esac
[ ! -e evidence ] || exit 91
mkdir evidence || exit 92
export LD_LIBRARY_PATH="$ROOT/lib"
export ADSP_LIBRARY_PATH="$ROOT/lib;/vendor/lib/rfsa/adsp;/vendor/dsp/cdsp;/system/lib/rfsa/adsp;/vendor/dsp"
./runner "$ROOT/contexts" "$ROOT/bundle" "$ROOT/evidence/run" "$L" "$ROOT/lib/libQnnHtp.so" >evidence/result.json 2>evidence/stderr.log &
pid=$!
echo "$pid" >evidence/runner.pid
trap 'kill -TERM "$pid" 2>/dev/null; sleep 2; kill -KILL "$pid" 2>/dev/null' HUP INT TERM
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
  available=${available:-0}
  printf '%s %s %s %s %s\n' "$(date +%s)" "$rss" "$hwm" "$pss" "$available" >>evidence/memory-samples.txt
  # Protect the installed app: bound this process, never kill another process.
  if [ "$rss" -gt 3145728 ] || [ "$available" -lt 614400 ]; then
    reason=sampled_rss_over_3GiB_or_device_available_below_600MiB
    kill -TERM "$pid" 2>/dev/null
    sleep 2
    kill -KILL "$pid" 2>/dev/null
    break
  fi
  sleep 0.5
done
wait "$pid"
rc=$?
# Post-run, owned-PID-only logs; never clear global logs or change profiling.
timeout 5 logcat -d --pid "$pid" -v threadtime >evidence/native-pid-logcat.txt 2>evidence/native-pid-logcat.stderr
printf 'runner_exit_code=%s\npeak_observed_vmhwm_kib=%s\npeak_sampled_pss_kib=%s\nguard_reason=%s\n' "$rc" "$peak" "$pss_peak" "$reason" >evidence/memory.txt
exit "$rc"

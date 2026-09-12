"""Pinned, generated shell control files for a future explicitly approved phone slot.

Never executed by import. All PID-file-derived signals revalidate executable,
argv and Linux starttime immediately before signalling; no process-name kills.
These checks followed by numeric-PID kill are not atomic/pidfd identity binding.
"""
import shlex


def common(remote):
    return f'REMOTE={shlex.quote(remote)}\n' + r'''
proc_start() {
  [ -r "/proc/$1/stat" ] || return 1
  st=$(cat "/proc/$1/stat") || return 1
  tail=${st##*) }
  printf '%s\n' "$tail" | awk '{print $20}'
}
record_self() {
  printf '%s\n' "$$" > "$REMOTE/evidence/$1.pid"
  proc_start "$$" > "$REMOTE/evidence/$1.start"
}
role_matches() {
  role=$1; pid=$2; expected_start=$3
  case "$pid:$expected_start" in *[!0-9:]*|:*|*:) return 1;; esac
  [ "$pid" -gt 1 ] || return 1
  [ "$(proc_start "$pid")" = "$expected_start" ] || return 1
  exe=$(readlink "/proc/$pid/exe") || return 1
  exe_bytes=$(readlink "/proc/$pid/exe" | wc -c) || return 1
  [ "$exe_bytes" -eq $((${#exe} + 1)) ] || return 1
  argv=$(tr '\000' '\n' < "/proc/$pid/cmdline") || return 1
  case "$role" in
    model)
      if [ "$exe" = "$REMOTE/bin/genie-app" ]; then
        expected=$(printf '%s\n-s\nexact-long.script' "$REMOTE/bin/genie-app")
        expected_fields=3
      else
        case "$exe" in /system/bin/sh|/system/bin/mksh) ;; *) return 1;; esac
        expected=$(printf '/system/bin/sh\n%s/model-entry.sh' "$REMOTE")
        expected_fields=2
      fi;;
    wrapper|watchdog)
      case "$exe" in /system/bin/sh|/system/bin/mksh) ;; *) return 1;; esac
      if [ "$role" = wrapper ]; then script=launch.sh; else script=watchdog.sh; fi
      expected=$(printf '/system/bin/sh\n%s/%s' "$REMOTE" "$script")
      expected_fields=2;;
    *) return 1;;
  esac
  [ "$argv" = "$expected" ] || return 1
  # Command substitution strips trailing newlines: also bind NUL field count
  # and byte length so extra empty arguments/literal-newline spoofing fail.
  fields=$(tr -cd '\000' < "/proc/$pid/cmdline" | wc -c) || return 1
  bytes=$(wc -c < "/proc/$pid/cmdline") || return 1
  [ "$fields" -eq "$expected_fields" ] && [ "$bytes" -eq $((${#expected} + 1)) ] || return 1
  [ "$(proc_start "$pid")" = "$expected_start" ]
}
signal_owned() {
  role=$1; pid=$2; start=$3; sig=$4
  case "$sig" in TERM|KILL) ;; *) return 64;; esac
  case "$pid:$start" in *[!0-9:]*|:*|*:) return 64;; esac
  [ "$pid" -gt 1 ] || return 64
  if [ ! -d "/proc/$pid" ]; then printf 'ABSENT\n'; return 0; fi
  role_matches "$role" "$pid" "$start" || {
    [ ! -d "/proc/$pid" ] && { printf 'ABSENT\n'; return 0; }
    printf 'REFUSED\n'; return 64
  }
  # No signal is issued before all scope/starttime/executable/argv checks above.
  # Residual TOCTOU remains between those checks and numeric-PID kill (no pidfd).
  kill -"$sig" "$pid" || { [ ! -d "/proc/$pid" ] && return 0; return 65; }
  printf 'SIGNALLED\n'
}
'''


def scripts(remote):
    source = '. ' + shlex.quote(remote + '/control.sh') + '\n'
    return {
        'control.sh': common(remote),
        'model-entry.sh': '#!/system/bin/sh\nset -eu\n' + source + r'''
# Both identity records must be written successfully BEFORE exec; same PID/starttime.
record_self model
cd "$REMOTE"
export LD_LIBRARY_PATH="$REMOTE/lib" ADSP_LIBRARY_PATH="$REMOTE/lib" QNN_LOG_LEVEL=verbose
export GEMMA_PREFILL_CAPTURE_DIR="$REMOTE/evidence/prefill-capture"
mkdir -m 700 "$GEMMA_PREFILL_CAPTURE_DIR" || exit 71
ulimit -v 8388608 || exit 72
exec "$REMOTE/bin/genie-app" -s exact-long.script
''',
        'launch.sh': '#!/system/bin/sh\nset -eu\n' + source + r'''
record_self wrapper
cd "$REMOTE"
read up rest < /proc/uptime
printf '%s\n' "${up%%.*}" > evidence/start.uptime
/system/bin/sh "$REMOTE/model-entry.sh" > evidence/runner.stdout 2> evidence/runner.stderr &
child=$!
/system/bin/sh "$REMOTE/watchdog.sh" > evidence/watchdog.stdout 2> evidence/watchdog.stderr &
set +e
wait "$child"
rc=$?
printf '%s\n' "$rc" > evidence/exit-code.tmp
mv evidence/exit-code.tmp evidence/exit-code.txt
exit "$rc"
''',
        'watchdog.sh': '#!/system/bin/sh\nset -eu\n' + source + r'''
record_self watchdog
start=$(cat "$REMOTE/evidence/start.uptime")
case "$start" in ''|*[!0-9]*) exit 66;; esac
deadline=$((start + 300))
while [ ! -f "$REMOTE/evidence/exit-code.txt" ]; do
  read up rest < /proc/uptime
  now=${up%%.*}
  if [ "$now" -ge "$deadline" ]; then
    printf 'deadline300\n' > "$REMOTE/evidence/watchdog-timeout.txt"
    pid=$(cat "$REMOTE/evidence/model.pid") || exit 66
    born=$(cat "$REMOTE/evidence/model.start") || exit 66
    signal_owned model "$pid" "$born" TERM || exit 67
    # Bounded grace; never escalate without a fresh identity check.
    sleep 5
    signal_owned model "$pid" "$born" KILL || exit 67
    exit 124
  fi
  sleep 1
done
''',
    }

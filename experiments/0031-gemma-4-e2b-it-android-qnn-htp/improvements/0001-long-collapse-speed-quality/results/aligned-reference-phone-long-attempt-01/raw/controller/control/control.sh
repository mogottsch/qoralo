REMOTE=/data/local/tmp/vibevoice-0031-aligned-aligned-long-20260912T100120Z-01

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
      if [ "$exe" = "$REMOTE/bin/litert_lm_aligned_reference" ]; then
        expected=$(printf '%s\n--backend=gpu\n--model_path=models/gemma-4-E2B-it.litertlm\n--workload_dir=workloads\n--output_dir=evidence\n--arm_id=0031-single-bos-aligned-gpu\n--cache_dir=cache\n--max_num_tokens=8192\n--max_output_tokens=2048\n--num_cpu_threads=4\n--request_timeout_seconds=1800\n--reset_mode=fresh_session' "$REMOTE/bin/litert_lm_aligned_reference")
        expected_fields=12
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

REMOTE=/data/local/tmp/vibevoice-0031-htp-chain-htp-chains-20260914T160058Z-01

proc_start() {
  [ -r "/proc/$1/stat" ] || return 1
  st=$(cat "/proc/$1/stat") || return 1
  tail=${st##*) }
  printf '%s\n' "$tail" | awk '{print $20}'
}
record_self() {
  printf '%s\n' "$$" > "$REMOTE/evidence/normalization_chain.$1.pid"
  proc_start "$$" > "$REMOTE/evidence/normalization_chain.$1.start"
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
      if [ "$exe" = "$REMOTE/bin/qnn-net-run" ]; then
        expected=$(printf '%s\n' /data/local/tmp/vibevoice-0031-htp-chain-htp-chains-20260914T160058Z-01/bin/qnn-net-run --backend /data/local/tmp/vibevoice-0031-htp-chain-htp-chains-20260914T160058Z-01/lib/libQnnHtp.so --retrieve_context /data/local/tmp/vibevoice-0031-htp-chain-htp-chains-20260914T160058Z-01/power-edge-context.bin --input_list __,/data/local/tmp/vibevoice-0031-htp-chain-htp-chains-20260914T160058Z-01/evidence/normalization_chain.inputlist,__ --output_dir /data/local/tmp/vibevoice-0031-htp-chain-htp-chains-20260914T160058Z-01/evidence/normalization_chain/outputs --num_inferences 1 --use_native_input_files --use_native_output_files --shared_buffer --profiling_level basic --log_level info)
        expected_fields=18
      else
        case "$exe" in /system/bin/sh|/system/bin/mksh) ;; *) return 1;; esac
        expected=$(printf '/system/bin/sh\n%s/normalization_chain-model-entry.sh' "$REMOTE")
        expected_fields=2
      fi;;
    wrapper|watchdog)
      case "$exe" in /system/bin/sh|/system/bin/mksh) ;; *) return 1;; esac
      if [ "$role" = wrapper ]; then script=normalization_chain-launch.sh; else script=normalization_chain-watchdog.sh; fi
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

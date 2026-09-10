#!/usr/bin/env bash
# Shared fail-closed phone evidence helpers. Callers must already hold phone.lock.

phone_cleanup_remote() {
  local adb=$1 serial=$2 remote=$3 out=$4
  if ! "$adb" -s "$serial" shell "rm -rf '$remote'" 9>&- >"$out/cleanup.stdout" 2>"$out/cleanup.stderr"; then
    echo unverified_transport_failure >"$out/cleanup-status.txt"
    return 2
  fi
  local state
  if ! state=$("$adb" -s "$serial" shell \
      "if test ! -e '$remote'; then echo absent; else echo present; fi" 9>&- \
      2>"$out/cleanup-verification.stderr"); then
    echo unverified_transport_failure >"$out/cleanup-status.txt"
    return 2
  fi
  state=${state//$'\r'/}
  case "$state" in
    absent|present) echo "$state" >"$out/cleanup-status.txt" ;;
    *) echo unverified_transport_failure >"$out/cleanup-status.txt"; return 2 ;;
  esac
}

phone_capture_process_after() {
  local adb=$1 serial=$2 process_name=$3 output=$4 error=$5
  if ! "$adb" -s "$serial" shell "pidof '$process_name' || true" 9>&- >"$output" 2>"$error"; then
    return 2
  fi
  tr -d '\r' <"$output" >"$output.tmp"
  mv "$output.tmp" "$output"
  [[ ! -s "$output" ]]
}

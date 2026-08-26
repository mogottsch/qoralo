#!/usr/bin/env bash
set -euo pipefail

[[ "${PHONE_RUN_APPROVED:-}" == yes ]] || {
  echo "phone work requires fresh coordination: set PHONE_RUN_APPROVED=yes only after Pi clears 0029" >&2
  exit 2
}
ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0029-lfm2.5-2.6b-android"
STAGE="$EXP/.local/android-stage"
CONTRACT="$EXP/protocol/experiment-contract.json"
MODEL="$EXP/.local/models/LFM2.5-2.6B-Q4_K_M.gguf"
PROMPT="$EXP/results/host-smoke/rendered/short.txt"
SERIAL=R5CW81PR8SY
REMOTE=/data/local/tmp/vibevoice-0029-lfm2.5-2.6b-android
DEFAULT_ADB="$HOME/Android/Sdk/platform-tools/adb"
[[ -x "$DEFAULT_ADB" ]] || DEFAULT_ADB=adb
ADB=${ADB:-$DEFAULT_ADB}
OUT="$EXP/.local/phone-$(date -u +%Y%m%dT%H%M%SZ)-smoke"
LOCK="$ROOT/artifacts/locks/phone.lock"
CLEANUP_STATE=not_started
REMOTE_PID=
ADB_RUN_PID=
MEMORY_PID=
mkdir -p "$OUT" "$ROOT/artifacts/locks"

exec 9>"$LOCK"
flock -n 9 || { echo "phone lock busy: $LOCK" >&2; exit 3; }
adb_cmd() { (exec 9>&-; "$ADB" -s "$SERIAL" "$@"); }
capture_optional() {
  local output=$1 reason=$2
  shift 2
  if ! "$@" >"$output" 2>"$output.stderr"; then
    printf '%s\n' "$reason" >"$output.unavailable-reason.txt"
  fi
}
cleanup() {
  set +e
  if [[ -n "$REMOTE_PID" ]]; then
    current=$(adb_cmd shell "cat '/proc/$REMOTE_PID/cmdline' 2>/dev/null" 2>/dev/null | tr '\0' ' ')
    if [[ "$current" == *"$REMOTE/llama-completion"* || "$current" == *"./llama-completion"* ]]; then
      adb_cmd shell "kill '$REMOTE_PID'" >/dev/null 2>&1
    fi
  fi
  [[ -n "$MEMORY_PID" ]] && kill "$MEMORY_PID" >/dev/null 2>&1
  [[ -n "$ADB_RUN_PID" ]] && wait "$ADB_RUN_PID" >/dev/null 2>&1
  adb_cmd shell "test ! -e '$REMOTE' || rm -rf '$REMOTE'" >/dev/null 2>&1
  if adb_cmd shell "test ! -e '$REMOTE'" >/dev/null 2>&1; then
    CLEANUP_STATE=verified_absent
  else
    CLEANUP_STATE=failed
  fi
  printf '{"remote_root":"%s","cleanup_state":"%s"}\n' "$REMOTE" "$CLEANUP_STATE" >"$OUT/cleanup.json"
}
trap cleanup EXIT INT TERM

BINARY="$STAGE/llama-completion"
[[ -x "$BINARY" && -f "$MODEL" && -f "$PROMPT" ]] || {
  echo "missing executable, model, or rendered prompt" >&2; exit 4;
}
binary_sha=$(jq -er '.runtime.android_build.binary_sha256 | select(type == "string")' "$CONTRACT")
model_sha=$(jq -er '.deployment_artifact.sha256' "$CONTRACT")
prompt_sha=$(jq -er '.tokenizer_and_template.prompt_inventory.short.rendered_sha256' "$CONTRACT")
printf '%s  %s\n%s  %s\n%s  %s\n' \
  "$binary_sha" llama-completion "$model_sha" model.gguf "$prompt_sha" short.txt \
  >"$OUT/expected-sha256.txt"
sha256sum "$BINARY" "$MODEL" "$PROMPT" | sed \
  -e "s#  $BINARY#  llama-completion#" \
  -e "s#  $MODEL#  model.gguf#" \
  -e "s#  $PROMPT#  short.txt#" >"$OUT/local-sha256.txt"
diff -u "$OUT/expected-sha256.txt" "$OUT/local-sha256.txt" >"$OUT/local-hash-diff.txt"

adb_cmd get-state >"$OUT/adb-state.txt"
model=$(adb_cmd shell getprop ro.product.model | tr -d '\r')
soc=$(adb_cmd shell getprop ro.soc.model | tr -d '\r')
abi=$(adb_cmd shell getprop ro.product.cpu.abi | tr -d '\r')
[[ "$model" == SM-S918B && "$soc" == SM8550 && "$abi" == arm64-v8a ]] || {
  echo "wrong device identity: model=$model soc=$soc abi=$abi" >&2; exit 5;
}
{
  printf 'serial=%s\nmodel=%s\nsoc=%s\nabi=%s\n' "$SERIAL" "$model" "$soc" "$abi"
  printf 'build_fingerprint='; adb_cmd shell getprop ro.build.fingerprint | tr -d '\r'
  printf 'android_sdk='; adb_cmd shell getprop ro.build.version.sdk | tr -d '\r'
} >"$OUT/device.txt"
adb_cmd shell df -k /data/local/tmp | tr -d '\r' >"$OUT/storage-before.txt"
available_kb=$(awk 'NR==2 {print $4}' "$OUT/storage-before.txt")
[[ "$available_kb" =~ ^[0-9]+$ && "$available_kb" -ge 5000000 ]] || {
  echo "need at least 5,000,000 KiB free under /data/local/tmp" >&2; exit 6;
}
capture_optional "$OUT/battery-before.txt" "dumpsys battery was unavailable to the shell" adb_cmd shell dumpsys battery
capture_optional "$OUT/thermal-before.txt" "dumpsys thermalservice was unavailable to the shell" adb_cmd shell dumpsys thermalservice
if adb_cmd shell "test -e '$REMOTE'" >/dev/null 2>&1; then
  echo "remote experiment root already exists; refusing to overwrite" >&2; exit 7
fi
adb_cmd shell "mkdir -p '$REMOTE'"
adb_cmd push "$BINARY" "$REMOTE/llama-completion" >"$OUT/push-binary.txt"
adb_cmd push "$MODEL" "$REMOTE/model.gguf" >"$OUT/push-model.txt"
adb_cmd push "$PROMPT" "$REMOTE/short.txt" >"$OUT/push-prompt.txt"
adb_cmd shell "chmod 755 '$REMOTE/llama-completion'; cd '$REMOTE' && sha256sum llama-completion model.gguf short.txt" \
  | tr -d '\r' >"$OUT/remote-sha256.txt"
diff -u "$OUT/expected-sha256.txt" "$OUT/remote-sha256.txt" >"$OUT/remote-hash-diff.txt"

set +e
(
  exec 9>&-
  ulimit -f 32768
  timeout --signal=TERM --kill-after=5s 1800s "$ADB" -s "$SERIAL" shell \
    "cd '$REMOTE' && echo \$\$ > runner.pid && exec ./llama-completion -m ./model.gguf -f ./short.txt -n 64 -c 8192 -t 4 -tb 4 --no-warmup --no-display-prompt --simple-io -no-cnv --temp 0 --override-kv tokenizer.ggml.add_bos_token=bool:false"
) >"$OUT/output.txt" 2>"$OUT/stderr.log" &
ADB_RUN_PID=$!
for _ in $(seq 1 200); do
  REMOTE_PID=$(adb_cmd shell "cat '$REMOTE/runner.pid' 2>/dev/null" | tr -d '\r') || true
  [[ "$REMOTE_PID" =~ ^[0-9]+$ ]] && break
  sleep 0.05
done
if [[ "$REMOTE_PID" =~ ^[0-9]+$ ]]; then
  (
    exec 9>&-
    "$ADB" -s "$SERIAL" shell "while kill -0 '$REMOTE_PID' 2>/dev/null; do date +%s.%N; cat '/proc/$REMOTE_PID/smaps_rollup' 2>/dev/null; grep -E '^(VmHWM|VmRSS|Threads):' '/proc/$REMOTE_PID/status' 2>/dev/null; echo --; sleep 0.1; done"
  ) >"$OUT/memory-samples.txt" 2>"$OUT/memory-sampler.stderr.log" &
  MEMORY_PID=$!
else
  REMOTE_PID=
  printf '%s\n' "runner PID was unavailable; sampled PSS and VmHWM are null" >"$OUT/memory-samples.unavailable-reason.txt"
fi
wait "$ADB_RUN_PID"
run_exit=$?
ADB_RUN_PID=
[[ -n "$MEMORY_PID" ]] && wait "$MEMORY_PID" || true
MEMORY_PID=
set -e
printf '%s\n' "$run_exit" >"$OUT/exit-code.txt"
sha256sum "$OUT/output.txt" "$OUT/stderr.log" >"$OUT/output-sha256.txt"
capture_optional "$OUT/battery-after.txt" "dumpsys battery was unavailable to the shell" adb_cmd shell dumpsys battery
capture_optional "$OUT/thermal-after.txt" "dumpsys thermalservice was unavailable to the shell" adb_cmd shell dumpsys thermalservice
cleanup
trap - EXIT INT TERM
[[ "$CLEANUP_STATE" == verified_absent ]] || exit 8
printf '%s\n' "$OUT"
exit "$run_exit"

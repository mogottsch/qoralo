#!/usr/bin/env bash
set -euo pipefail

[[ "${PHONE_RUN_APPROVED:-}" == yes && "${PI_PHONE_PRIORITY_TRANSFERRED:-}" == yes ]] || {
  echo "set PHONE_RUN_APPROVED=yes and PI_PHONE_PRIORITY_TRANSFERRED=yes only after Pi explicitly transfers phone priority" >&2
  exit 2
}
ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0032-qwen-3.5-2b-android-qnn-htp"
ET="$EXP/.local/executorch"
QNN=${QNN_SDK_ROOT:-/home/moritz/opt/qairt/2.49.0.260730}
PTE=${PTE:-$EXP/.local/exact-qnn/qwen35-2b-w4a16-qnn.pte}
RUNNER="$ET/build-android/examples/qualcomm/executor_runner/qwen35_explicit_state_runner"
PROMPT_IDS=${PROMPT_IDS:-$EXP/protocol/token-ids/short.int32le}
BACKEND="$ET/build-android/backends/qualcomm/libqnn_executorch_backend.so"
SERIAL=${SERIAL:-R5CW81PR8SY}
REMOTE=/data/local/tmp/vibevoice-0032-qwen35-qnn-viability
DEFAULT_ADB="$HOME/Android/Sdk/platform-tools/adb"
[[ -x "$DEFAULT_ADB" ]] || DEFAULT_ADB=adb
ADB=${ADB:-$DEFAULT_ADB}
OUT=${OUT:-$EXP/.local/phone-$(date -u +%Y%m%dT%H%M%SZ)-viability}
RUN_TIMEOUT_SECONDS=${RUN_TIMEOUT_SECONDS:-1800}
LOCK="$ROOT/artifacts/locks/phone.lock"
CLEANUP_STATE=not_started
PROCESS_CLEANUP_STATE=not_started
mkdir -p "$OUT"

exec 9>"$LOCK"
flock -n 9 || { echo "phone lock busy: $LOCK" >&2; exit 3; }
adb_cmd() { (exec 9>&-; "$ADB" -s "$SERIAL" "$@"); }
cleanup() {
  set +e
  # This runner name and remote root are unique to experiment 0032.
  adb_cmd shell "pidof qwen35_explicit_state_runner 2>/dev/null | tr ' ' '\n' | while read pid; do test -z \"\$pid\" || kill \"\$pid\"; done" >/dev/null 2>&1
  sleep 1
  if [[ -z "$(adb_cmd shell "pidof qwen35_explicit_state_runner 2>/dev/null" | tr -d '\r[:space:]')" ]]; then
    PROCESS_CLEANUP_STATE=verified_absent
  else
    PROCESS_CLEANUP_STATE=failed
  fi
  adb_cmd shell "test ! -e '$REMOTE' || rm -rf '$REMOTE'" >/dev/null 2>&1
  if adb_cmd shell "test ! -e '$REMOTE'" >/dev/null 2>&1; then
    CLEANUP_STATE=verified_absent
  else
    CLEANUP_STATE=failed
  fi
  printf '{"remote_root":"%s","cleanup_state":"%s","process_cleanup_state":"%s"}\n' \
    "$REMOTE" "$CLEANUP_STATE" "$PROCESS_CLEANUP_STATE" >"$OUT/cleanup.json"
}
trap cleanup EXIT INT TERM

for path in "$PTE" "$RUNNER" "$PROMPT_IDS" "$BACKEND" \
  "$QNN/lib/aarch64-android/libQnnHtp.so" \
  "$QNN/lib/aarch64-android/libQnnSystem.so" \
  "$QNN/lib/aarch64-android/libQnnHtpV73Stub.so" \
  "$QNN/lib/hexagon-v73/unsigned/libQnnHtpV73Skel.so"; do
  [[ -f "$path" ]] || { echo "missing $path" >&2; exit 4; }
done
expected_hash() {
  local expected=$1 path=$2
  local observed
  observed=$(sha256sum "$path" | cut -d' ' -f1)
  [[ "$observed" == "$expected" ]] || {
    echo "hash mismatch for $path: $observed != $expected" >&2
    exit 4
  }
}
expected_hash bfdae1c3327c954566ec0d4a5a0ee8873eb145d0921bc3f9d988a6a2557be6df "$PTE"
expected_hash 0b5bef7984738d60d2f4b2f4dbae1c13f1f5914b75b8cc00e5ae3e2ed0f81fc5 "$RUNNER"
expected_hash dcfd3c24cb3f8a370f91b38c9720d7e3dd5c623d491fed70ded3726ec49048f4 "$PROMPT_IDS"
expected_hash 0d97f44ac9abcaf7e5e025440c41c3727acc6315f2bd2613ab1cb31afe508b37 "$BACKEND"
expected_hash a09b3af28342331b3ec9e57ecbe42bfe54a5fff37c4323ce5685c395ae3ee604 "$QNN/lib/aarch64-android/libQnnHtp.so"
expected_hash 536201ed918f4066f9ef35671198c072faf9ef04af24545f5fae0fc79aa05baa "$QNN/lib/aarch64-android/libQnnSystem.so"
expected_hash 2912cc4f29cc5163c36c6c58f931bd08b798ccf8545a670a9498549f95b9036f "$QNN/lib/aarch64-android/libQnnHtpV73Stub.so"
expected_hash bd54463547f0234d06045699b1f747b7d9d3e3b581874840af50c295b3124f25 "$QNN/lib/hexagon-v73/unsigned/libQnnHtpV73Skel.so"

adb_cmd get-state >"$OUT/adb-state.txt"
model=$(adb_cmd shell getprop ro.product.model | tr -d '\r')
soc=$(adb_cmd shell getprop ro.soc.model | tr -d '\r')
abi=$(adb_cmd shell getprop ro.product.cpu.abi | tr -d '\r')
[[ "$model" == SM-S918B && "$soc" == SM8550 && "$abi" == arm64-v8a ]] || {
  echo "wrong device: model=$model soc=$soc abi=$abi" >&2
  exit 5
}
{
  printf 'serial=%s\nmodel=%s\nsoc=%s\nabi=%s\n' "$SERIAL" "$model" "$soc" "$abi"
  printf 'build_fingerprint='; adb_cmd shell getprop ro.build.fingerprint | tr -d '\r'
  printf 'android_sdk='; adb_cmd shell getprop ro.build.version.sdk | tr -d '\r'
} >"$OUT/device.txt"
adb_cmd shell dumpsys battery >"$OUT/battery-before.txt" 2>"$OUT/battery-before.stderr" || true
adb_cmd shell dumpsys thermalservice >"$OUT/thermal-before.txt" 2>"$OUT/thermal-before.stderr" || true
adb_cmd shell df -k /data/local/tmp | tr -d '\r' >"$OUT/storage-before.txt"

if adb_cmd shell "test -e '$REMOTE'" >/dev/null 2>&1; then
  echo "remote root exists; refusing to overwrite" >&2
  exit 6
fi
adb_cmd shell "mkdir -p '$REMOTE/outputs'"

files=(
  "$PTE:model.pte"
  "$RUNNER:qwen35_explicit_state_runner"
  "$PROMPT_IDS:short.int32le"
  "$BACKEND:libqnn_executorch_backend.so"
  "$QNN/lib/aarch64-android/libQnnHtp.so:libQnnHtp.so"
  "$QNN/lib/aarch64-android/libQnnSystem.so:libQnnSystem.so"
  "$QNN/lib/aarch64-android/libQnnHtpV73Stub.so:libQnnHtpV73Stub.so"
  "$QNN/lib/hexagon-v73/unsigned/libQnnHtpV73Skel.so:libQnnHtpV73Skel.so"
)
: >"$OUT/local-sha256.txt"
for item in "${files[@]}"; do
  source=${item%%:*}; name=${item##*:}
  sha256sum "$source" | sed "s#  .*#  $name#" >>"$OUT/local-sha256.txt"
  adb_cmd push "$source" "$REMOTE/$name" >>"$OUT/push.log"
done
adb_cmd shell "chmod 755 '$REMOTE/qwen35_explicit_state_runner'; cd '$REMOTE' && sha256sum model.pte qwen35_explicit_state_runner short.int32le libqnn_executorch_backend.so libQnnHtp.so libQnnSystem.so libQnnHtpV73Stub.so libQnnHtpV73Skel.so" \
  | tr -d '\r' >"$OUT/remote-sha256.txt"
diff -u <(sort "$OUT/local-sha256.txt") <(sort "$OUT/remote-sha256.txt") >"$OUT/hash-diff.txt"

set +e
timeout --signal=TERM --kill-after=5s "$RUN_TIMEOUT_SECONDS" \
  "$ADB" -s "$SERIAL" shell \
  "cd '$REMOTE' && export LD_LIBRARY_PATH='$REMOTE' && export ADSP_LIBRARY_PATH='$REMOTE;/vendor/lib/rfsa/adsp;/vendor/dsp/cdsp;/system/lib/rfsa/adsp' && ./qwen35_explicit_state_runner --model_path=model.pte --prompt_ids=short.int32le --output_ids=generated.int32le --max_new_tokens=1 --metrics_path=metrics.json --etdump_path=etdump.etdp --log_level=5 --profile_level=2" \
  >"$OUT/runner.stdout.log" 2>"$OUT/runner.stderr.log"
run_exit=$?
set -e
printf '%s\n' "$run_exit" >"$OUT/exit-code.txt"
adb_cmd shell "cd '$REMOTE' && find . -maxdepth 2 -type f -printf '%p %s bytes\\n' 2>/dev/null || toybox find . -maxdepth 2 -type f" \
  | tr -d '\r' >"$OUT/remote-files.txt" || true
adb_cmd pull "$REMOTE/etdump.etdp" "$OUT/etdump.etdp" >"$OUT/pull-etdump.log" 2>&1 || true
adb_cmd pull "$REMOTE/metrics.json" "$OUT/metrics.json" >"$OUT/pull-metrics.log" 2>&1 || true
adb_cmd pull "$REMOTE/generated.int32le" "$OUT/generated.int32le" >"$OUT/pull-generated.log" 2>&1 || true
adb_cmd shell dumpsys battery >"$OUT/battery-after.txt" 2>"$OUT/battery-after.stderr" || true
adb_cmd shell dumpsys thermalservice >"$OUT/thermal-after.txt" 2>"$OUT/thermal-after.stderr" || true
sha256sum "$OUT"/runner.* "$OUT"/etdump.etdp "$OUT"/metrics.json "$OUT"/generated.int32le 2>/dev/null >"$OUT/evidence-sha256.txt" || true
cleanup
trap - EXIT INT TERM
[[ "$CLEANUP_STATE" == verified_absent && "$PROCESS_CLEANUP_STATE" == verified_absent ]] || exit 7
printf '%s\n' "$OUT"
exit "$run_exit"

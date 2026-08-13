#!/usr/bin/env bash
# Proven, non-root physical-HTP control for experiment 0010.
# This script intentionally does not run the vocoder.
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: PHONE_USE_CONFIRMED=yes run_tiny_htp_smoke.sh \
  SERIAL ANDROID_RUNTIME_DIR QAIRT_ROOT SMOKE_MODEL OUTPUT_DIR

ANDROID_RUNTIME_DIR must contain:
  libonnxruntime.so libc++_shared.so onnxruntime_perf_test

OUTPUT_DIR must be below this experiment's ignored work/ directory.
The caller must obtain fresh human confirmation immediately before invoking it.
EOF
  exit 2
}

[[ $# -eq 5 ]] || usage
[[ "${PHONE_USE_CONFIRMED:-}" == "yes" ]] || {
  echo "refusing phone use: set PHONE_USE_CONFIRMED=yes only after fresh human confirmation" >&2
  exit 2
}

SERIAL="$1"
ANDROID_RUNTIME_DIR="$(realpath "$2")"
QAIRT_ROOT="$(realpath "$3")"
SMOKE_MODEL="$(realpath "$4")"
OUTPUT_DIR="$(realpath -m "$5")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$EXP_DIR/../.." && pwd)"
ADB="${ADB:-$HOME/Android/Sdk/platform-tools/adb}"
REMOTE=/data/local/tmp/vibevoice-qnn-0010-smoke
LOCK="$REPO_ROOT/artifacts/locks/phone.lock"

case "$OUTPUT_DIR/" in
  "$EXP_DIR/work/"*) ;;
  *) echo "OUTPUT_DIR must be below $EXP_DIR/work" >&2; exit 2 ;;
esac

required=(
  "$ANDROID_RUNTIME_DIR/libonnxruntime.so"
  "$ANDROID_RUNTIME_DIR/libc++_shared.so"
  "$ANDROID_RUNTIME_DIR/onnxruntime_perf_test"
  "$QAIRT_ROOT/lib/aarch64-android/libQnnHtp.so"
  "$QAIRT_ROOT/lib/aarch64-android/libQnnHtpPrepare.so"
  "$QAIRT_ROOT/lib/aarch64-android/libQnnSystem.so"
  "$QAIRT_ROOT/lib/aarch64-android/libQnnHtpV73Stub.so"
  "$QAIRT_ROOT/lib/hexagon-v73/unsigned/libQnnHtpV73Skel.so"
  "$SMOKE_MODEL"
)
for path in "${required[@]}"; do
  [[ -f "$path" ]] || { echo "missing required file: $path" >&2; exit 2; }
done
[[ -x "$ADB" ]] || { echo "adb is not executable: $ADB" >&2; exit 2; }

mkdir -p "$OUTPUT_DIR"
exec 9>"$LOCK"
flock -n 9 || { echo "phone lock is already held: $LOCK" >&2; exit 3; }

adb_cmd() {
  "$ADB" -s "$SERIAL" "$@" </dev/null
}

cleanup() {
  set +e
  adb_cmd shell "rm -rf '$REMOTE'" >"$OUTPUT_DIR/cleanup.stdout.log" 2>"$OUTPUT_DIR/cleanup.stderr.log"
  local status=$?
  printf '%s\n' "$status" >"$OUTPUT_DIR/cleanup.exit-code"
}
trap cleanup EXIT

mapfile -t online < <("$ADB" devices | awk 'NR > 1 && $2 == "device" {print $1}')
[[ ${#online[@]} -eq 1 && "${online[0]}" == "$SERIAL" ]] || {
  echo "expected exactly the requested authorized online device" >&2
  exit 4
}
[[ "$(adb_cmd shell getprop ro.product.model | tr -d '\r')" == "SM-S918B" ]]
[[ "$(adb_cmd shell getprop ro.soc.model | tr -d '\r')" == "SM8550" ]]
[[ "$(adb_cmd shell getprop sys.boot_completed | tr -d '\r')" == "1" ]]

sha256sum "${required[@]}" >"$OUTPUT_DIR/local-sha256.txt"
adb_cmd shell "rm -rf '$REMOTE' && mkdir -p '$REMOTE'"

push_as() {
  adb_cmd push "$1" "$REMOTE/$2" >/dev/null
}
push_as "$ANDROID_RUNTIME_DIR/libonnxruntime.so" libonnxruntime.so
push_as "$ANDROID_RUNTIME_DIR/libc++_shared.so" libc++_shared.so
push_as "$ANDROID_RUNTIME_DIR/onnxruntime_perf_test" onnxruntime_perf_test
push_as "$QAIRT_ROOT/lib/aarch64-android/libQnnHtp.so" libQnnHtp.so
# QAIRT 2.49 loads this dynamically even though libQnnHtp.so has no ELF NEEDED entry for it.
push_as "$QAIRT_ROOT/lib/aarch64-android/libQnnHtpPrepare.so" libQnnHtpPrepare.so
push_as "$QAIRT_ROOT/lib/aarch64-android/libQnnSystem.so" libQnnSystem.so
push_as "$QAIRT_ROOT/lib/aarch64-android/libQnnHtpV73Stub.so" libQnnHtpV73Stub.so
push_as "$QAIRT_ROOT/lib/hexagon-v73/unsigned/libQnnHtpV73Skel.so" libQnnHtpV73Skel.so
push_as "$SMOKE_MODEL" qdq-add.onnx
adb_cmd shell "chmod 755 '$REMOTE/onnxruntime_perf_test'; cd '$REMOTE' && sha256sum *" \
  >"$OUTPUT_DIR/remote-sha256.txt"

provider_options="backend_path|$REMOTE/libQnnHtp.so profiling_level|detailed profiling_file_path|$REMOTE/smoke-qnn.csv offload_graph_io_quantization|0 htp_performance_mode|burst soc_model|43"
remote_command="cd '$REMOTE' && export LD_LIBRARY_PATH='$REMOTE' && export ADSP_LIBRARY_PATH='$REMOTE;/vendor/lib/rfsa/adsp;/vendor/dsp/cdsp;/system/lib/rfsa/adsp;/vendor/dsp' && ./onnxruntime_perf_test -e qnn -i '$provider_options' -C 'session.disable_cpu_ep_fallback|1' -m times -r 1 -I -x 1 -y 1 -v '$REMOTE/qdq-add.onnx'"

set +e
timeout 180 "$ADB" -s "$SERIAL" shell "$remote_command" </dev/null \
  >"$OUTPUT_DIR/run.stdout.log" 2>"$OUTPUT_DIR/run.stderr.log"
status=$?
set -e
printf '%s\n' "$status" >"$OUTPUT_DIR/run.exit-code"
adb_cmd pull "$REMOTE/smoke-qnn.csv" "$OUTPUT_DIR/smoke-qnn.csv" >/dev/null 2>&1 || true
(( status == 0 )) || {
  tail -200 "$OUTPUT_DIR/run.stdout.log" >&2 || true
  tail -300 "$OUTPUT_DIR/run.stderr.log" >&2 || true
  exit "$status"
}

profile="$OUTPUT_DIR/smoke-qnn.csv"
[[ -s "$profile" ]]
grep -Fq 'RPC (execute) time' "$profile"
grep -Fq 'QNN accelerator (execute) time' "$profile"
grep -Fq 'Accelerator (execute) time (cycles)' "$profile"
grep -Fq 'Number of HVX threads used' "$profile"

printf '%s\n' "passed: physical QNN HTP profile captured at $profile"

#!/usr/bin/env bash
set -euo pipefail

MODE=${1:?usage: run_phone.sh smoke|campaign}
case "$MODE" in smoke|campaign) ;; *) echo "invalid mode: $MODE" >&2; exit 2;; esac
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
EXP="$ROOT/experiments/0030-qwen-3.5-2b-android-vulkan-gpu"
STAGE="$EXP/.local/android-stage"
SERIAL=R5CW81PR8SY
REMOTE=/data/local/tmp/vibevoice-0030-qwen-3.5-2b-android-vulkan-gpu
PORT=8030
DEFAULT_ADB="$HOME/Android/Sdk/platform-tools/adb"
[[ -x "$DEFAULT_ADB" ]] || DEFAULT_ADB=adb
ADB=${ADB:-$DEFAULT_ADB}
if [[ -n "${CLIENT_BASE:-}" ]]; then
  CLIENT_BASE=$CLIENT_BASE
elif [[ "${ADB_SERVER_SOCKET:-}" =~ ^tcp:([^:]+):[0-9]+$ ]]; then
  # ADB forward listeners live on the Windows-hosted daemon when WSL uses a
  # remote ADB server; connect through that host rather than WSL localhost.
  CLIENT_BASE="http://${BASH_REMATCH[1]}:$PORT"
else
  CLIENT_BASE="http://127.0.0.1:$PORT"
fi
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)-$MODE
OUT="$EXP/.local/phone-$RUN_ID"
LOCK="$ROOT/artifacts/locks/phone.lock"
SERVER_PID=
ADB_SERVER_PID=
MEMORY_PID=
GPU_SAMPLER_PID=
CLEANUP_STATE=not_started
mkdir -p "$OUT" "$ROOT/artifacts/locks"

exec 9>"$LOCK"
flock -n 9 || { echo "phone lock busy: $LOCK" >&2; exit 3; }

adb_cmd() {
  # Do not let subprocesses inherit the public phone lock descriptor.
  (exec 9>&-; "$ADB" -s "$SERIAL" "$@")
}

cleanup() {
  set +e
  if [[ -n "$SERVER_PID" ]]; then
    current=$(adb_cmd shell "cat /proc/$SERVER_PID/cmdline 2>/dev/null" 2>/dev/null | tr '\0' ' ')
    if [[ "$current" == *"$REMOTE/llama-server"* || "$current" == *"./llama-server"* ]]; then
      adb_cmd shell "kill $SERVER_PID" >/dev/null 2>&1
    fi
  fi
  [[ -n "$MEMORY_PID" ]] && kill "$MEMORY_PID" >/dev/null 2>&1
  [[ -n "$GPU_SAMPLER_PID" ]] && kill "$GPU_SAMPLER_PID" >/dev/null 2>&1
  [[ -n "$ADB_SERVER_PID" ]] && wait "$ADB_SERVER_PID" >/dev/null 2>&1
  adb_cmd forward --remove "tcp:$PORT" >/dev/null 2>&1
  if adb_cmd shell "test -d '$REMOTE'" >/dev/null 2>&1; then
    adb_cmd shell "rm -rf '$REMOTE'" >/dev/null 2>&1
  fi
  if adb_cmd shell "test ! -e '$REMOTE'" >/dev/null 2>&1; then CLEANUP_STATE=verified_absent; else CLEANUP_STATE=failed; fi
  printf '{"remote_root":"%s","cleanup_state":"%s"}\n' "$REMOTE" "$CLEANUP_STATE" >"$OUT/cleanup.json"
}
trap cleanup EXIT INT TERM

[[ -x "$STAGE/llama-server" ]] || { echo "missing executable staged server" >&2; exit 4; }
[[ -f "$STAGE/model.gguf" ]] || { echo "missing staged model" >&2; exit 4; }
printf '%s  %s\n' \
  b806fc03df6510eb7a141aea093cec7a878a2aa7456ea076a84791fadec68c00 llama-server \
  aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223 model.gguf \
  >"$OUT/expected-sha256.txt"
(cd "$STAGE" && sha256sum -c "$OUT/expected-sha256.txt") >"$OUT/local-hash-check.txt"

adb_cmd get-state | tee "$OUT/adb-state.txt"
model=$(adb_cmd shell getprop ro.product.model | tr -d '\r')
soc=$(adb_cmd shell getprop ro.soc.model | tr -d '\r')
abi=$(adb_cmd shell getprop ro.product.cpu.abi | tr -d '\r')
[[ "$model" == SM-S918B && "$soc" == SM8550 && "$abi" == arm64-v8a ]] || {
  echo "wrong device identity: model=$model soc=$soc abi=$abi" >&2; exit 5;
}
{
  printf 'serial=%s\nmodel=%s\nsoc=%s\nabi=%s\n' "$SERIAL" "$model" "$soc" "$abi"
  printf 'build_fingerprint='; adb_cmd shell getprop ro.build.fingerprint | tr -d '\r'
  printf 'build_id='; adb_cmd shell getprop ro.build.id | tr -d '\r'
  printf 'android_release='; adb_cmd shell getprop ro.build.version.release | tr -d '\r'
  printf 'android_sdk='; adb_cmd shell getprop ro.build.version.sdk | tr -d '\r'
} >"$OUT/device.txt"
adb_cmd shell df -k /data/local/tmp >"$OUT/storage-before.txt"
adb_cmd shell dumpsys battery >"$OUT/battery-before.txt"
adb_cmd shell dumpsys thermalservice >"$OUT/thermal-before.txt"
adb_cmd shell dumpsys power >"$OUT/power-before.txt"
adb_cmd shell 'for p in /sys/class/kgsl/kgsl-3d0/gpubusy /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage /sys/class/kgsl/kgsl-3d0/devfreq/cur_freq /sys/class/kgsl/kgsl-3d0/devfreq/available_frequencies; do echo "== $p"; cat "$p" 2>&1 || true; done' >"$OUT/gpu-before.txt"
if adb_cmd shell "test -e '$REMOTE'" >/dev/null 2>&1; then
  echo "remote experiment root already exists; refusing to overwrite: $REMOTE" >&2
  exit 6
fi
adb_cmd shell "mkdir -p '$REMOTE/cache'"
adb_cmd push "$STAGE/llama-server" "$REMOTE/llama-server" | tee "$OUT/push-server.txt"
adb_cmd push "$STAGE/model.gguf" "$REMOTE/model.gguf" | tee "$OUT/push-model.txt"
adb_cmd shell "chmod 755 '$REMOTE/llama-server'"
adb_cmd shell "cd '$REMOTE' && sha256sum llama-server model.gguf" | tr -d '\r' >"$OUT/remote-sha256.txt"
diff -u "$OUT/expected-sha256.txt" "$OUT/remote-sha256.txt" >"$OUT/stage-hash-diff.txt"
adb_cmd forward "tcp:$PORT" "tcp:$PORT" >"$OUT/forward.txt"

SETUP_START=$(python3 -c 'import time; print(time.monotonic_ns())')
(
  exec 9>&-
  "$ADB" -s "$SERIAL" shell "cd '$REMOTE' && echo \$\$ > server.pid && exec ./llama-server -m ./model.gguf --host 127.0.0.1 --port $PORT --ctx-size 8192 --parallel 1 --threads 4 --threads-batch 4 --device Vulkan0 --gpu-layers 25 --split-mode none --main-gpu 0 --reasoning off --jinja --slot-save-path ./cache --no-webui"
) >"$OUT/server.stdout.log" 2>"$OUT/server.stderr.log" &
ADB_SERVER_PID=$!
for _ in $(seq 1 200); do
  SERVER_PID=$(adb_cmd shell "cat '$REMOTE/server.pid' 2>/dev/null" | tr -d '\r') || true
  [[ "$SERVER_PID" =~ ^[0-9]+$ ]] && break
  sleep 0.05
done
[[ "$SERVER_PID" =~ ^[0-9]+$ ]] || { echo "server pid not available" >&2; exit 7; }

(
  exec 9>&-
  "$ADB" -s "$SERIAL" shell "while kill -0 '$SERVER_PID' 2>/dev/null; do date +%s.%N; cat '/proc/$SERVER_PID/smaps_rollup' 2>/dev/null; grep -E '^(VmHWM|VmRSS|Threads):' '/proc/$SERVER_PID/status' 2>/dev/null; echo --; sleep 0.1; done"
) >"$OUT/memory-samples.txt" 2>"$OUT/memory-sampler.stderr.log" &
MEMORY_PID=$!
(
  exec 9>&-
  "$ADB" -s "$SERIAL" shell "while kill -0 '$SERVER_PID' 2>/dev/null; do date +%s.%N; for p in /sys/class/kgsl/kgsl-3d0/gpubusy /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage /sys/class/kgsl/kgsl-3d0/devfreq/cur_freq; do printf '%s=' \"\$p\"; cat \"\$p\" 2>/dev/null || printf 'unavailable\\n'; done; echo --; sleep 0.1; done"
) >"$OUT/gpu-samples.txt" 2>"$OUT/gpu-sampler.stderr.log" &
GPU_SAMPLER_PID=$!

printf '%s\n' "$CLIENT_BASE" >"$OUT/client-base.txt"
python3 "$EXP/tools/run_client.py" \
  --base "$CLIENT_BASE" \
  --mode "$MODE" \
  --output "$OUT/client" \
  --workloads "$ROOT/protocols/android-llm-benchmark/workloads/inference-v1" \
  --setup-start-monotonic-ns "$SETUP_START" \
  --backend-proof-log "$OUT/server.stderr.log"

adb_cmd shell "kill '$SERVER_PID'"
wait "$ADB_SERVER_PID" || true
ADB_SERVER_PID=
kill "$MEMORY_PID" >/dev/null 2>&1 || true
wait "$MEMORY_PID" || true
MEMORY_PID=
kill "$GPU_SAMPLER_PID" >/dev/null 2>&1 || true
wait "$GPU_SAMPLER_PID" || true
GPU_SAMPLER_PID=
adb_cmd shell dumpsys battery >"$OUT/battery-after.txt"
adb_cmd shell dumpsys thermalservice >"$OUT/thermal-after.txt"
adb_cmd shell dumpsys power >"$OUT/power-after.txt"
adb_cmd shell 'for p in /sys/class/kgsl/kgsl-3d0/gpubusy /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage /sys/class/kgsl/kgsl-3d0/devfreq/cur_freq /sys/class/kgsl/kgsl-3d0/devfreq/available_frequencies; do echo "== $p"; cat "$p" 2>&1 || true; done' >"$OUT/gpu-after.txt"
cleanup
trap - EXIT INT TERM
printf '%s\n' "$OUT"

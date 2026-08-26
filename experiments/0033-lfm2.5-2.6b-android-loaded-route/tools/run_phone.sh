#!/usr/bin/env bash
set -euo pipefail

ARM=${1:?usage: run_phone.sh cpu|opencl smoke|campaign}
MODE=${2:?usage: run_phone.sh cpu|opencl smoke|campaign}
case "$ARM" in cpu|opencl) ;; *) echo "invalid arm: $ARM" >&2; exit 2;; esac
case "$MODE" in smoke|campaign) ;; *) echo "invalid mode: $MODE" >&2; exit 2;; esac
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
EXP="$ROOT/experiments/0033-lfm2.5-2.6b-android-loaded-route"
SERIAL=R5CW81PR8SY
REMOTE="/data/local/tmp/vibevoice-0033-lfm2.5-2.6b-android-loaded-route-$ARM"
if [[ "$ARM" == cpu ]]; then
  STAGE="$EXP/.local/android-stage-cpu"; PORT=8033
  SERVER_SHA256=8ce2767eba7480326682d69963eeb483204ee1541c3b5b0c0ef409068ea2b217
  BACKEND_ENV=""; BACKEND_ARGS="--device none --gpu-layers 0"
else
  STAGE="$EXP/.local/android-stage-opencl"; PORT=8034
  SERVER_SHA256=64409e6e96a7d003ed6c68ec12363f3e6d7c34d46af40bc439cb84f060cd4ced
  BACKEND_ENV="GGML_OPENCL_PLATFORM=QUALCOMM GGML_OPENCL_DEVICE=Adreno GGML_OPENCL_KERNEL_CACHE_DIR=./cache/opencl"
  BACKEND_ARGS="--device GPUOpenCL --gpu-layers 31 --split-mode none --main-gpu 0 --flash-attn off --verbosity 5"
fi
MODEL_SHA256=02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed
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
COOLDOWN_SECONDS=${COOLDOWN_SECONDS:-180}
HEALTH_DEADLINE_SECONDS=${HEALTH_DEADLINE_SECONDS:-1200}
[[ "$COOLDOWN_SECONDS" =~ ^[0-9]+$ ]] || { echo "COOLDOWN_SECONDS must be a nonnegative integer" >&2; exit 2; }
[[ "$HEALTH_DEADLINE_SECONDS" =~ ^[1-9][0-9]*$ ]] || { echo "HEALTH_DEADLINE_SECONDS must be positive" >&2; exit 2; }
OUT="$EXP/.local/phone-$RUN_ID"
LOCK="$ROOT/artifacts/locks/phone.lock"
SERVER_PID=
ADB_SERVER_PID=
MEMORY_PID=
GPU_SAMPLER_PID=
REMOTE_CREATED=0
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
  if [[ "$REMOTE_CREATED" == 0 ]]; then
    CLEANUP_STATE=not_applicable_no_remote_creation
  else
    if adb_cmd shell "test -d '$REMOTE'" >/dev/null 2>&1; then
      adb_cmd shell "rm -rf '$REMOTE'" >/dev/null 2>&1
    fi
    if adb_cmd shell "test ! -e '$REMOTE'" >/dev/null 2>&1; then CLEANUP_STATE=verified_absent; else CLEANUP_STATE=failed; fi
  fi
  printf '{"remote_root":"%s","cleanup_state":"%s"}\n' "$REMOTE" "$CLEANUP_STATE" >"$OUT/cleanup.json"
}
trap cleanup EXIT INT TERM

[[ -x "$STAGE/llama-server" ]] || { echo "missing executable staged server" >&2; exit 4; }
[[ -f "$STAGE/model.gguf" ]] || { echo "missing staged model" >&2; exit 4; }
printf '%s  %s\n' \
  "$SERVER_SHA256" llama-server \
  "$MODEL_SHA256" model.gguf \
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
adb_cmd shell dumpsys battery >"$OUT/battery-pre-cooldown.txt"
adb_cmd shell dumpsys thermalservice >"$OUT/thermal-pre-cooldown.txt"
adb_cmd shell dumpsys power >"$OUT/power-pre-cooldown.txt"
COOLDOWN_START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
sleep "$COOLDOWN_SECONDS"
COOLDOWN_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '{"seconds":%s,"start_utc":"%s","end_utc":"%s","threshold_gated":false}\n' "$COOLDOWN_SECONDS" "$COOLDOWN_START" "$COOLDOWN_END" >"$OUT/cooldown.json"
adb_cmd shell dumpsys battery >"$OUT/battery-before.txt"
adb_cmd shell dumpsys thermalservice >"$OUT/thermal-before.txt"
adb_cmd shell dumpsys power >"$OUT/power-before.txt"
if [[ "$ARM" == opencl ]]; then
  adb_cmd shell 'printf "gpu_model="; cat /sys/class/kgsl/kgsl-3d0/gpu_model; printf "opencl_library="; ls -l /vendor/lib64/libOpenCL.so /system/vendor/lib64/libOpenCL.so 2>&1 || true' | tr -d '\r' >"$OUT/gpu-model.txt"
  grep -Eqi 'gpu_model=.*Adreno.*740' "$OUT/gpu-model.txt" || { echo "Adreno 740 sysfs proof missing" >&2; exit 5; }
fi
adb_cmd shell 'for p in /sys/class/kgsl/kgsl-3d0/gpubusy /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage /sys/class/kgsl/kgsl-3d0/devfreq/cur_freq /sys/class/kgsl/kgsl-3d0/devfreq/available_frequencies; do echo "== $p"; cat "$p" 2>&1 || true; done' >"$OUT/gpu-before.txt"
if adb_cmd shell "test -e '$REMOTE'" >/dev/null 2>&1; then
  echo "remote experiment root already exists; refusing to overwrite: $REMOTE" >&2
  exit 6
fi
REMOTE_CREATED=1
adb_cmd shell "mkdir -p '$REMOTE/cache/opencl'"
adb_cmd push "$STAGE/llama-server" "$REMOTE/llama-server" | tee "$OUT/push-server.txt"
adb_cmd push "$STAGE/model.gguf" "$REMOTE/model.gguf" | tee "$OUT/push-model.txt"
adb_cmd shell "chmod 755 '$REMOTE/llama-server'"
adb_cmd shell "cd '$REMOTE' && sha256sum llama-server model.gguf" | tr -d '\r' >"$OUT/remote-sha256.txt"
diff -u "$OUT/expected-sha256.txt" "$OUT/remote-sha256.txt" >"$OUT/stage-hash-diff.txt"
adb_cmd forward "tcp:$PORT" "tcp:$PORT" >"$OUT/forward.txt"
printf 'arm=%s\nserver_sha256=%s\nbackend_env=%s\nbackend_args=%s\n' "$ARM" "$SERVER_SHA256" "$BACKEND_ENV" "$BACKEND_ARGS" >"$OUT/backend-config.txt"

SETUP_START=$(python3 -c 'import time; print(time.monotonic_ns())')
(
  exec 9>&-
  "$ADB" -s "$SERIAL" shell "cd '$REMOTE' && echo \$\$ > server.pid && $BACKEND_ENV exec ./llama-server -m ./model.gguf --host 127.0.0.1 --port $PORT --ctx-size 8192 --parallel 1 --threads 4 --threads-batch 4 $BACKEND_ARGS --override-kv tokenizer.ggml.add_bos_token=bool:false --jinja --slot-save-path ./cache --no-webui"
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
CLIENT_ARGS=(
  --base "$CLIENT_BASE" --mode "$MODE" --backend "$ARM" --output "$OUT/client"
  --workloads "$ROOT/protocols/android-llm-benchmark/workloads/inference-v1"
  --setup-start-monotonic-ns "$SETUP_START" --health-deadline-seconds "$HEALTH_DEADLINE_SECONDS"
)
if [[ "$ARM" == opencl ]]; then CLIENT_ARGS+=(--backend-proof-log "$OUT/server.stderr.log" --gpu-model-proof "$OUT/gpu-model.txt"); fi
python3 "$EXP/tools/run_client.py" "${CLIENT_ARGS[@]}"

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

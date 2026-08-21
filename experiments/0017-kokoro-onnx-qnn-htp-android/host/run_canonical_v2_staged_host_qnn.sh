#!/usr/bin/env bash
# Re-run the complete canonical-v2 18-stage fallback-disabled host QNN gate.
# This is a host eligibility gate only; it never accesses the phone.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
EXP="$REPO/experiments/0017-kokoro-onnx-qnn-htp-android"
BUILD="$REPO/experiments/0010-supertonic-qnn-htp-feasibility/.local/ort-v1.27.1-qnn-2.49.0-host-patched-a08e17/Release"
QAIRT="${QAIRT_ROOT:-/home/moritz/opt/qairt/2.49.0.260730}"
MANIFEST="$EXP/work/canonical-v2/stages-v1/manifest.json"
MODELS="$EXP/work/canonical-v2/stages-v1/models"
INPUTS="$EXP/work/canonical-v2/frontend-official-v1"
RUNNER="$EXP/.local/bin/kokoro-canonical-stage-host-docker"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
OUT="$EXP/work/canonical-v2/stages-v1/qnn-host-$RUN_ID"
NAME="exp0017-canonical-qnn-$RUN_ID"
IMAGE="vibevoice-experiment-0010-qairt:2.49.0.260730-ubuntu22.04"

require_sha() {
  local expected=$1 path=$2
  [[ -f "$path" && ! -L "$path" ]] || { echo "missing regular file: $path" >&2; exit 2; }
  local actual
  actual=$(sha256sum "$path" | awk '{print $1}')
  [[ "$actual" == "$expected" ]] || {
    echo "SHA-256 mismatch: $path expected=$expected actual=$actual" >&2
    exit 2
  }
}

require_sha 3f21c996ec3d5a63b80cbceb9ff83a21cc86321cabfea3e2dedd1af4676fbad1 "$MANIFEST"
require_sha 938480879497262461dcc4632a0ebeebb92f721c9192441c17b406af8ac0e023 "$RUNNER"
require_sha 9c565b2a6ee1a811f188f3e3425a3188af58866988ce5a2197eeaacc81dde280 "$INPUTS/tokens.raw"
require_sha 8acaca07623d98a1085f6b182fb997d715dd1d67862e350567e6d9b1bc8ec71b "$INPUTS/style.raw"
require_sha e00e5eb9444182f352323374ef4e08ebcb784725fdd4fd612d7730540b3e0c8c "$INPUTS/speed.raw"
[[ -f "$BUILD/libonnxruntime.so" ]] || { echo "missing patched ORT build: $BUILD" >&2; exit 2; }
[[ -f "$QAIRT/lib/x86_64-linux-clang/libQnnHtp.so" ]] || { echo "missing pinned QAIRT/QNN backend: $QAIRT" >&2; exit 2; }
command -v docker >/dev/null
command -v timeout >/dev/null
command -v flock >/dev/null

python3 - "$REPO" "$MANIFEST" <<'PY'
import hashlib, json, sys
from pathlib import Path
repo, manifest_path = map(Path, sys.argv[1:])
manifest = json.loads(manifest_path.read_text())
assert manifest["source"]["sha256"] == "0c7ce33eac4c6664819a61e48469a9cf43ad403d852b01af5517a13c7ed2a066"
assert len(manifest["stages"]) == 18
for stage in manifest["stages"]:
    path = repo / stage["model"]["path"]
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != stage["model"]["sha256"]:
        raise SystemExit(f"stage model hash mismatch: {stage['name']} {actual}")
print("verified 18 canonical-v2 stage model hashes")
PY

# Default to compiler serialization. An operator may explicitly opt into
# concurrent compilation only after checking WSL headroom and coordinating with
# the owner of the older compiler job.
if [[ ${ALLOW_CONCURRENT_QNN:-no} != yes ]]; then
  for file in /proc/[0-9]*/comm; do
    [[ -r "$file" ]] || continue
    case "$(<"$file")" in
      qnn-session-gate|kokoro-stage-host|kokoro-canonical*|HtpPrepare)
        echo "another QNN compiler/session process is active: $file $(<"$file")" >&2
        exit 3
        ;;
    esac
  done
fi

mem_available=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
(( mem_available >= 8 * 1024 * 1024 )) || {
  echo "less than 8 GiB MemAvailable before launch: $mem_available KiB" >&2
  exit 3
}

mkdir -p "$OUT"
date -u +%FT%TZ >"$OUT/start.txt"
printf '%s\n' "$RUN_ID" >"$OUT/run-id.txt"
printf '%s\n' "$NAME" >"$OUT/container-name.txt"
SWAP_BASE=$(awk '/SwapFree/ {print $2}' /proc/meminfo)
MEM_STOP=$((4 * 1024 * 1024))
SWAP_DROP=$((1024 * 1024))
MEM_RESUME=$((8 * 1024 * 1024))
printf 'swap_base_kib=%s\nmem_pause_below_kib=%s\nswap_pause_drop_kib=%s\nmem_resume_above_kib=%s\n' \
  "$SWAP_BASE" "$MEM_STOP" "$SWAP_DROP" "$MEM_RESUME" >"$OUT/monitor-policy.txt"

monitor() {
  local paused=0
  while docker inspect "$NAME" >/dev/null 2>&1; do
    local now mem swap
    now=$(date -u +%FT%TZ)
    mem=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
    swap=$(awk '/SwapFree/ {print $2}' /proc/meminfo)
    printf '%s mem_available_kib=%s swap_free_kib=%s paused=%s\n' \
      "$now" "$mem" "$swap" "$paused" >>"$OUT/memory-monitor.log"
    if (( paused == 0 )) && { (( mem < MEM_STOP )) || (( swap < SWAP_BASE - SWAP_DROP )); }; then
      printf '%s pause mem_available_kib=%s swap_free_kib=%s\n' "$now" "$mem" "$swap" \
        >>"$OUT/pause-events.log"
      docker pause "$NAME" >>"$OUT/pause-events.log" 2>&1 || true
      paused=1
    elif (( paused == 1 && mem > MEM_RESUME )); then
      printf '%s unpause mem_available_kib=%s swap_free_kib=%s\n' "$now" "$mem" "$swap" \
        >>"$OUT/pause-events.log"
      docker unpause "$NAME" >>"$OUT/pause-events.log" 2>&1 || true
      paused=0
    fi
    sleep 5
  done
}

set +e
/usr/bin/time -v timeout --signal=TERM --kill-after=60 28800 \
  docker run --rm --name "$NAME" --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$REPO:/repo" -v "$BUILD:/build:ro" -v "$QAIRT:/opt/qairt:ro" -w /repo \
  "$IMAGE" env LD_LIBRARY_PATH=/build:/opt/qairt/lib/x86_64-linux-clang \
  python3 /repo/experiments/0017-kokoro-onnx-qnn-htp-android/tools/run_staged_pipeline_qnn.py \
  --manifest /repo/experiments/0017-kokoro-onnx-qnn-htp-android/work/canonical-v2/stages-v1/manifest.json \
  --repo-root /repo \
  --runner /repo/experiments/0017-kokoro-onnx-qnn-htp-android/.local/bin/kokoro-canonical-stage-host-docker \
  --output-dir "/repo/experiments/0017-kokoro-onnx-qnn-htp-android/work/canonical-v2/stages-v1/qnn-host-$RUN_ID" \
  --provider qnn --backend /opt/qairt/lib/x86_64-linux-clang/libQnnHtp.so \
  --optimization disabled --runs 1 \
  --pipeline-input tokens=/repo/experiments/0017-kokoro-onnx-qnn-htp-android/work/canonical-v2/frontend-official-v1/tokens.raw \
  --pipeline-input style=/repo/experiments/0017-kokoro-onnx-qnn-htp-android/work/canonical-v2/frontend-official-v1/style.raw \
  --pipeline-input speed=/repo/experiments/0017-kokoro-onnx-qnn-htp-android/work/canonical-v2/frontend-official-v1/speed.raw \
  >"$OUT/launcher.stdout.log" 2>"$OUT/launcher.stderr.log" &
docker_pid=$!
for _ in $(seq 1 60); do
  docker inspect "$NAME" >/dev/null 2>&1 && break
  sleep 1
done
monitor &
monitor_pid=$!
wait "$docker_pid"
rc=$?
kill "$monitor_pid" 2>/dev/null || true
wait "$monitor_pid" 2>/dev/null || true
set -e

date -u +%FT%TZ >"$OUT/end.txt"
printf '%s\n' "$rc" >"$OUT/exit-code.txt"
printf '%s\n' "$OUT" >"$EXP/.local/latest-canonical-v2-host-qnn-run.txt"
echo "canonical-v2 staged host QNN exit_code=$rc output=$OUT"
exit "$rc"

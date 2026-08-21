#!/usr/bin/env bash
set -uo pipefail
[[ $# == 1 ]] || { echo "usage: $0 MODEL_BASENAME" >&2; exit 2; }
ROOT="$(git rev-parse --show-toplevel)"
EXP="$ROOT/experiments/0019-moss-tts-nano-qnn-htp-android"
BUILD="$ROOT/experiments/0010-supertonic-qnn-htp-feasibility/.local/ort-v1.27.1-qnn-2.49.0-host-patched-a08e17/Release"
QAIRT=/home/moritz/opt/qairt/2.49.0.260730
IMAGE=vibevoice-experiment-0010-qairt:2.49.0.260730-ubuntu22.04
name="$1"; out="$EXP/.local/logs/$name"; rm -rf "$out";mkdir -p "$out"
SOC_MODEL="${SOC_MODEL:-43}"
quiet_arg=""; [[ ${QUIET:-0} == 1 ]] && quiet_arg="--quiet"
set +e
docker run --rm -v "$EXP:/exp" -v "$BUILD:/build:ro" -v "$QAIRT:/opt/qairt:ro" -w /exp \
 -e LD_LIBRARY_PATH=/build:/opt/qairt/lib/x86_64-linux-clang:/usr/lib/llvm-14/lib "$IMAGE" sh -lc \
 "/exp/.local/qnn-session-gate --model /exp/.local/specialized/$name.onnx --backend /opt/qairt/lib/x86_64-linux-clang/libQnnHtp.so --profile /exp/.local/logs/$name/ort --soc-model '$SOC_MODEL' $quiet_arg" >"$out/stdout.log" 2>"$out/stderr.log"
rc=$?;set -e;echo "$rc" >"$out/exit-code.txt"
sha256sum "$out/stdout.log" "$out/stderr.log" >"$out/logs.sha256"
printf '%s rc=%s\n' "$name" "$rc"
exit 0

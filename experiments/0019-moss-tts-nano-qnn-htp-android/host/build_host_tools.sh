#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)";EXP="$ROOT/experiments/0019-moss-tts-nano-qnn-htp-android";BASE="$ROOT/experiments/0010-supertonic-qnn-htp-feasibility"
SRC="${ORT_SOURCE:-$BASE/.local/onnxruntime-v1.27.1-source}";BUILD="${ORT_HOST_BUILD:-$BASE/.local/ort-v1.27.1-qnn-2.49.0-host-patched-a08e17/Release}";QAIRT="${QAIRT_ROOT:-/home/moritz/opt/qairt/2.49.0.260730}";IMAGE="${QAIRT_IMAGE:-vibevoice-experiment-0010-qairt:2.49.0.260730-ubuntu22.04}"
[[ -f "$SRC/include/onnxruntime/core/session/onnxruntime_cxx_api.h" && -f "$BUILD/libonnxruntime.so" && -f "$QAIRT/lib/x86_64-linux-clang/libQnnHtp.so" ]]
mkdir -p "$EXP/.local"
docker run --rm --user "$(id -u):$(id -g)" -v "$EXP:/exp" -v "$BUILD:/build:ro" -v "$SRC:/ortsrc:ro" -v "$QAIRT:/opt/qairt:ro" -w /exp "$IMAGE" sh -lc \
 'g++ -std=c++17 -O2 -I/ortsrc/include/onnxruntime/core/session host/qnn_session_gate.cc -L/build -Wl,-rpath,/build -lonnxruntime -o .local/qnn-session-gate'
g++ -std=c++17 -O1 -pthread -I"$SRC/include/onnxruntime/core/session" -I"$EXP/host" "$EXP/host/moss_fixed_e2e_runner.cc" -L"$BUILD" -Wl,-rpath,"$BUILD" -lonnxruntime -o "$EXP/.local/moss-fixed-e2e-host"
sha256sum "$EXP/.local/qnn-session-gate" "$EXP/.local/moss-fixed-e2e-host" "$BUILD/libonnxruntime.so" "$QAIRT/lib/x86_64-linux-clang/libQnnHtp.so"

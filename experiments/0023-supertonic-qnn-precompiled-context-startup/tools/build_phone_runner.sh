#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0023-supertonic-qnn-precompiled-context-startup"
NDK=${NDK:-/home/moritz/Android/Sdk/ndk/26.3.11579264}
ORT_SOURCE=${ORT_SOURCE:-$ROOT/experiments/0010-supertonic-qnn-htp-feasibility/.local/onnxruntime-v1.27.1-source}
ORT_ANDROID=${ORT_ANDROID:-$ROOT/experiments/0010-supertonic-qnn-htp-feasibility/.local/ort-v1.27.1-qnn-2.49.0-android-arm64/Release}
OUTPUT="$EXP/.local/bin/supertonic-qnn-context-runner"
CXX="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android28-clang++"
mkdir -p "$(dirname "$OUTPUT")"
"$CXX" -std=c++17 -O2 -Wall -Wextra -Werror -fPIE -pie \
  "$EXP/phone/supertonic_qnn_context_runner.cc" \
  -I"$ORT_SOURCE/include/onnxruntime/core/session" \
  -L"$ORT_ANDROID" -lonnxruntime -Wl,-rpath,'$ORIGIN/lib' \
  -o "$OUTPUT"
file "$OUTPUT"
sha256sum "$OUTPUT"
"$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf" -d "$OUTPUT" \
  | grep NEEDED

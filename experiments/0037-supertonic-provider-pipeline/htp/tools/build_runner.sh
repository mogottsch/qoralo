#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
E="$ROOT/experiments/0037-supertonic-provider-pipeline/htp"
NDK=${NDK:-/home/moritz/Android/Sdk/ndk/26.3.11579264}
SOURCE="$ROOT/experiments/0010-supertonic-qnn-htp-feasibility/.local/onnxruntime-v1.27.1-source"
LIB="$ROOT/experiments/0010-supertonic-qnn-htp-feasibility/.local/ort-v1.27.1-qnn-2.49.0-android-arm64/Release"
OUT="$E/.local/bin/runner"
mkdir -p "$(dirname "$OUT")"
"$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android28-clang++" \
 -std=c++17 -O2 -ffp-contract=off -Wall -Wextra -Werror -fPIE -pie "$E/phone/runner.cc" \
 -I"$SOURCE/include/onnxruntime/core/session" -L"$LIB" -lonnxruntime \
 -Wl,-rpath,'$ORIGIN/lib' -o "$OUT"
file "$OUT"
sha256sum "$E/phone/runner.cc" "$OUT" > "$E/.local/bin/build.sha256"

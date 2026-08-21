#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)";EXP="$ROOT/experiments/0019-moss-tts-nano-qnn-htp-android";BASE="$ROOT/experiments/0010-supertonic-qnn-htp-feasibility"
SRC="${ORT_SOURCE:-$BASE/.local/onnxruntime-v1.27.1-source}";ORT="${ORT_ANDROID_BUILD:-$BASE/.local/ort-v1.27.1-qnn-2.49.0-android-arm64}";NDK="${ANDROID_NDK_ROOT:-/home/moritz/opt/android-sdk/ndk/26.2.11394342}";API="${ANDROID_API:-34}";CXX="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android${API}-clang++"
[[ -x "$CXX" && -f "$SRC/include/onnxruntime/core/session/onnxruntime_cxx_api.h" && -f "$ORT/Release/libonnxruntime.so" ]]
mkdir -p "$EXP/.local"
"$CXX" -std=c++17 -O2 -fPIE -pie -pthread -I"$SRC/include/onnxruntime/core/session" -I"$EXP/host" "$EXP/host/moss_fixed_e2e_runner.cc" -L"$ORT/Release" -lonnxruntime -Wl,-rpath,'$ORIGIN' -o "$EXP/.local/moss-fixed-e2e-android"
file "$EXP/.local/moss-fixed-e2e-android"
sha256sum "$EXP/.local/moss-fixed-e2e-android" "$ORT/Release/libonnxruntime.so"

#!/usr/bin/env bash
set -euo pipefail
EXP=$(cd "$(dirname "$0")/.." && pwd)
DEPS=${ANDROID_DEPS:-$EXP/.local/android-deps/extracted}
NDK=${ANDROID_NDK_ROOT:-$HOME/Android/Sdk/ndk/28.1.13356709}
CLANG="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android31-clang++"
OUT="$EXP/.local/android-stage"
mkdir -p "$OUT"
"$CLANG" -std=c++17 -O2 -DNDEBUG -fPIE -pie \
  -I"$DEPS/ort/headers" \
  "$EXP/phone/lfm2_qnn_runner.cpp" \
  -L"$DEPS/ort/jni/arm64-v8a" -lonnxruntime \
  -Wl,-rpath,'$ORIGIN' -Wl,--enable-new-dtags \
  -llog -landroid -ldl -lm \
  -o "$OUT/lfm2_qnn_runner"
"$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip" "$OUT/lfm2_qnn_runner"
file "$OUT/lfm2_qnn_runner"
sha256sum "$OUT/lfm2_qnn_runner"

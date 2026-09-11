#!/usr/bin/env bash
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
# script is at experiments/<experiment>/cpu, so repository is ../../../
EXP="$REPO/experiments/0036-supertonic-whole-chapter-cpu-htp"
NDK="${ANDROID_NDK_HOME:-$HOME/Android/Sdk/ndk/28.1.13356709}"
ORT="$REPO/experiments/0010-supertonic-qnn-htp-feasibility/.local"
STAGE="$EXP/.local/cpu/stage"
mkdir -p "$STAGE/lib" "$STAGE/models"
cp "$REPO/experiments/0023-supertonic-qnn-precompiled-context-startup/.local/phone-stage/lib/libonnxruntime.so" "$STAGE/lib/"
cp "$NDK/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so" "$STAGE/lib/"
"$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android28-clang++" -std=c++17 -O2 -Wall -Wextra \
  -I"$ORT/onnxruntime-v1.27.1-source/include/onnxruntime/core/session" \
  "$EXP/cpu/runner.cc" -L"$STAGE/lib" -lonnxruntime -Wl,-rpath,'$ORIGIN/lib' -o "$STAGE/runner"
sha256sum "$EXP/cpu/runner.cc" "$STAGE/runner" "$STAGE/lib/"* > "$EXP/.local/cpu/build.sha256"

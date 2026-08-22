#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0024-pocket-tts-qnn-precompiled-context-startup"
GRAPHS="$EXP/.local/graphs"
CONTEXTS="$EXP/.local/contexts-host"
ASSETS="$EXP/.local/assets"
ORT="$ROOT/experiments/0010-supertonic-qnn-htp-feasibility/.local/ort-v1.27.1-qnn-2.49.0-android-arm64/Release"
INC="$ROOT/experiments/0010-supertonic-qnn-htp-feasibility/.local/onnxruntime-v1.27.1-source/include/onnxruntime/core/session"
NDK=${ANDROID_NDK_ROOT:-/home/moritz/Android/Sdk/ndk/26.2.11394342}
QAIRT=${QAIRT_SDK_ROOT:-/home/moritz/opt/qairt/2.49.0.260730}
CC="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android27-clang++"
[[ -f $GRAPHS/inventory.json ]] || { echo missing_graph_inventory >&2; exit 2; }
python3 - "$GRAPHS/inventory.json" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); assert len(r['graphs']) == 8
assert r['source_arm_and_context_arm_use_same_files']
PY

for arm in source context; do
  stage="$EXP/.local/android-stage-$arm"
  rm -rf "$stage"
  mkdir -p "$stage/model" "$stage/lib" "$stage/assets"
  "$CC" -std=c++17 -O2 -fPIE -pie -I"$INC" \
    "$EXP/tools/pocket_context_benchmark_runner.cc" -L"$ORT" -lonnxruntime \
    -Wl,-rpath,'$ORIGIN/lib' -o "$stage/pocket_context_benchmark_runner"
  cp "$ASSETS/alba-flow-cache-v1.f32" "$ASSETS/canonical-token-ids-64.i64" \
     "$ASSETS/numpy-randomstate-seed0-temp0p3-292x32.f32" "$stage/assets/"
  if [[ $arm == source ]]; then
    cp "$GRAPHS/"*.onnx "$stage/model/"
  else
    declare -A NAMES=(
      [text]=text_conditioner.onnx [prefill]=flow_prefill_text64.onnx
      [bos]=flow_ar_bos1.onnx [latent]=flow_ar_latent1.onnx [flow]=flow.onnx
      [decoder12]=mimi_decoder12.onnx [decoder6]=mimi_decoder6.onnx
      [decoder1]=mimi_decoder1.onnx
    )
    for component in text prefill bos latent flow decoder12 decoder6 decoder1; do
      context="$CONTEXTS/$component"
      name=${NAMES[$component]}
      cp "$context/$name" "$context/${name%.onnx}_qnn.bin" "$stage/model/"
    done
    count=$(find "$stage/model" -maxdepth 1 -type f -name '*.onnx' | wc -l)
    [[ $count == 8 ]] || { echo context_descriptor_count_failed >&2; exit 3; }
    while IFS= read -r descriptor; do
      [[ $(stat -c %s "$descriptor") -lt 65536 ]] || {
        echo "context stage contains source-sized ONNX: $descriptor" >&2
        exit 4
      }
    done < <(find "$stage/model" -maxdepth 1 -type f -name '*.onnx')
  fi
  cp "$ORT/libonnxruntime.so" "$stage/lib/"
  cp "$QAIRT/lib/aarch64-android/"{libQnnHtp.so,libQnnHtpPrepare.so,libQnnHtpV73Stub.so,libQnnSystem.so} "$stage/lib/"
  cp "$QAIRT/lib/hexagon-v73/unsigned/libQnnHtpV73Skel.so" "$stage/lib/"
  cp "$NDK/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so" "$stage/lib/"
  (cd "$stage" && find . -type f -exec sha256sum {} + | sort) >"$EXP/.local/android-stage-$arm.sha256"
  du -sh "$stage"
done

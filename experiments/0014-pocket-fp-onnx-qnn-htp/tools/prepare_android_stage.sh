#!/usr/bin/env bash
set -euo pipefail
[[ $# == 1 && ( $1 == fp16 || $1 == int16 ) ]]||{ echo "usage: $0 fp16|int16" >&2;exit 2; }
VARIANT=$1;ROOT=$(git rev-parse --show-toplevel);EXP="$ROOT/experiments/0014-pocket-fp-onnx-qnn-htp";STAGE="$EXP/.local/android-stage";MODEL="$STAGE/model";LIB="$STAGE/lib";QAIRT=${QAIRT_SDK_ROOT:-/home/moritz/opt/qairt/2.49.0.260730};NDK=${ANDROID_NDK_ROOT:-/home/moritz/opt/android-sdk/ndk/26.2.11394342};ORT_ROOT="$ROOT/experiments/0010-supertonic-qnn-htp-feasibility/.local/ort-v1.27.1-qnn-2.49.0-android-arm64/Release";ORT_INC="$ROOT/experiments/0010-supertonic-qnn-htp-feasibility/.local/onnxruntime-v1.27.1-source/include/onnxruntime/core/session"
rm -rf "$STAGE";mkdir -p "$MODEL" "$LIB"
cp "$ORT_ROOT/libonnxruntime.so" "$LIB/"
cp "$QAIRT/lib/aarch64-android/"{libQnnHtp.so,libQnnHtpPrepare.so,libQnnHtpV73Stub.so,libQnnSystem.so} "$LIB/"
cp "$QAIRT/lib/hexagon-v73/unsigned/libQnnHtpV73Skel.so" "$LIB/"
cp "$NDK/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so" "$LIB/"
cp "$EXP/.local/static-optimized/text_conditioner-text26.onnx" "$MODEL/text_conditioner.onnx"
cp "$EXP/.local/qnn-v2/mimi_encoder-encoder240000.onnx" "$MODEL/mimi_encoder.onnx"
for n in 12 6 1;do cp "$EXP/.local/qnn-v2/mimi_decoder-decoder$n.onnx" "$MODEL/mimi_decoder$n.onnx";done
if [[ $VARIANT == fp16 ]];then
 cp "$EXP/.local/qnn-flow/flow_lm_prefill_voice126.onnx" "$MODEL/flow_prefill_voice126.onnx";cp "$EXP/.local/qnn-flow/flow_lm_prefill_text26.onnx" "$MODEL/flow_prefill_text26.onnx";cp "$EXP/.local/qnn-flow/flow_lm_ar_bos1.onnx" "$MODEL/flow_ar_bos1.onnx";cp "$EXP/.local/qnn-flow/flow_lm_ar_latent1.onnx" "$MODEL/flow_ar_latent1.onnx";cp "$EXP/.local/static-optimized/flow_lm_flow-flow1.onnx" "$MODEL/flow.onnx"
else
 cp "$EXP/.local/qnn-int16-flow/flow_lm_prefill_voice126-int16.onnx" "$MODEL/flow_prefill_voice126.onnx";cp "$EXP/.local/qnn-int16-flow/flow_lm_prefill_text26-int16.onnx" "$MODEL/flow_prefill_text26.onnx";cp "$EXP/.local/qnn-int16-flow/flow_lm_ar_bos1-int16.onnx" "$MODEL/flow_ar_bos1.onnx";cp "$EXP/.local/qnn-int16-flow/flow_lm_ar_latent1-int16.onnx" "$MODEL/flow_ar_latent1.onnx";cp "$EXP/.local/qnn-int16-flow/flow_lm_flow-flow1-int16.onnx" "$MODEL/flow.onnx"
fi
cp "$EXP/work/bria-10s.wav" "$MODEL/bria.wav";cp "$ROOT/experiments/0012-pocket-onnx-vs-executorch-android/.local/onnx-controlled/bos_before_voice.npy" "$MODEL/"
CC="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android27-clang++";"$CC" -std=c++17 -O2 -fPIE -pie -I"$ORT_INC" "$EXP/tools/pocket_full_qnn_runner.cc" -L"$ORT_ROOT" -lonnxruntime -Wl,-rpath,'$ORIGIN/lib' -o "$STAGE/pocket_full_qnn_runner"
(cd "$STAGE"&&find . -type f -exec sha256sum {} +|sort)>"$EXP/work/full-qnn-$VARIANT-stage-sha256.txt";du -sh "$STAGE";echo "$EXP/work/full-qnn-$VARIANT-stage-sha256.txt"

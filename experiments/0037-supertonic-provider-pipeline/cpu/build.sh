#!/usr/bin/env bash
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
EXP="$REPO/experiments/0037-supertonic-provider-pipeline"
NDK="${ANDROID_NDK_HOME:-$HOME/Android/Sdk/ndk/28.1.13356709}"
ORT="$REPO/experiments/0010-supertonic-qnn-htp-feasibility/.local"
STAGE="$EXP/.local/cpu/stage"
mkdir -p "$STAGE/lib" "$STAGE/models"
cp "$REPO/experiments/0023-supertonic-qnn-precompiled-context-startup/.local/phone-stage/lib/libonnxruntime.so" "$STAGE/lib/"
cp "$NDK/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so" "$STAGE/lib/"
"$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android28-clang++" -std=c++17 -O2 -ffp-contract=off -Wall -Wextra \
 -I"$ORT/onnxruntime-v1.27.1-source/include/onnxruntime/core/session" "$EXP/cpu/runner.cc" \
 -L"$STAGE/lib" -lonnxruntime -Wl,-rpath,'$ORIGIN/lib' -o "$STAGE/runner"
python3 - "$REPO" "$STAGE" <<'PY'
from pathlib import Path
import sys,json,hashlib,shutil
repo,stage=map(Path,sys.argv[1:]);assets=repo/'experiments/0007-mobile-podcast-preview-bakeoff/artifacts/supertonic-3/snapshot/onnx'
inventory=json.loads((repo/'experiments/0011-supertonic-official-fp32-phone-comparison/results/source-inventory.json').read_text())
pins={Path(x['path']).name:x['sha256'] for x in inventory['assets']};records={}
for label,name in [('duration','duration_predictor.onnx'),('text','text_encoder.onnx'),('vector','vector_estimator.onnx'),('vocoder','vocoder.onnx')]:
 data=(assets/name).read_bytes();digest=hashlib.sha256(data).hexdigest()
 if digest!=pins[name]:raise ValueError('official graph changed')
 shutil.copyfile(assets/name,stage/'models'/(label+'.onnx'));records[label]={'source':str(assets/name),'sha256':digest,'bytes':len(data),'graph_modifications':None,'shapes':'original_dynamic','all_learned_weights':'original_bytes'}
(stage.parent/'model-provenance.json').write_text(json.dumps(records,indent=2)+'\n')
PY
sha256sum "$EXP/cpu/runner.cc" "$STAGE/runner" "$STAGE/lib/"* > "$EXP/.local/cpu/build.sha256"

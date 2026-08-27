#!/usr/bin/env bash
set -euo pipefail
EXP=$(cd "$(dirname "$0")/.." && pwd)
QAIRT=${QAIRT_ROOT:-$HOME/opt/qairt/2.49.0.260730}
VENV_SITE=${VENV_SITE:-$EXP/.local/venv/lib/python3.14/site-packages}
OUT=${OUT:-$EXP/.local/direct-qnn-probe}
CONTEXT="$EXP/.local/qnn-aot-pipeline/layer-00-core-norm/context_qnn.bin"
mkdir -p "$OUT/inputs" "$OUT/output" "$EXP/.local/qnn-net-run-libs"
ln -sf "$VENV_SITE/onnxruntime_qnn.libs/libunwind-6b740a46.so.1.0" "$EXP/.local/qnn-net-run-libs/libunwind.so.1"
ln -sf "$VENV_SITE/onnxruntime_qnn.libs/libc++abi-0539aa51.so.1.0" "$EXP/.local/qnn-net-run-libs/libc++abi.so.1"
ln -sf "$VENV_SITE/onnxruntime_qnn.libs/libc++-71bc274c.so.1.0" "$EXP/.local/qnn-net-run-libs/libc++.so.1"
"$EXP/.local/venv/bin/python" - "$EXP/.local/phone-stage" "$OUT/inputs" <<'PY'
import sys,numpy as np
from pathlib import Path
stage,out=Path(sys.argv[1]),Path(sys.argv[2]);token=124894
q=np.memmap(stage/'embedding-quant.u8',np.uint8,'r',shape=(128000,1024))[token]
s=np.memmap(stage/'embedding-scales.f32le',np.float32,'r',shape=(128000,64))[token]
z=np.memmap(stage/'embedding-zp.u8',np.uint8,'r',shape=(128000,32))[token]
u=np.empty(2048,np.float32);u[::2]=q&15;u[1::2]=q>>4
zp=np.empty(64,np.float32);zp[::2]=z&15;zp[1::2]=z>>4
((u-np.repeat(zp,32))*np.repeat(s,32)).tofile(out/'embedding.f32')
np.zeros(2048*3,np.float32).tofile(out/'conv.f32')
PY
cat > "$OUT/input-list.txt" <<EOF
/model/embed_tokens/GatherBlockQuantized/output_0:=$OUT/inputs/embedding.f32 past_conv.0:=$OUT/inputs/conv.f32
EOF
rm -rf "$OUT/output";mkdir "$OUT/output"
export LD_LIBRARY_PATH="$EXP/.local/qnn-net-run-libs:$VENV_SITE/onnxruntime_qnn:$VENV_SITE/onnxruntime_qnn.libs:$QAIRT/lib/x86_64-linux-clang"
"$QAIRT/bin/x86_64-linux-clang/qnn-context-binary-utility" --context_binary="$CONTEXT" --json_file="$OUT/layer00-context.json"
"$QAIRT/bin/x86_64-linux-clang/qnn-net-run" \
  --backend="$VENV_SITE/onnxruntime_qnn/libQnnHtp.so" \
  --retrieve_context="$CONTEXT" --input_list="$OUT/input-list.txt" \
  --output_dir="$OUT/output" --profiling_level=detailed --perf_profile=burst --log_level=info \
  >"$OUT/stdout.log" 2>"$OUT/stderr.log"

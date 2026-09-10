#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0032-qwen-3.5-2b-android-qnn-htp"
D="$EXP/.local/diagnosis/controlled-p1-qnn-call-20260910T122428Z"
export QNN_SDK_ROOT=/home/moritz/opt/qairt/2.49.0.260730
export PYTHONPATH="$QNN_SDK_ROOT/lib/python:$EXP/.local/executorch:$ROOT"
export LD_LIBRARY_PATH="$QNN_SDK_ROOT/lib/x86_64-linux-clang:$ROOT/artifacts/venv-executorch-1.2/lib/python3.11/site-packages/executorch/backends/qualcomm/sdk/libcxx-14.0.0:$ROOT/artifacts/venv-executorch-1.2/lib/python3.11/site-packages/executorch/extension/pybindings"
export PYTHONUNBUFFERED=1
# Exactly one QNN call at position1, explicit QDQ-origin inputs, never resume.
exec "$ROOT/artifacts/venv-executorch-1.2/bin/python" "$EXP/tools/controlled_position1.py" call \
 --backend qnn \
 --pack-header "$EXP/.local/diagnosis/controlled-p1-qdq-pack-20260910T114619Z/pack-header.json" \
 --pack-header-sha256 ec38185783dbd2bc387dbf5387c3f89cd4a4fbb786f2504a82b2b48cd43cd392 \
 --artifact-root "$EXP" --timeout-seconds 300 --output-dir "$D/run" \
 --qdq-control-result "$EXP/.local/diagnosis/controlled-p1-qdq-call-20260910T120717Z/run/control/result.json" \
 --qdq-control-sha256 7137d83a3c89a73121ad5bd2514c865b7cec97fe8b5c2d117be25fe165f43519

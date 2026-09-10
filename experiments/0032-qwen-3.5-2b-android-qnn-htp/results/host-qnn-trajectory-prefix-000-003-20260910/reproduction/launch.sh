#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0032-qwen-3.5-2b-android-qnn-htp"
D="$EXP/.local/diagnosis/qnn-prefix-20260910T104805Z"
export QNN_SDK_ROOT=/home/moritz/opt/qairt/2.49.0.260730
export PYTHONPATH="$QNN_SDK_ROOT/lib/python:$EXP/.local/executorch:$ROOT"
export LD_LIBRARY_PATH="$QNN_SDK_ROOT/lib/x86_64-linux-clang:$ROOT/artifacts/venv-executorch-1.2/lib/python3.11/site-packages/executorch/backends/qualcomm/sdk/libcxx-14.0.0:$ROOT/artifacts/venv-executorch-1.2/lib/python3.11/site-packages/executorch/extension/pybindings"
export PYTHONUNBUFFERED=1
# Only positions0-3 from zero state. No checkpoint/resume arguments or follow-on.
exec "$ROOT/artifacts/venv-executorch-1.2/bin/python" "$EXP/tools/compare_qnn_trajectory.py" \
 --pte "$EXP/.local/diagnosis/restart-20260910T083327Z/01-hidden-compile/diagnostic-w4a16-qnn.pte" \
 --params "$EXP/.local/executorch/examples/models/qwen3_5/config/2b_config.json" \
 --token-ids "$EXP/protocol/token-ids/short.int32le" \
 --artifact-manifest "$EXP/results/host-histogram-precision-20260910/artifact-manifest.json" \
 --reference-directory "$EXP/results/host-histogram-full-short-20260910" \
 --reference-root "$EXP" --context 4096 \
 --max-positions 4 --timeout-seconds 900 --output-dir "$D/run"

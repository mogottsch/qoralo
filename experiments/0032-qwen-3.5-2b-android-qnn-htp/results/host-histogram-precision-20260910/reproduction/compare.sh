#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0032-qwen-3.5-2b-android-qnn-htp"
D="$EXP/.local/diagnosis/restart-20260910T083327Z"
C="$D/01-hidden-compile"
export PATH="$ROOT/artifacts/tools/flatbuffers-25.12.19:$PATH"
export QNN_SDK_ROOT=/home/moritz/opt/qairt/2.49.0.260730
export PYTHONPATH="$QNN_SDK_ROOT/lib/python:$EXP/.local/executorch:$ROOT"
export LD_LIBRARY_PATH="$QNN_SDK_ROOT/lib/x86_64-linux-clang:$ROOT/artifacts/venv-executorch-1.2/lib/python3.11/site-packages/executorch/backends/qualcomm/sdk/libcxx-14.0.0:$ROOT/artifacts/venv-executorch-1.2/lib/python3.11/site-packages/executorch/extension/pybindings"
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 PYTHONUNBUFFERED=1
python - "$C/exit.json" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))['exit_code'] == 0
PY
common=(--diagnostic-hidden-states --params "$EXP/.local/executorch/examples/models/qwen3_5/config/2b_config.json" --token-ids "$EXP/protocol/token-ids/short.int32le" --qdq-file "$C/diagnostic-w4a16-qdq.pt2" --pte "$C/diagnostic-w4a16-qnn.pte" --qdq-outputs "$D/qdq-outputs.pt" --qnn-outputs "$D/qnn-outputs.pt" --result "$D/comparison.json")
for phase in qdq qnn compare; do
  python "$D/guard.py" "$D/02-$phase" nice -n 15 ionice -c 2 -n 7 "$ROOT/artifacts/venv-executorch-1.2/bin/python" "$EXP/tools/localize_qnn_first_token.py" --phase "$phase" "${common[@]}"
done

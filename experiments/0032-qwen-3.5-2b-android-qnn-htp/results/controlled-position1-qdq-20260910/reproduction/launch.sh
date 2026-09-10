#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0032-qwen-3.5-2b-android-qnn-htp"
D="$EXP/.local/diagnosis/controlled-p1-qdq-call-20260910T120717Z"
export PYTHONPATH="$EXP/.local/executorch:$ROOT"
export PYTHONUNBUFFERED=1
# Exactly one QDQ forward at position1. No QNN backend/pair/resume/follow-on args.
exec "$ROOT/artifacts/venv-executorch-1.2/bin/python" "$EXP/tools/controlled_position1.py" call \
 --backend qdq \
 --pack-header "$EXP/.local/diagnosis/controlled-p1-qdq-pack-20260910T114619Z/pack-header.json" \
 --pack-header-sha256 ec38185783dbd2bc387dbf5387c3f89cd4a4fbb786f2504a82b2b48cd43cd392 \
 --artifact-root "$EXP" --timeout-seconds 600 --output-dir "$D/run"

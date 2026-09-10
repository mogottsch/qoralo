#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0032-qwen-3.5-2b-android-qnn-htp"
D="$EXP/.local/diagnosis/full-short-20260910T092627Z"
export TMPDIR="$D/scratch" TMP="$D/scratch" TEMP="$D/scratch"
[[ "$(stat -f -c %T "$TMPDIR")" != tmpfs ]] || { echo 'refusing tmpfs scratch' >&2; exit 2; }
export PYTHONPATH="$EXP/.local/executorch:$ROOT"
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 PYTHONUNBUFFERED=1
python "$D/guard.py" "$D/replay" nice -n 15 ionice -c 2 -n 7 "$ROOT/artifacts/venv-executorch-1.2/bin/python" "$EXP/tools/replay_saved_qdq.py" \
 --params "$EXP/.local/executorch/examples/models/qwen3_5/config/2b_config.json" \
 --token-ids "$EXP/protocol/token-ids/short.int32le" \
 --qdq-file "$EXP/.local/diagnosis/restart-20260910T083327Z/01-hidden-compile/diagnostic-w4a16-qdq.pt2" \
 --artifact-manifest "$EXP/results/host-histogram-precision-20260910/artifact-manifest.json" \
 --output "$D/replay/result.json" --logits "$D/replay/final-logits.pt" \
 --progress "$D/replay/progress.jsonl" --context 4096

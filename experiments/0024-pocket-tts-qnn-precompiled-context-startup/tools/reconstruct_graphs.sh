#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0024-pocket-tts-qnn-precompiled-context-startup"
PY="$EXP/.local/export-venv/bin/python"
EXPORTER="$EXP/.local/onnx-export"
CONFIG="$EXP/.local/onnx-export-local.yaml"
CONTROLLED="$EXP/.local/onnx-controlled"
STATIC="$EXP/.local/static-flow"
GRAPHS="$EXP/.local/graphs"
LOGS="$EXP/.local/logs"
mkdir -p "$ROOT/artifacts/locks" "$CONTROLLED" "$STATIC" "$LOGS"
exec 8>>"$ROOT/artifacts/locks/heavy-ram.lock"
flock -n 8 || { echo heavy_ram_lock_busy >&2; exit 3; }
[[ -x $PY && -d $EXPORTER && -f $CONFIG ]] || { echo missing_reconstruction_inputs >&2; exit 4; }
# Pinned exporter commit b25d4a7 has a CLI bug: --language retains its default
# when --config is supplied, although TTSModel correctly rejects both selectors.
# Apply only that documented local CLI fix; learned code and tensors are unchanged.
for script in "$EXPORTER/scripts/export_mimi_and_conditioner.py" "$EXPORTER/scripts/export_flow_lm.py"; do
  sed -i 's/type=str, default=DEFAULT_LANGUAGE/type=str, default=None/' "$script"
done
# The exporter-pinned Config predates the official runtime-only temperature key.
sed -i '/^default_temperature:/d' "$CONFIG"

if [[ ! -f $CONTROLLED/mimi_decoder.onnx || ! -f $CONTROLLED/text_conditioner.onnx ]]; then
  (cd "$EXPORTER" && PYTHONPATH="$EXPORTER" "$PY" scripts/export_mimi_and_conditioner.py \
    --output_dir "$CONTROLLED" --config "$CONFIG") \
    >"$LOGS/export-mimi-text.stdout.log" 2>"$LOGS/export-mimi-text.stderr.log"
fi
if [[ ! -f $CONTROLLED/flow_lm_flow.onnx ]]; then
  (cd "$EXPORTER" && PYTHONPATH="$EXPORTER" "$PY" scripts/export_flow_lm.py \
    --output_dir "$CONTROLLED" --config "$CONFIG") \
    >"$LOGS/export-flow.stdout.log" 2>"$LOGS/export-flow.stderr.log"
fi
if [[ ! -f $STATIC/flow_lm_prefill_text64.onnx ]]; then
  PYTHONPATH="$EXPORTER" "$PY" "$EXP/tools/export_flow_qnn_static.py" \
    --config "$CONFIG" --exporter-root "$EXPORTER" --output "$STATIC" \
    --capacity 512 --voice-steps 126 --text-steps 64 --skip-voice \
    >"$LOGS/export-static-flow.stdout.json" 2>"$LOGS/export-static-flow.stderr.log"
fi
rm -rf "$GRAPHS"
derivative_arg=()
[[ ${ALLOW_DOCUMENTED_DERIVATIVE:-no} == yes ]] && derivative_arg+=(--allow-documented-derivatives)
"$PY" "$EXP/tools/prepare_qnn_derivatives.py" \
  --controlled "$CONTROLLED" --static-flow "$STATIC" --output "$GRAPHS" \
  "${derivative_arg[@]}"

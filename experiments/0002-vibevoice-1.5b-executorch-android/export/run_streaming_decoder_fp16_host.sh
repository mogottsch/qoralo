#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
ARTIFACTS=${ARTIFACTS:-"$ROOT/artifacts/0002"}
PYTHON=${PYTHON:-"$ROOT/artifacts/venv-executorch-1.2/bin/python"}
SOURCE=${SOURCE:-"$ROOT/artifacts/source/microsoft-vibevoice"}
MODEL=${MODEL:-"$ROOT/artifacts/models/microsoft-VibeVoice-1.5B"}
EXPORT_DIR="$ROOT/experiments/0002-vibevoice-1.5b-executorch-android/export"
FIRST_DIR="$ARTIFACTS/acoustic-decoder-streaming-first-segments-fp16-1.2"
CACHED_DIR="$ARTIFACTS/acoustic-decoder-streaming-cached-segments-fp16-1.2"
RESULT_DIR="$ARTIFACTS/lane-a/fp16"
export PATH="$ROOT/artifacts/tools/flatbuffers-25.12.19:$PATH"

# This lane loads only the acoustic decoder. It never invokes full-model capture.
available_kib=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
if (( available_kib < 4 * 1024 * 1024 )); then
  echo "Refusing decoder export with less than 4 GiB MemAvailable" >&2
  exit 1
fi
mkdir -p "$RESULT_DIR"

measure() {
  local name=$1
  shift
  python3 "$EXPORT_DIR/measure_command.py" \
    --output "$RESULT_DIR/$name-metrics.json" \
    --stdout "$RESULT_DIR/$name.log" \
    --stderr "$RESULT_DIR/$name.stderr" \
    -- "$@"
}

measure export-first \
  "$PYTHON" "$EXPORT_DIR/export_streaming_segments.py" \
  --entry first --precision fp16 --atol 2e-3 --rtol 2e-3 --cache-atol 5e-2 \
  --source "$SOURCE" --model "$MODEL" \
  --fixture "$ARTIFACTS/acoustic-decoder-fixtures/call_000.pt" \
  --output-dir "$FIRST_DIR"

measure export-cached \
  "$PYTHON" "$EXPORT_DIR/export_streaming_segments.py" \
  --entry cached --precision fp16 --atol 2e-3 --rtol 2e-3 --cache-atol 5e-2 \
  --source "$SOURCE" --model "$MODEL" \
  --fixture "$ARTIFACTS/acoustic-decoder-fixtures/call_001.pt" \
  --output-dir "$CACHED_DIR"

measure host-validation \
  "$PYTHON" "$EXPORT_DIR/validate_streaming_sequence.py" \
  "$FIRST_DIR" "$CACHED_DIR" --precision fp16 --repeats 2 \
  --atol 2e-3 --rtol 2e-3 --cache-atol 5e-2 \
  --output "$RESULT_DIR/host-result.json"

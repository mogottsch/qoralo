#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
BASE="$ROOT/experiments/0002-vibevoice-1.5b-executorch-android"
PY=${PYTHON:-$ROOT/artifacts/venv-executorch-1.2/bin/python}
INPUT=${INPUT:-$ROOT/artifacts/0002/lane-d/locked-reference-input}
OUT=${ARTIFACT_DIR:-$ROOT/artifacts/0002/lane-d/locked-reference}
PREFLIGHT="$OUT/preflight.json"
INTERMEDIATE="$OUT/two-speaker-result.json"
RESULT=${RESULT:-$BASE/results/locked-reference-android.json}
mkdir -p "$OUT"

"$PY" "$BASE/export/generation_two_speaker_io.py" prepare "$INPUT" \
  --manifest "$OUT/two-speaker-manifest.json" | tee "$OUT/prepare.log"
DEVICE_MODEL=$(adb shell getprop ro.product.model | tr -d '\r')
"$PY" "$BASE/export/locked_reference_android.py" preflight "$INPUT" "$PREFLIGHT" \
  --device-model "$DEVICE_MODEL" | tee "$OUT/preflight.log"
INPUT="$INPUT" ARTIFACT_DIR="$OUT" RESULT="$INTERMEDIATE" SKIP_HOST=1 \
  "$BASE/android/run-multi-chunk-generation-probe.sh"
"$PY" "$BASE/export/locked_reference_android.py" finalize "$OUT" "$PREFLIGHT" "$RESULT" \
  --commit "$(git rev-parse HEAD)" | tee "$OUT/finalize.log"

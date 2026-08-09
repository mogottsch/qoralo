#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
BASE="$ROOT/experiments/0002-vibevoice-1.5b-executorch-android"
PY=${PYTHON:-$ROOT/artifacts/venv-executorch-1.2/bin/python}
INPUT=${INPUT:-$ROOT/artifacts/0002/generation-two-speaker-input}
OUT=${ARTIFACT_DIR:-$ROOT/artifacts/0002/generation-two-speaker-android}
RUNTIME_RESULT="$OUT/recurrent-runtime-result.json"
RESULT=${RESULT:-$BASE/results/generation-two-speaker-android.json}

"$PY" "$BASE/export/generation_two_speaker_io.py" prepare "$INPUT" \
  --manifest "$BASE/fixtures/two-speaker-manifest.json" | tee "$OUT.prepare.log"
INPUT="$INPUT" ARTIFACT_DIR="$OUT" RESULT="$RUNTIME_RESULT" SKIP_HOST=1 \
  "$BASE/android/run-multi-chunk-generation-probe.sh"
"$PY" "$BASE/export/generation_two_speaker_io.py" finalize "$OUT" "$RUNTIME_RESULT" "$RESULT" \
  --commit "$(git rev-parse HEAD)" | tee "$OUT/two-speaker-comparison.log"

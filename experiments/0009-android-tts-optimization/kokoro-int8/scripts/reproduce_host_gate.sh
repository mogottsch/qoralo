#!/usr/bin/env bash
# Rebuild every canonical host artifact. This never accesses an Android device.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="$(cd "$ROOT/../../.." && pwd)"
SOURCE_ROOT="${SOURCE_ROOT:-$PROJECT/experiments/0008-sherpa-onnx-android-tts-benchmark/artifacts/extracted/kokoro/kokoro-multi-lang-v1_0}"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
ASR_PYTHON="${ASR_PYTHON:-/usr/bin/python3.14}"
mkdir -p "$ROOT/generated/screening" "$ROOT/generated/blind"

run_log() {
  local log="$1"
  shift
  "$@" >"$log" 2>&1
  printf 'passed: %s\n' "$log"
}

# Deterministic selected model and an independent, retained bit-exact rebuild.
run_log "$ROOT/generated/final-quantize.log" \
  "$PYTHON" "$ROOT/scripts/quantize.py" --source-root "$SOURCE_ROOT"
run_log "$ROOT/generated/reproduction-rebuild.log" \
  "$PYTHON" "$ROOT/scripts/quantize.py" --source-root "$SOURCE_ROOT" \
  --output "$ROOT/generated/model.static-qdq-s8s8.onnx" \
  --report "$ROOT/reports/reproduction-rebuild.json"

# Retained failures and alternative static recipes.
run_log "$ROOT/generated/reproduce-dynamic-failure.log" \
  "$PYTHON" "$ROOT/scripts/reproduce_dynamic_failure.py" --source-root "$SOURCE_ROOT"
run_log "$ROOT/generated/screening/full-eligible-quantize.log" \
  "$PYTHON" "$ROOT/scripts/quantize.py" --source-root "$SOURCE_ROOT" \
  --config "$ROOT/screening/full-eligible-s8s8.json" \
  --output "$ROOT/generated/screening/full-eligible-s8s8.onnx" \
  --report "$ROOT/reports/screening-full-eligible-quantization.json"
run_log "$ROOT/generated/screening/linear-only-quantize.log" \
  "$PYTHON" "$ROOT/scripts/quantize.py" --source-root "$SOURCE_ROOT" \
  --config "$ROOT/screening/linear-only-s8s8.json" \
  --output "$ROOT/generated/screening/linear-only-s8s8.onnx" \
  --report "$ROOT/reports/screening-linear-only-quantization.json"

# Final matched evidence. Kokoro has unseeded random operators, so regenerated WAV
# hashes can change; each run is hash-addressed and produces a fresh blind package.
run_log "$ROOT/generated/synthesis-fp32.log" \
  "$PYTHON" "$ROOT/scripts/synthesize.py" --variant fp32 --source-root "$SOURCE_ROOT"
run_log "$ROOT/generated/synthesis-int8.log" \
  "$PYTHON" "$ROOT/scripts/synthesize.py" --variant int8 --source-root "$SOURCE_ROOT"
run_log "$ROOT/generated/audio-analysis.log" \
  "$PYTHON" "$ROOT/scripts/analyze_audio.py"

run_log "$ROOT/generated/screening/full-eligible-synthesis.log" \
  "$PYTHON" "$ROOT/scripts/synthesize.py" --variant int8 --source-root "$SOURCE_ROOT" \
  --quantization-report "$ROOT/reports/screening-full-eligible-quantization.json" \
  --output-dir "$ROOT/generated/screening/full-eligible-audio" \
  --report "$ROOT/reports/screening-full-eligible-synthesis.json"
run_log "$ROOT/generated/screening/full-eligible-analysis.log" \
  "$PYTHON" "$ROOT/scripts/analyze_audio.py" \
  --int8-report "$ROOT/reports/screening-full-eligible-synthesis.json" \
  --output "$ROOT/reports/screening-full-eligible-analysis.json"

run_log "$ROOT/generated/screening/linear-only-synthesis.log" \
  "$PYTHON" "$ROOT/scripts/synthesize.py" --variant int8 --source-root "$SOURCE_ROOT" \
  --quantization-report "$ROOT/reports/screening-linear-only-quantization.json" \
  --output-dir "$ROOT/generated/screening/linear-only-audio" \
  --report "$ROOT/reports/screening-linear-only-synthesis.json"
run_log "$ROOT/generated/screening/linear-only-analysis.log" \
  "$PYTHON" "$ROOT/scripts/analyze_audio.py" \
  --int8-report "$ROOT/reports/screening-linear-only-synthesis.json" \
  --output "$ROOT/reports/screening-linear-only-analysis.json"

run_log "$ROOT/generated/asr-probe.log" \
  "$ASR_PYTHON" "$ROOT/scripts/asr_probe.py"
run_log "$ROOT/generated/blind-package.log" \
  "$PYTHON" "$ROOT/scripts/build_blind.py"
run_log "$ROOT/generated/checker-limitation.log" \
  "$PYTHON" "$ROOT/scripts/reproduce_checker_limitation.py" --source-root "$SOURCE_ROOT"

"$PYTHON" "$ROOT/scripts/make_candidate_selection.py"
"$PYTHON" "$ROOT/scripts/make_failure_report.py"
"$PYTHON" "$ROOT/scripts/make_quality_report.py"
"$PYTHON" "$ROOT/scripts/verify_package.py" --source-root "$SOURCE_ROOT" --runtime-smoke
"$PYTHON" "$ROOT/scripts/make_package_manifest.py"
"$PYTHON" "$ROOT/scripts/verify_package.py" --source-root "$SOURCE_ROOT" --runtime-smoke --require-manifest

printf '\nHost package rebuilt and verified. Quality status remains awaiting_user_listening.\n'

#!/usr/bin/env bash
# Build, measure, and publish the final periodic-GC execution experiment.
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
BASE="$ROOT/experiments/0002-vibevoice-1.5b-executorch-android"
OUT=${ARTIFACT_DIR:-$ROOT/artifacts/0002/lane-d/complete-build-final}
MEASUREMENT=${MEASUREMENT:-$BASE/results/complete-build-final-measurement.json}
RESULT=${RESULT:-$BASE/results/complete-build-final.json}
APK="$BASE/android/app/build/outputs/apk/debug/app-debug.apk"
GRADLE=${GRADLE:-$ROOT/artifacts/tools/gradle-8.10.2/bin/gradle}
export ANDROID_HOME=${ANDROID_HOME:-/home/moritz/Android/Sdk}
export ANDROID_SDK_ROOT=$ANDROID_HOME
mkdir -p "$OUT" "$ROOT/artifacts/locks"

# The measurement harness takes the phone lock. Reinstall preserves the deployed app-private
# accepted package while replacing only controller bytecode.
(cd "$BASE/android" && "$GRADLE" --no-daemon :app:assembleDebug) | tee "$OUT/build.log"
adb install -r "$APK" >"$OUT/adb-install.txt"
ARTIFACT_DIR="$OUT/measurement" RESULT="$MEASUREMENT" "$BASE/android/measure-complete-build.sh"
python3 "$BASE/export/complete_build_final.py" \
  "$BASE/results/complete-build-memory-optimized.json" "$MEASUREMENT" \
  "$BASE/results/locked-reference-comparison.json" "$RESULT" --commit "$(git rev-parse HEAD)"

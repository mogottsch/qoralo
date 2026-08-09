#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)/experiments/0002-vibevoice-1.5b-executorch-android
OUT=$(mktemp -d)
trap 'rm -rf "$OUT"' EXIT
javac -d "$OUT" \
  "$ROOT/android/app/src/main/java/dev/moket/vibevoiceprobe/TokenSelector.java" \
  "$ROOT/android/app/src/main/java/dev/moket/vibevoiceprobe/DpmSolverMultistepScheduler.java" \
  "$ROOT/android/app/src/main/java/dev/moket/vibevoiceprobe/GenerationController.java" \
  "$ROOT/tests/java/dev/moket/vibevoiceprobe/GenerationControllerTest.java"
java -cp "$OUT" dev.moket.vibevoiceprobe.GenerationControllerTest

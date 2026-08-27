#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0032-qwen-3.5-2b-android-qnn-htp"
ET=${ET:-$EXP/.local/executorch}
BUILD=${BUILD:-$ET/build-android}
SOURCE_DIR="$ET/examples/qualcomm/executor_runner"

[[ -f "$BUILD/CMakeCache.txt" ]] || {
  echo "missing configured ExecuTorch Android build: $BUILD" >&2
  exit 2
}
install -m 0644 "$EXP/tools/qwen35_explicit_state_runner.cpp" \
  "$SOURCE_DIR/qwen35_explicit_state_runner.cpp"
install -m 0644 "$EXP/tools/qwen35_explicit_state_runner.cmake" \
  "$SOURCE_DIR/qwen35_explicit_state_runner.cmake"
if ! grep -Fq 'include(qwen35_explicit_state_runner.cmake)' "$SOURCE_DIR/CMakeLists.txt"; then
  printf '\ninclude(qwen35_explicit_state_runner.cmake)\n' >>"$SOURCE_DIR/CMakeLists.txt"
fi

QUALCOMM_BUILD="$BUILD/examples/qualcomm"
cmake -S "$ET/examples/qualcomm" -B "$QUALCOMM_BUILD"
cmake --build "$QUALCOMM_BUILD" --target qwen35_explicit_state_runner -- -j"${JOBS:-4}"
RUNNER="$QUALCOMM_BUILD/executor_runner/qwen35_explicit_state_runner"
[[ -x "$RUNNER" ]] || {
  echo "runner build did not produce $RUNNER" >&2
  exit 3
}
STRIP=$(sed -n 's/^CMAKE_STRIP:FILEPATH=//p' "$QUALCOMM_BUILD/CMakeCache.txt")
[[ -x "$STRIP" ]] || { echo "missing Android strip tool: $STRIP" >&2; exit 4; }
"$STRIP" --strip-unneeded "$RUNNER"
file "$RUNNER"
stat -c 'bytes=%s' "$RUNNER"
sha256sum "$RUNNER"

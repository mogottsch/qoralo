#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^(host|android)$ ]]; then
  echo "usage: $0 host|android" >&2
  exit 2
fi

ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0025-gemma-4-e2b-it-android"
TREE="$EXP/.local/LiteRT-LM"
BAZELISK="$EXP/.local/bin/bazelisk"
LOCK="$ROOT/artifacts/locks/heavy-ram.lock"
NDK="$HOME/Android/Sdk/ndk/28.1.13356709"

python3 "$EXP/tools/prepare_litert_lm_tree.py" --tree "$TREE"

# --batch is mandatory: a persistent Bazel server inherits the flock file
# descriptor and can retain the repository heavy-RAM lock after build exit.
# Batch mode keeps the lock lifetime equal to this build process.
exec 9>"$LOCK"
flock -w 600 9
cd "$TREE"
if [[ "$1" == host ]]; then
  "$BAZELISK" --batch build //runtime/engine:litert_lm_canonical_runner
else
  ANDROID_NDK_HOME="$NDK" "$BAZELISK" --batch build \
    --config=android_arm64 \
    --define=litert_runtime_link_mode=dynamic \
    --define=resolve_symbols_in_exec=false \
    //runtime/engine:litert_lm_canonical_runner
fi

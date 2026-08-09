#!/usr/bin/env bash
# Hash-safe package pruning followed by the same cold/warm protocol as Step 37.
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
BASE="$ROOT/experiments/0002-vibevoice-1.5b-executorch-android"
OUT=${ARTIFACT_DIR:-$ROOT/artifacts/0002/lane-d/complete-build-memory}
FULL="$OUT/optimized-complete-build.json"
RESULT=${RESULT:-$BASE/results/complete-build-memory-optimized.json}
PKG=dev.moket.vibevoiceprobe
mkdir -p "$OUT"

# These are obsolete deployment aliases created by older probes. Refuse deletion unless
# each byte-for-byte matches the accepted first-call artifact that remains deployed.
prune_alias() {
  local alias=$1 accepted=$2
  if ! adb shell "run-as $PKG test -e '$alias'"; then return; fi
  local hashes
  hashes=$(adb shell "run-as $PKG sha256sum '$alias' '$accepted'" | tr -d '\r')
  [[ $(printf '%s\n' "$hashes" | awk '{print $1}' | sort -u | wc -l) -eq 1 ]] || {
    echo "refusing to prune non-identical alias $alias" >&2; exit 4;
  }
  adb shell "run-as $PKG rm '$alias'"
}
for n in $(seq 0 7); do
  prune_alias "files/models/decoder/segment-$n.pte" "files/models/decoder/first/segment-$n.pte"
done
prune_alias files/models/semantic.pte files/models/semantic-first.pte
adb shell "run-as $PKG rmdir files/models/decoder 2>/dev/null || true" >/dev/null

ARTIFACT_DIR="$OUT/measurement" RESULT="$FULL" "$BASE/android/measure-complete-build.sh"
python3 "$BASE/export/complete_build_memory.py" \
  "$BASE/results/complete-build-xnnpack.json" "$FULL" "$RESULT" --commit "$(git rev-parse HEAD)"

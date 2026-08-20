#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel);OUT="$ROOT/experiments/0014-pocket-fp-onnx-qnn-htp/.local/upstream-0008";NAME=sherpa-onnx-pocket-tts-int8-2026-01-26;ARCHIVE="$OUT/$NAME.tar.bz2";URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/$NAME.tar.bz2";mkdir -p "$OUT"
if [[ ! -f $ARCHIVE ]];then curl -fL --retry 3 --output "$ARCHIVE.part" "$URL";mv "$ARCHIVE.part" "$ARCHIVE";fi
echo "2f3b88823cbbb9bf0b2477ec8ae7b3fec417b3a87b6bb5f256dba66f2ad967cb  $ARCHIVE"|sha256sum -c -
[[ -d $OUT/$NAME ]]||tar -xjf "$ARCHIVE" -C "$OUT"
find "$OUT/$NAME" -maxdepth 2 -type f -printf '%s %P\n'|sort -n

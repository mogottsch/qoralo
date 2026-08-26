#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^(host|android)$ ]]; then
  echo "usage: $0 host|android" >&2
  exit 2
fi

ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0029-lfm2.5-2.6b-android"
SRC="$EXP/.local/source/llama.cpp"
BUILD="$EXP/.local/build/$1"
LOCK="$ROOT/artifacts/locks/heavy-ram.lock"
REVISION=5c0d18881e0e9794c96b2602736b758bac9d9388
NDK="$HOME/Android/Sdk/ndk/28.1.13356709"

[[ -d "$SRC/.git" ]] || { echo "missing llama.cpp checkout: $SRC" >&2; exit 3; }
[[ "$(git -C "$SRC" rev-parse HEAD)" == "$REVISION" ]] || {
  echo "llama.cpp HEAD is not $REVISION" >&2; exit 3;
}
[[ -z "$(git -C "$SRC" status --porcelain)" ]] || {
  echo "llama.cpp checkout is dirty" >&2; exit 3;
}
mkdir -p "$BUILD" "$ROOT/artifacts/locks"

prefix_map="-ffile-prefix-map=$SRC=/src/llama.cpp -ffile-prefix-map=$BUILD=/build/llama.cpp"
common_flags=(
  -G Ninja
  -DCMAKE_BUILD_TYPE=Release
  "-DCMAKE_C_FLAGS=$prefix_map"
  "-DCMAKE_CXX_FLAGS=$prefix_map"
  -DBUILD_SHARED_LIBS=OFF
  -DGGML_NATIVE=OFF
  -DGGML_OPENMP=OFF
  -DGGML_CCACHE=OFF
  -DLLAMA_CURL=OFF
  -DLLAMA_BUILD_NUMBER=7446
  -DLLAMA_BUILD_COMMIT=5c0d18881e0e9794c96b2602736b758bac9d9388
  -DLLAMA_BUILD_TESTS=OFF
  -DLLAMA_BUILD_EXAMPLES=OFF
  -DLLAMA_BUILD_SERVER=OFF
)

exec 9>"$LOCK"
flock -w 1800 9 || { echo "timed out waiting for heavy-RAM lock" >&2; exit 4; }

if [[ "$1" == host ]]; then
  cmake -S "$SRC" -B "$BUILD" "${common_flags[@]}"
  cmake --build "$BUILD" --target llama-completion llama-tokenize --parallel 4
  "$BUILD/bin/llama-completion" --version
  "$BUILD/bin/llama-tokenize" --help >/dev/null
else
  [[ -f "$NDK/source.properties" ]] || { echo "missing pinned NDK: $NDK" >&2; exit 5; }
  grep -qx 'Pkg.Revision = 28.1.13356709' "$NDK/source.properties" || {
    echo "wrong NDK revision" >&2; exit 5;
  }
  cmake -S "$SRC" -B "$BUILD" "${common_flags[@]}" \
    -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI=arm64-v8a \
    -DANDROID_PLATFORM=android-31 \
    -DANDROID_STL=c++_static
  cmake --build "$BUILD" --target llama-completion --parallel 4
  "$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip" "$BUILD/bin/llama-completion"
  mkdir -p "$EXP/.local/android-stage"
  install -m 0755 "$BUILD/bin/llama-completion" "$EXP/.local/android-stage/llama-completion"
  "$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf" -h -d \
    "$EXP/.local/android-stage/llama-completion"
  sha256sum "$EXP/.local/android-stage/llama-completion"
fi

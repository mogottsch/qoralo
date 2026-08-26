#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0027-qwen-3.5-2b-android"
LOCAL="$EXP/.local"
SRC="$LOCAL/llama.cpp"
BUILD=${BUILD_DIR:-"$LOCAL/build-android-artifact-v2"}
STAGE="$LOCAL/android-stage"
LOCK="$ROOT/artifacts/locks/heavy-ram.lock"

LLAMA_REVISION=0a5ac49bce4c42893368585edf3ffb41a38f0108
LLAMA_TREE=9355e5ebbca69eb403229473bec6ddfb38f055e0
LLAMA_BUILD_NUMBER=10627
MODEL_URL=https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/f6d5376be1edb4d416d56da11e5397a961aca8ae/Qwen3.5-2B-Q4_K_M.gguf
MODEL_BYTES=1280835840
MODEL_SHA256=aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223
SERVER_BYTES=9844576
SERVER_SHA256=8ce2767eba7480326682d69963eeb483204ee1541c3b5b0c0ef409068ea2b217

find_ndk() {
  local candidate
  for candidate in \
    "${ANDROID_NDK_ROOT:-}" \
    "$HOME/opt/android-sdk/ndk/28.1.13356709" \
    "$HOME/Android/Sdk/ndk/28.1.13356709"; do
    if [[ -n "$candidate" && -f "$candidate/source.properties" ]] &&
       grep -qx 'Pkg.Revision = 28.1.13356709' "$candidate/source.properties"; then
      printf '%s\n' "$candidate"
      return
    fi
  done
  echo "NDK 28.1.13356709 (r28b) not found; set ANDROID_NDK_ROOT" >&2
  exit 2
}

verify_file() {
  local path=$1 bytes=$2 digest=$3
  [[ -f "$path" ]] || { echo "missing file: $path" >&2; return 1; }
  [[ $(stat -Lc %s "$path") == "$bytes" ]] || { echo "wrong byte size: $path" >&2; return 1; }
  [[ $(sha256sum "$path" | awk '{print $1}') == "$digest" ]] || { echo "wrong SHA-256: $path" >&2; return 1; }
}

NDK=$(find_ndk)
mkdir -p "$LOCAL/downloads" "$ROOT/artifacts/locks"
MODEL="$LOCAL/downloads/Qwen3.5-2B-Q4_K_M.gguf"
if ! verify_file "$MODEL" "$MODEL_BYTES" "$MODEL_SHA256" 2>/dev/null; then
  rm -f "$MODEL.part"
  curl -L --fail --retry 5 --retry-delay 3 -o "$MODEL.part" "$MODEL_URL"
  verify_file "$MODEL.part" "$MODEL_BYTES" "$MODEL_SHA256"
  mv "$MODEL.part" "$MODEL"
fi

if [[ ! -d "$SRC/.git" ]]; then
  git init -q "$SRC"
  git -C "$SRC" remote add origin https://github.com/ggml-org/llama.cpp.git
fi
git -C "$SRC" fetch --depth=1 origin "$LLAMA_REVISION"
git -C "$SRC" checkout --detach "$LLAMA_REVISION"
[[ $(git -C "$SRC" rev-parse HEAD) == "$LLAMA_REVISION" ]]
[[ $(git -C "$SRC" rev-parse 'HEAD^{tree}') == "$LLAMA_TREE" ]]
git -C "$SRC" diff --quiet
git -C "$SRC" diff --cached --quiet

# The Android route always passes --no-webui. Disable both local UI building and
# the mutable prebuilt-UI fallback, so unused web assets cannot change the ELF.
# Prefix maps remove checkout/build paths from retained __FILE__ strings.
MAP="-ffile-prefix-map=$SRC=/src/llama.cpp -ffile-prefix-map=$BUILD=/build/llama.cpp"
(
  exec 9>"$LOCK"
  flock -w 600 9
  rm -rf "$BUILD"
  cmake -S "$SRC" -B "$BUILD" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI=arm64-v8a \
    -DANDROID_PLATFORM=android-31 \
    -DANDROID_STL=c++_static \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_FLAGS="$MAP" \
    -DCMAKE_CXX_FLAGS="$MAP" \
    -DBUILD_SHARED_LIBS=OFF \
    -DGGML_NATIVE=OFF \
    -DGGML_OPENMP=OFF \
    -DGGML_CPU_ARM_ARCH=armv8.7-a \
    -DGGML_CCACHE=OFF \
    -DLLAMA_CURL=OFF \
    -DLLAMA_OPENSSL=OFF \
    -DLLAMA_BUILD_UI=OFF \
    -DLLAMA_USE_PREBUILT_UI=OFF \
    -DLLAMA_BUILD_NUMBER="$LLAMA_BUILD_NUMBER" \
    -DLLAMA_BUILD_COMMIT="$LLAMA_REVISION"
  cmake --build "$BUILD" --target llama-server -j "${BUILD_JOBS:-$(nproc)}"
  "$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip" "$BUILD/bin/llama-server"
)

verify_file "$BUILD/bin/llama-server" "$SERVER_BYTES" "$SERVER_SHA256"
NEEDED=$("$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf" -d "$BUILD/bin/llama-server" | sed -n 's/.*Shared library: \[\(.*\)\]/\1/p' | sort | paste -sd, -)
[[ "$NEEDED" == "libc.so,libdl.so,libm.so" ]] || { echo "unexpected dynamic dependencies: $NEEDED" >&2; exit 3; }
if strings "$BUILD/bin/llama-server" | grep -qF "$ROOT"; then
  echo "unmapped checkout path remains in llama-server" >&2
  exit 3
fi

rm -rf "$STAGE"
mkdir -p "$STAGE"
install -m 755 "$BUILD/bin/llama-server" "$STAGE/llama-server"
ln "$MODEL" "$STAGE/model.gguf"
verify_file "$STAGE/llama-server" "$SERVER_BYTES" "$SERVER_SHA256"
verify_file "$STAGE/model.gguf" "$MODEL_BYTES" "$MODEL_SHA256"
(
  cd "$STAGE"
  sha256sum llama-server model.gguf > ../android-stage.sha256
)
printf 'phone-ready stage: %s\n' "$STAGE"
cat "$LOCAL/android-stage.sha256"

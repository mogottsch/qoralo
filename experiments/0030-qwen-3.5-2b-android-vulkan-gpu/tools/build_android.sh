#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0030-qwen-3.5-2b-android-vulkan-gpu"
LOCAL="$EXP/.local"
SRC="$LOCAL/llama.cpp"
BUILD=${BUILD_DIR:-"$LOCAL/build-android-vulkan"}
STAGE="$LOCAL/android-stage"
LOCK="$ROOT/artifacts/locks/heavy-ram.lock"

LLAMA_REVISION=0a5ac49bce4c42893368585edf3ffb41a38f0108
LLAMA_TREE=9355e5ebbca69eb403229473bec6ddfb38f055e0
LLAMA_BUILD_NUMBER=10627
MODEL_URL=https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/f6d5376be1edb4d416d56da11e5397a961aca8ae/Qwen3.5-2B-Q4_K_M.gguf
MODEL_BYTES=1280835840
MODEL_SHA256=aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223
GLSLC_BYTES=6896168
GLSLC_SHA256=452a8331070f15d126df5e263fb9f04e78240dac5f1defe6c434b2c2eef0a53a
SPIRV_HEADER_SHA256=e4e3a2cadd392141ca9f8b5528d450a39d891526b6cab25aa578a6e788f7b58d
VULKAN_HEADERS_REVISION=217e93c664ec6704ec2d8c36fa116c1a4a1e2d40
VULKAN_HEADERS_TREE=3617c6a36daa7c2c60dc4e017be821b3e235341b
VULKAN_HPP_BYTES=877362
VULKAN_HPP_SHA256=2680718d7452870e5b2127b7cbfafcc2f71af7dd74106c44d25927698c8b18ac
SERVER_BYTES=34242152
SERVER_SHA256=b806fc03df6510eb7a141aea093cec7a878a2aa7456ea076a84791fadec68c00

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
GLSLC="$NDK/shader-tools/linux-x86_64/glslc"
SPIRV_INCLUDE="$NDK/sources/third_party/shaderc/third_party/spirv-tools/external/spirv-headers/include"
SPIRV_HEADER="$SPIRV_INCLUDE/spirv/unified1/spirv.hpp"
verify_file "$GLSLC" "$GLSLC_BYTES" "$GLSLC_SHA256"
verify_file "$SPIRV_HEADER" 125518 "$SPIRV_HEADER_SHA256"
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
else
  git -C "$SRC" remote set-url origin https://github.com/ggml-org/llama.cpp.git
fi
git -C "$SRC" fetch --depth=1 origin "$LLAMA_REVISION"
git -C "$SRC" checkout --detach "$LLAMA_REVISION"
[[ $(git -C "$SRC" rev-parse HEAD) == "$LLAMA_REVISION" ]]
[[ $(git -C "$SRC" rev-parse 'HEAD^{tree}') == "$LLAMA_TREE" ]]
git -C "$SRC" diff --quiet
git -C "$SRC" diff --cached --quiet
(
  cd "$SRC/ggml/src/ggml-vulkan"
  sha256sum -c "$EXP/protocol/vulkan-shaders.SHA256SUMS"
)

VULKAN_HEADERS="$LOCAL/Vulkan-Headers"
if [[ ! -d "$VULKAN_HEADERS/.git" ]]; then
  git init -q "$VULKAN_HEADERS"
  git -C "$VULKAN_HEADERS" remote add origin https://github.com/KhronosGroup/Vulkan-Headers.git
else
  git -C "$VULKAN_HEADERS" remote set-url origin https://github.com/KhronosGroup/Vulkan-Headers.git
fi
git -C "$VULKAN_HEADERS" fetch --depth=1 origin "$VULKAN_HEADERS_REVISION"
git -C "$VULKAN_HEADERS" checkout --detach "$VULKAN_HEADERS_REVISION"
[[ $(git -C "$VULKAN_HEADERS" rev-parse HEAD) == "$VULKAN_HEADERS_REVISION" ]]
[[ $(git -C "$VULKAN_HEADERS" rev-parse 'HEAD^{tree}') == "$VULKAN_HEADERS_TREE" ]]
git -C "$VULKAN_HEADERS" diff --quiet
git -C "$VULKAN_HEADERS" diff --cached --quiet
verify_file "$VULKAN_HEADERS/include/vulkan/vulkan.hpp" "$VULKAN_HPP_BYTES" "$VULKAN_HPP_SHA256"

# llama.cpp requires a SPIRV-Headers CMake package only as a presence gate; the
# pinned NDK ships the actual public header but not package metadata. Generate
# the minimal package marker and pass the exact NDK include tree explicitly.
PKG="$LOCAL/cmake-packages/SPIRV-Headers"
mkdir -p "$PKG"
printf 'set(SPIRV-Headers_FOUND TRUE)\n' > "$PKG/SPIRV-HeadersConfig.cmake"

# The route always uses --no-webui. Prefix-map checkout/build paths and compile
# the Vulkan backend plus its embedded SPIR-V using the NDK-pinned glslc.
MAP="-ffile-prefix-map=$SRC=/src/llama.cpp -ffile-prefix-map=$BUILD=/build/llama.cpp"
INCLUDE="-isystem$VULKAN_HEADERS/include -isystem$SPIRV_INCLUDE"
(
  exec 9>"$LOCK"
  flock -w 1800 9
  rm -rf "$BUILD"
  cmake -S "$SRC" -B "$BUILD" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
    -DCMAKE_PREFIX_PATH="$LOCAL/cmake-packages" \
    -DSPIRV-Headers_DIR="$PKG" \
    -DVulkan_GLSLC_EXECUTABLE="$GLSLC" \
    -DANDROID_ABI=arm64-v8a \
    -DANDROID_PLATFORM=android-31 \
    -DANDROID_STL=c++_static \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_FLAGS="$MAP" \
    -DCMAKE_CXX_FLAGS="$MAP $INCLUDE" \
    -DBUILD_SHARED_LIBS=OFF \
    -DGGML_NATIVE=OFF \
    -DGGML_OPENMP=OFF \
    -DGGML_CPU_ARM_ARCH=armv8.7-a \
    -DGGML_CCACHE=OFF \
    -DGGML_VULKAN=ON \
    -DGGML_VULKAN_CHECK_RESULTS=OFF \
    -DGGML_VULKAN_DEBUG=OFF \
    -DGGML_VULKAN_MEMORY_DEBUG=OFF \
    -DGGML_VULKAN_VALIDATE=OFF \
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
[[ "$NEEDED" == "libc.so,libdl.so,libm.so,libvulkan.so" ]] || { echo "unexpected dynamic dependencies: $NEEDED" >&2; exit 3; }
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
printf 'phone-ready candidate stage: %s\n' "$STAGE"
stat -Lc 'server_bytes=%s' "$STAGE/llama-server"
cat "$LOCAL/android-stage.sha256"

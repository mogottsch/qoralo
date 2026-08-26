#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0035-qwen-3.5-2b-android-opencl-gpu"
LOCAL="$EXP/.local"
SRC="$LOCAL/llama.cpp"
HEADERS="$LOCAL/OpenCL-Headers"
LOADER="$LOCAL/OpenCL-ICD-Loader"
LOADER_BUILD=${LOADER_BUILD_DIR:-"$LOCAL/build-opencl-loader"}
BUILD=${BUILD_DIR:-"$LOCAL/build-android-opencl"}
STAGE="$LOCAL/android-stage"
LOCK="$ROOT/artifacts/locks/heavy-ram.lock"

LLAMA_REVISION=0a5ac49bce4c42893368585edf3ffb41a38f0108
LLAMA_TREE=9355e5ebbca69eb403229473bec6ddfb38f055e0
LLAMA_BUILD_NUMBER=10627
OPENCL_HEADERS_REVISION=6fe718c31a45fe25151362a72ef041c3a1047cbd
OPENCL_HEADERS_TREE=185dae17ab1e5bf078e50a42a2f851ae868465d0
OPENCL_LOADER_REVISION=b7bd2803acc779c03d96588e9ca9e9568a18698a
OPENCL_LOADER_TREE=992f5bd721d4460224aa2a3d3885ddc1ac72b3c9
KERNEL_MANIFEST_SHA256=db17a882fcc799e394bc83fedba5f2979e011b132a1441bb6a4e0383e8902b7e
MODEL_URL=https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/f6d5376be1edb4d416d56da11e5397a961aca8ae/Qwen3.5-2B-Q4_K_M.gguf
MODEL_BYTES=1280835840
MODEL_SHA256=aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223
SERVER_BYTES=12313808
SERVER_SHA256=64409e6e96a7d003ed6c68ec12363f3e6d7c34d46af40bc439cb84f060cd4ced

find_ndk() {
  local candidate
  for candidate in "${ANDROID_NDK_ROOT:-}" "$HOME/opt/android-sdk/ndk/28.1.13356709" "$HOME/Android/Sdk/ndk/28.1.13356709"; do
    if [[ -n "$candidate" && -f "$candidate/source.properties" ]] && grep -qx 'Pkg.Revision = 28.1.13356709' "$candidate/source.properties"; then
      printf '%s\n' "$candidate"; return
    fi
  done
  echo "NDK 28.1.13356709 (r28b) not found; set ANDROID_NDK_ROOT" >&2; exit 2
}
verify_file() {
  local path=$1 bytes=$2 digest=$3
  [[ -f "$path" ]] || { echo "missing file: $path" >&2; return 1; }
  [[ $(stat -Lc %s "$path") == "$bytes" ]] || { echo "wrong byte size: $path" >&2; return 1; }
  [[ $(sha256sum "$path" | awk '{print $1}') == "$digest" ]] || { echo "wrong SHA-256: $path" >&2; return 1; }
}
prepare_repo() {
  local dir=$1 url=$2 revision=$3 tree=$4
  if [[ ! -d "$dir/.git" ]]; then git init -q "$dir"; git -C "$dir" remote add origin "$url"; else git -C "$dir" remote set-url origin "$url"; fi
  git -C "$dir" fetch --depth=1 origin "$revision"
  git -C "$dir" checkout --detach "$revision"
  [[ $(git -C "$dir" rev-parse HEAD) == "$revision" ]]
  [[ $(git -C "$dir" rev-parse 'HEAD^{tree}') == "$tree" ]]
  git -C "$dir" diff --quiet
  git -C "$dir" diff --cached --quiet
}

NDK=$(find_ndk)
mkdir -p "$LOCAL/downloads" "$ROOT/artifacts/locks"
MODEL="$LOCAL/downloads/Qwen3.5-2B-Q4_K_M.gguf"
if ! verify_file "$MODEL" "$MODEL_BYTES" "$MODEL_SHA256" 2>/dev/null; then
  rm -f "$MODEL.part"; curl -L --fail --retry 5 --retry-delay 3 -o "$MODEL.part" "$MODEL_URL"
  verify_file "$MODEL.part" "$MODEL_BYTES" "$MODEL_SHA256"; mv "$MODEL.part" "$MODEL"
fi
prepare_repo "$SRC" https://github.com/ggml-org/llama.cpp.git "$LLAMA_REVISION" "$LLAMA_TREE"
prepare_repo "$HEADERS" https://github.com/KhronosGroup/OpenCL-Headers.git "$OPENCL_HEADERS_REVISION" "$OPENCL_HEADERS_TREE"
prepare_repo "$LOADER" https://github.com/KhronosGroup/OpenCL-ICD-Loader.git "$OPENCL_LOADER_REVISION" "$OPENCL_LOADER_TREE"
[[ $(sha256sum "$EXP/protocol/opencl-kernels.SHA256SUMS" | awk '{print $1}') == "$KERNEL_MANIFEST_SHA256" ]]
(cd "$SRC/ggml/src/ggml-opencl" && sha256sum -c "$EXP/protocol/opencl-kernels.SHA256SUMS")

MAP="-ffile-prefix-map=$SRC=/src/llama.cpp -ffile-prefix-map=$BUILD=/build/llama.cpp -ffile-prefix-map=$HEADERS=/src/OpenCL-Headers -ffile-prefix-map=$LOADER=/src/OpenCL-ICD-Loader -ffile-prefix-map=$LOADER_BUILD=/build/OpenCL-ICD-Loader"
(
  exec 9>"$LOCK"; flock -w 1800 9
  rm -rf "$LOADER_BUILD" "$LOCAL/opencl-link" "$BUILD"
  cmake -S "$LOADER" -B "$LOADER_BUILD" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-31 -DANDROID_STL=c++_static \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS="$MAP" \
    -DOPENCL_ICD_LOADER_HEADERS_DIR="$HEADERS" \
    -DOPENCL_ICD_LOADER_BUILD_SHARED_LIBS=ON -DENABLE_OPENCL_LAYERS=OFF \
    -DOPENCL_ICD_LOADER_BUILD_TESTING=OFF -DBUILD_TESTING=OFF
  cmake --build "$LOADER_BUILD" --target OpenCL -j "${BUILD_JOBS:-$(nproc)}"
  mkdir -p "$LOCAL/opencl-link"
  # Android CMake emits an unversioned link-only loader with SONAME
  # libOpenCL.so, matching Qualcomm's vendor implementation on the phone.
  cp "$LOADER_BUILD/libOpenCL.so" "$LOCAL/opencl-link/libOpenCL.so"
  "$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf" -d "$LOCAL/opencl-link/libOpenCL.so" | grep -F 'Library soname: [libOpenCL.so]'
  cmake -S "$SRC" -B "$BUILD" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-31 -DANDROID_STL=c++_static \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS="$MAP" -DCMAKE_CXX_FLAGS="$MAP" \
    -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DGGML_OPENMP=OFF -DGGML_CPU_ARM_ARCH=armv8.7-a -DGGML_CCACHE=OFF \
    -DGGML_OPENCL=ON -DGGML_OPENCL_TARGET_VERSION=300 -DGGML_OPENCL_EMBED_KERNELS=ON \
    -DGGML_OPENCL_USE_ADRENO_KERNELS=ON -DGGML_OPENCL_USE_ADRENO_BIN_KERNELS=OFF -DGGML_OPENCL_PROFILING=OFF \
    -DOpenCL_INCLUDE_DIR="$HEADERS" -DOpenCL_LIBRARY="$LOCAL/opencl-link/libOpenCL.so" \
    -DLLAMA_CURL=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF \
    -DLLAMA_BUILD_NUMBER="$LLAMA_BUILD_NUMBER" -DLLAMA_BUILD_COMMIT="$LLAMA_REVISION"
  cmake --build "$BUILD" --target llama-server -j "${BUILD_JOBS:-$(nproc)}"
  "$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip" "$BUILD/bin/llama-server"
)
if [[ -n "$SERVER_BYTES" || -n "$SERVER_SHA256" ]]; then
  [[ -n "$SERVER_BYTES" && -n "$SERVER_SHA256" ]] || { echo "both expected server fields are required" >&2; exit 3; }
  verify_file "$BUILD/bin/llama-server" "$SERVER_BYTES" "$SERVER_SHA256"
fi
NEEDED=$("$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf" -d "$BUILD/bin/llama-server" | sed -n 's/.*Shared library: \[\(.*\)\]/\1/p' | sort | paste -sd, -)
[[ "$NEEDED" == "libOpenCL.so,libc.so,libdl.so,libm.so" ]] || { echo "unexpected dynamic dependencies: $NEEDED" >&2; exit 3; }
if strings "$BUILD/bin/llama-server" | grep -qF "$ROOT"; then echo "unmapped checkout path remains" >&2; exit 3; fi
rm -rf "$STAGE"; mkdir -p "$STAGE"
install -m 755 "$BUILD/bin/llama-server" "$STAGE/llama-server"
ln "$MODEL" "$STAGE/model.gguf"
verify_file "$STAGE/model.gguf" "$MODEL_BYTES" "$MODEL_SHA256"
(cd "$STAGE" && sha256sum llama-server model.gguf > ../android-stage.sha256)
printf 'phone-ready candidate stage: %s\n' "$STAGE"
stat -Lc 'server_bytes=%s' "$STAGE/llama-server"
cat "$LOCAL/android-stage.sha256"

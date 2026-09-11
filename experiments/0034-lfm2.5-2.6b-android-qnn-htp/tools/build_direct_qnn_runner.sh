#!/usr/bin/env bash
set -euo pipefail
EXP=$(cd "$(dirname "$0")/.." && pwd)
QAIRT=${QAIRT_ROOT:-$HOME/opt/qairt/2.49.0.260730}
NDK=${ANDROID_NDK_ROOT:-$HOME/Android/Sdk/ndk/28.1.13356709}
SRC="$QAIRT/examples/QNN/SampleApp/SampleApp/src"
OUT=${OUT:-$EXP/.local/direct-qnn-android}
GEN="$OUT/include"
mkdir -p "$GEN"
python3 - "$SRC/QnnSampleApp.hpp" "$GEN/QnnSampleApp.hpp" <<'PY'
import sys
from pathlib import Path
source=Path(sys.argv[1]).read_text()
# Access-control-only build adaptation. The generated Qualcomm header remains
# ignored and outside Git; class layout and compiled SDK objects are unchanged.
Path(sys.argv[2]).write_text(source.replace(" private:\n", " public:\n"))
PY
mapfile -t SOURCES < <(find "$SRC/Log" "$SRC/PAL/src/linux" "$SRC/PAL/src/common" "$SRC/Utils" "$SRC/WrapperUtils" -name '*.cpp' -type f | sort)
SOURCES+=("$SRC/QnnSampleApp.cpp")
CXX="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android31-clang++"
"$CXX" -std=c++17 -O2 -DNDEBUG -fPIE -pie \
  -I"$GEN" -I"$SRC" -I"$SRC/Log" -I"$SRC/PAL/include" -I"$SRC/Utils" \
  -I"$SRC/WrapperUtils" -I"$SRC/CachingUtil" -I"$QAIRT/include/QNN" \
  -I"$QAIRT/examples/QNN/SampleApp/SampleApp/include/flatbuffers" \
  "$EXP/phone/direct_lfm2_qnn_runner.cpp" "${SOURCES[@]}" \
  -Wl,--gc-sections -llog -landroid -ldl -lm \
  -o "$OUT/direct_lfm2_qnn_runner"
"$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip" "$OUT/direct_lfm2_qnn_runner"
file "$OUT/direct_lfm2_qnn_runner"
sha256sum "$OUT/direct_lfm2_qnn_runner"

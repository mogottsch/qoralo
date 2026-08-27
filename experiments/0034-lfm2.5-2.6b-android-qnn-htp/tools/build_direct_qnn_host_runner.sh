#!/usr/bin/env bash
set -euo pipefail
EXP=$(cd "$(dirname "$0")/.." && pwd)
QAIRT=${QAIRT_ROOT:-$HOME/opt/qairt/2.49.0.260730}
SRC="$QAIRT/examples/QNN/SampleApp/SampleApp/src"
OUT="$EXP/.local/direct-qnn-host"
GEN="$OUT/include"
mkdir -p "$GEN"
python3 - "$SRC/QnnSampleApp.hpp" "$GEN/QnnSampleApp.hpp" <<'PY'
import sys
from pathlib import Path
s=Path(sys.argv[1]).read_text();Path(sys.argv[2]).write_text(s.replace(' private:\n',' public:\n'))
PY
mapfile -t SOURCES < <(find "$SRC/Log" "$SRC/PAL/src/linux" "$SRC/PAL/src/common" "$SRC/Utils" "$SRC/WrapperUtils" -name '*.cpp' -type f | sort)
SOURCES+=("$SRC/QnnSampleApp.cpp")
g++ -std=c++17 -O2 -DNDEBUG -I"$GEN" -I"$SRC" -I"$SRC/Log" -I"$SRC/PAL/include" -I"$SRC/Utils" -I"$SRC/WrapperUtils" -I"$SRC/CachingUtil" -I"$QAIRT/include/QNN" -I"$QAIRT/examples/QNN/SampleApp/SampleApp/include/flatbuffers" "$EXP/phone/direct_lfm2_qnn_runner.cpp" "${SOURCES[@]}" -Wl,--gc-sections -ldl -lpthread -lm -o "$OUT/direct_lfm2_qnn_runner"
strip "$OUT/direct_lfm2_qnn_runner"
file "$OUT/direct_lfm2_qnn_runner";sha256sum "$OUT/direct_lfm2_qnn_runner"

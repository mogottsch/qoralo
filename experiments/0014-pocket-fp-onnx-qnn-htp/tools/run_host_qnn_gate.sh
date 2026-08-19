#!/usr/bin/env bash
set -euo pipefail
[[ $# == 2 ]]||{ echo "usage: $0 MODEL OUT_DIR" >&2;exit 2; }
MODEL=$(realpath "$1");OUT=$(realpath -m "$2");mkdir -p "$OUT";rm -f "$OUT"/{stdout.log,stderr.log,exit-code.txt,qnn.csv,qnn_qnn.log}
ROOT=$(git rev-parse --show-toplevel);BUILD="$ROOT/experiments/0010-supertonic-qnn-htp-feasibility/.local/ort-v1.27.1-qnn-2.49.0-host-patched-a08e17/Release";SDK=/home/moritz/opt/qairt/2.49.0.260730;IMAGE=vibevoice-experiment-0010-qairt:2.49.0.260730-ubuntu22.04;OPT=${HOST_OPT_LEVEL:-99};FP16=${HOST_FP16:-1}
set +e
docker run --rm -e OPT="$OPT" -e FP16="$FP16" -v "$BUILD:/build:ro" -v "$SDK:/opt/qairt:ro" -v "$MODEL:/model.onnx:ro" -v "$OUT:/out" "$IMAGE" bash -lc 'export LD_LIBRARY_PATH=/build:/opt/qairt/lib/x86_64-linux-clang; cd /out; /build/onnxruntime_perf_test -e qnn -i "backend_path|/opt/qairt/lib/x86_64-linux-clang/libQnnHtp.so enable_htp_fp16_precision|$FP16 profiling_level|detailed profiling_file_path|/out/qnn.csv offload_graph_io_quantization|0 htp_performance_mode|burst soc_model|43" -C "session.disable_cpu_ep_fallback|1" -o "$OPT" -n -x 1 -y 1 -v /model.onnx' >"$OUT/stdout.log" 2>"$OUT/stderr.log"
rc=$?;set -e;printf '%s\n' "$rc">"$OUT/exit-code.txt";grep -E 'Number of partitions supported|All nodes placed|Unsupported nodes|fallback to CPU|Session creation time' "$OUT/stderr.log" "$OUT/stdout.log" >"$OUT/summary.txt"||true;exit "$rc"

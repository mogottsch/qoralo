#!/usr/bin/env bash
set -euo pipefail
# Memory-heavy: coordinate exclusive host compiler use before running.
ROOT="$(git rev-parse --show-toplevel)";EXP="$ROOT/experiments/0019-moss-tts-nano-qnn-htp-android";BUILD="$ROOT/experiments/0010-supertonic-qnn-htp-feasibility/.local/ort-v1.27.1-qnn-2.49.0-host-patched-a08e17/Release";QAIRT=/home/moritz/opt/qairt/2.49.0.260730
IMAGE=vibevoice-experiment-0010-qairt:2.49.0.260730-ubuntu22.04;OUT="$EXP/.local/contexts";LOG="$EXP/.local/context-logs";rm -rf "$OUT" "$LOG";mkdir -p "$OUT" "$LOG"
printf 'utc\tmem_available_kib\tswap_free_kib\n' >"$LOG/resource-samples.tsv"
(while true;do awk -v now="$(date -u +%FT%TZ)" '/MemAvailable:/{m=$2}/SwapFree:/{s=$2}END{print now"\t"m"\t"s}' /proc/meminfo >>"$LOG/resource-samples.tsv";sleep 1;done)& sampler=$!
cleanup_sampler(){ kill "$sampler" 2>/dev/null||true;wait "$sampler" 2>/dev/null||true;};trap cleanup_sampler EXIT
for item in 'prefill:prefill-s226-qnn' 'decode:decode-fixed-cap600-attention-qnn' 'local:local-fixed-b1' 'codec:codec-full-cap375-qnn';do
 name=${item%%:*};model=${item#*:};mkdir -p "$LOG/$name";start=$(date +%s.%N);set +e
 timeout --signal=TERM --kill-after=60 1800 docker run --rm -v "$EXP:/exp" -v "$BUILD:/build:ro" -v "$QAIRT:/opt/qairt:ro" -w /exp -e LD_LIBRARY_PATH=/build:/opt/qairt/lib/x86_64-linux-clang:/usr/lib/llvm-14/lib "$IMAGE" sh -lc "/exp/.local/qnn-session-gate --model /exp/.local/specialized/$model.onnx --backend /opt/qairt/lib/x86_64-linux-clang/libQnnHtp.so --profile /exp/.local/context-logs/$name/ort --context-file /exp/.local/contexts/${name}_ctx.onnx --quiet" >"$LOG/$name/stdout.log" 2>"$LOG/$name/stderr.log";rc=$?;set -e;end=$(date +%s.%N);echo "$rc" >"$LOG/$name/exit-code.txt";python3 -c "print(float('$end')-float('$start'))" >"$LOG/$name/wall-seconds.txt";[[ $rc == 0 ]];[[ -f "$OUT/${name}_ctx.onnx" ]];echo "$name context generated"
done
cleanup_sampler;trap - EXIT
(cd "$OUT";find . -type f -print0|sort -z|xargs -0 sha256sum > context-manifest.sha256)

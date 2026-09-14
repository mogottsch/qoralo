#!/system/bin/sh
set -eu
. /data/local/tmp/vibevoice-0031-htp-power-htp-power-20260914T152014Z-03/control.sh

record_self model
cd "$REMOTE"
export LD_LIBRARY_PATH="$REMOTE/lib" ADSP_LIBRARY_PATH="$REMOTE/lib" QNN_LOG_LEVEL=info
ulimit -v 12582912 || exit 72
# Conservative <=16MiB per file; actual byte limits are read back below.
ulimit -f 16384 || exit 73
cat "/proc/$$/limits" > "$REMOTE/evidence/limits-pre-exec.txt"
set -- $(awk '/^Max address space/ {print $4, $5}' "$REMOTE/evidence/limits-pre-exec.txt")
[ "$1" = 12884901888 ] && [ "$2" = 12884901888 ] || exit 74
set -- $(awk '/^Max file size/ {print $4, $5}' "$REMOTE/evidence/limits-pre-exec.txt")
[ "$1" -ge 393216 ] && [ "$1" -le 16777216 ] && [ "$2" -le 16777216 ] || exit 75
printf '%s\n' base:=/data/local/tmp/vibevoice-0031-htp-power-htp-power-20260914T152014Z-03/inputs/power_edge.uint16le > /data/local/tmp/vibevoice-0031-htp-power-htp-power-20260914T152014Z-03/evidence/power_edge.inputlist
printf '%s\n' x:=/data/local/tmp/vibevoice-0031-htp-power-htp-power-20260914T152014Z-03/inputs/normalization_chain.uint16le > /data/local/tmp/vibevoice-0031-htp-power-htp-power-20260914T152014Z-03/evidence/normalization_chain.inputlist
printf '%s\n' x:=/data/local/tmp/vibevoice-0031-htp-power-htp-power-20260914T152014Z-03/inputs/normalization_exposed.uint16le > /data/local/tmp/vibevoice-0031-htp-power-htp-power-20260914T152014Z-03/evidence/normalization_exposed.inputlist
exec /data/local/tmp/vibevoice-0031-htp-power-htp-power-20260914T152014Z-03/bin/qnn-net-run --backend /data/local/tmp/vibevoice-0031-htp-power-htp-power-20260914T152014Z-03/lib/libQnnHtp.so --retrieve_context /data/local/tmp/vibevoice-0031-htp-power-htp-power-20260914T152014Z-03/power-edge-context.bin --input_list /data/local/tmp/vibevoice-0031-htp-power-htp-power-20260914T152014Z-03/evidence/power_edge.inputlist,/data/local/tmp/vibevoice-0031-htp-power-htp-power-20260914T152014Z-03/evidence/normalization_chain.inputlist,/data/local/tmp/vibevoice-0031-htp-power-htp-power-20260914T152014Z-03/evidence/normalization_exposed.inputlist --output_dir /data/local/tmp/vibevoice-0031-htp-power-htp-power-20260914T152014Z-03/evidence/outputs --num_inferences 1 --use_native_input_files --use_native_output_files --shared_buffer --profiling_level basic --log_level info

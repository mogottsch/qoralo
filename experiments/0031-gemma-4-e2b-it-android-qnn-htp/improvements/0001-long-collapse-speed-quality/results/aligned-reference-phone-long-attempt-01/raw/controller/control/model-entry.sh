#!/system/bin/sh
set -eu
. /data/local/tmp/vibevoice-0031-aligned-aligned-long-20260912T100120Z-01/control.sh

# Both identity records must be written successfully BEFORE exec; same PID/starttime.
record_self model
cd "$REMOTE"
export LD_LIBRARY_PATH="$REMOTE/lib"
exec "$REMOTE/bin/litert_lm_aligned_reference" --backend=gpu --model_path=models/gemma-4-E2B-it.litertlm --workload_dir=workloads --output_dir=evidence --arm_id=0031-single-bos-aligned-gpu --cache_dir=cache --max_num_tokens=8192 --max_output_tokens=2048 --num_cpu_threads=4 --request_timeout_seconds=1800 --reset_mode=fresh_session

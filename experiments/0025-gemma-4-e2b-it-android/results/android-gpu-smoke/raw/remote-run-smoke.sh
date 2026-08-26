#!/system/bin/sh
cd '/data/local/tmp/vibevoice-0025-gemma-4-e2b-it-android'
export LD_LIBRARY_PATH='/data/local/tmp/vibevoice-0025-gemma-4-e2b-it-android/lib'
bin/litert_lm_canonical_runner --backend=gpu --model_path='/data/local/tmp/vibevoice-0025-gemma-4-e2b-it-android/models/gemma-4-E2B-it.litertlm' --workload_dir='/data/local/tmp/vibevoice-0025-gemma-4-e2b-it-android/workloads' --output_dir='/data/local/tmp/vibevoice-0025-gemma-4-e2b-it-android/output' --arm_id=gemma-4-e2b-it-litert-lm-generic-gpu-smoke --cache_dir='/data/local/tmp/vibevoice-0025-gemma-4-e2b-it-android/cache-generic-gpu-smoke' --max_num_tokens=8192 --max_output_tokens=2048 --num_cpu_threads=4 --request_timeout_seconds=1800 --reset_mode=fresh_session --smoke_only --smoke_max_output_tokens=64 > '/data/local/tmp/vibevoice-0025-gemma-4-e2b-it-android/raw/runner-stdout.jsonl' 2> '/data/local/tmp/vibevoice-0025-gemma-4-e2b-it-android/raw/runner-stderr.log'
code=$?
echo $code > '/data/local/tmp/vibevoice-0025-gemma-4-e2b-it-android/raw/runner-exit-code.txt'
exit $code

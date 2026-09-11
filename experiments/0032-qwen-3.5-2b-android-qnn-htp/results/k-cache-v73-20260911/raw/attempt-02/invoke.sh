#!/system/bin/sh
set -eu
cd /data/local/tmp/vibevoice-0032-kcache-20260911-02
export LD_LIBRARY_PATH=/data/local/tmp/vibevoice-0032-kcache-20260911-02
export ADSP_LIBRARY_PATH='/data/local/tmp/vibevoice-0032-kcache-20260911-02;/vendor/lib/rfsa/adsp;/vendor/dsp/cdsp;/system/lib/rfsa/adsp'
sha256sum -c SHA256SUMS >out/pre-run-hashes.txt
test "$(wc -l <input_list.txt)" -eq 1
set +e
timeout -s TERM -k 5 60 sh -c 'echo $$ > runner.pid; exec ./kcache_probe --model_path=model.pte --input_list_path=input_list.txt --output_folder_path=out --warm_up=0 --iteration=1 --shared_buffer=false --log_level=5 --profile_level=0 --etdump_path=out/etdump.etdp --performance_output_path=out/inference_speed.txt' >out/runner.stdout.log 2>out/runner.stderr.log
rc=$?
printf "%s\n" "$rc" >out/exit-code.txt
sha256sum -c SHA256SUMS >out/post-run-hashes.txt
exit "$rc"

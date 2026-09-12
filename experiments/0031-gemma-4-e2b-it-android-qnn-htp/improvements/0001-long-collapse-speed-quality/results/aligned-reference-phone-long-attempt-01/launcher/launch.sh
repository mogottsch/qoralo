#!/bin/sh
set +e
/usr/bin/nice -n 15 /usr/bin/timeout --signal=TERM --kill-after=450 3600 /usr/bin/python3 -B /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/phone-return-launches/aligned-long-20260912T100120Z-01/run.py --execute --reviewed-stage-digest 247493005323235fac12203085f5d07599f179249bbbde908d4c17c288678e92 --pi-slot pi-gemma-aligned-gpu-long-20260912-a --run-id aligned-long-20260912T100120Z-01
rc=$?
printf "%s\n" "$rc" > /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/phone-return-launches/aligned-long-20260912T100120Z-01/controller-exit-code.txt
exit "$rc"

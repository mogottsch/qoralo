#!/system/bin/sh
# Device-side single run. Bounded by timeout; records pid + start identity before exec.
cd "$1" || exit 97
echo "$$ $(cut -d' ' -f22 /proc/$$/stat)" > "$2.pid"
export LD_LIBRARY_PATH="$1/lib"
exec timeout -k 3 "$4" ./bin/"$3" model assets/alba-flow-cache-v1.f32 assets/noise-134x32.f32 "$2.wav" 0.3 134 >"$2.json" 2>"$2.err"

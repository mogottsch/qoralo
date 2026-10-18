#!/system/bin/sh
# Terminates only processes whose cwd is this run's unique stage dir. Prints remaining count; exit 0 iff none.
R="$1"; cd / || exit 97; me=$$
list() { for d in /proc/[0-9]*; do p=${d#/proc/}; [ "$p" = "$me" ] && continue; [ "$(readlink "$d/cwd" 2>/dev/null)" = "$R" ] && echo "$p"; done; }
for p in $(list); do echo "owned pid=$p start=$(cut -d' ' -f22 /proc/$p/stat 2>/dev/null)"; kill -TERM "$p" 2>/dev/null; done
sleep 3
for p in $(list); do echo "kill pid=$p"; kill -KILL "$p" 2>/dev/null; done
sleep 1
n=$(list | wc -l); echo "owned_remaining=$n"; [ "$n" = 0 ]

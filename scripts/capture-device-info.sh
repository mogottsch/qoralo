#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-artifacts/device-info-$(date -u +%Y%m%dT%H%M%SZ).txt}"
mkdir -p "$(dirname "$OUT")"

if ! adb get-state >/dev/null 2>&1; then
  echo "No authorized ADB device. Unlock the phone and approve the USB debugging prompt." >&2
  exit 1
fi

{
  echo "captured_at=$(date -u --iso-8601=seconds)"
  echo
  echo "== device =="
  adb shell 'printf "manufacturer="; getprop ro.product.manufacturer; printf "model="; getprop ro.product.model; printf "device="; getprop ro.product.device; printf "android="; getprop ro.build.version.release; printf "api="; getprop ro.build.version.sdk; printf "soc_manufacturer="; getprop ro.soc.manufacturer; printf "soc_model="; getprop ro.soc.model; printf "abis="; getprop ro.product.cpu.abilist'
  echo
  echo "== memory =="
  adb shell "grep '^MemTotal:' /proc/meminfo"
  echo
  echo "== CPU =="
  adb shell 'printf "cores="; grep -c ^processor /proc/cpuinfo; grep -m1 "^Features" /proc/cpuinfo'
  echo
  echo "== GPU =="
  adb shell "dumpsys SurfaceFlinger 2>/dev/null | grep -m1 'GLES:'"
  adb shell 'printf "vulkan="; getprop ro.hardware.vulkan'
} | tee "$OUT"

echo "Wrote $OUT" >&2

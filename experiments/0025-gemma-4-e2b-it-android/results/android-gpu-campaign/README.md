# Canonical Android GPU campaign

This directory contains the complete protocol-v2 Gemma 4 E2B IT Android GPU campaign using the explicitly approved generic artifact route: one first short request followed by five loaded-Engine requests for each of short, medium, and long. One GPU Engine/model route remained loaded while a fresh Session isolated each later logical request. Session recreation is measured separately and excluded from request timing.

The process requested the GPU-only LiteRT accelerator bit with no CPU fallback bit and retained the fully-delegated single-delegate hint. After compilation it mapped `libLiteRtGpuAccelerator.so`, Qualcomm/Adreno OpenCL and GLES drivers, and held `/dev/kgsl-3d0` open. The runner completed all 16 requests with exit code zero. Raw outputs, logs, provider binding, hashes, conditions, lock lifecycle, and verified scoped cleanup are retained.

The phone ended at Android thermal status 3, so likely sustained thermal throttling is a limitation. Output sanity establishes only sensible-looking natural-language text, not correctness or utility.

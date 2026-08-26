# Android GPU viability smoke

This bounded 64-token short request proves that the approved generic artifact binds the official LiteRT GPU route on the authorized phone. It is a viability milestone only, not experiment completion or a canonical performance distribution.

The benchmark process requested `HwAccelerators::kGpu` without a CPU fallback bit and retained the fully-delegated single-delegate hint. After Engine compilation and Session creation it mapped `libLiteRtGpuAccelerator.so`, Qualcomm/Adreno OpenCL and GLES driver libraries, and held `/dev/kgsl-3d0` open. The request completed with exact raw output. The scoped stage was removed and verified absent.

The older dedicated Artisan artifact blocker remains historical non-metric evidence under `results/android-gpu-blocker/`; this smoke does not overwrite or relabel it.

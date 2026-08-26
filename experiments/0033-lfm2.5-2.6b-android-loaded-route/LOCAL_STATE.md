# Machine-local handover state

Captured after completion of 0035 and both 0033 arms. Everything below is ignored local state; committed results and build recipes remain authoritative.

## Shared machine prerequisites

- NDK: `/home/moritz/opt/android-sdk/ndk/28.1.13356709` (`Pkg.Revision = 28.1.13356709`); `source.properties` SHA-256 `84bef2c605bb263571c299f1eef3307ff58f741710f8cce514cb525b28567f41`.
- Remote Windows ADB daemon: `ADB_SERVER_SOCKET=tcp:172.27.80.1:5037`; authorized serial `R5CW81PR8SY` when connected.
- Phone and heavy-RAM locks: `artifacts/locks/phone.lock` and `artifacts/locks/heavy-ram.lock`.
- Final phone state: both experiment roots verified absent, no experiment process remains, phone lock free.

## 0035 Qwen OpenCL

Ignored root size at handover: approximately 3.3 GiB under `experiments/0035-qwen-3.5-2b-android-opencl-gpu/.local/`.

- `llama.cpp/`: commit `0a5ac49bce4c42893368585edf3ffb41a38f0108`, tree `9355e5ebbca69eb403229473bec6ddfb38f055e0`.
- `OpenCL-Headers/`: commit `6fe718c31a45fe25151362a72ef041c3a1047cbd`, tree `185dae17ab1e5bf078e50a42a2f851ae868465d0`.
- `OpenCL-ICD-Loader/`: commit `b7bd2803acc779c03d96588e9ca9e9568a18698a`, tree `992f5bd721d4460224aa2a3d3885ddc1ac72b3c9`.
- `downloads/Qwen3.5-2B-Q4_K_M.gguf`: 1,280,835,840 bytes, SHA-256 `aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223`; hardlinked locally to other experiments (inode observed `3339820`, link count 6).
- `android-stage/llama-server`: 12,313,808 bytes, SHA-256 `64409e6e96a7d003ed6c68ec12363f3e6d7c34d46af40bc439cb84f060cd4ced`.
- Reproducibility directories: `build-android-opencl/`, `build-android-opencl-b/`, `build-opencl-loader/`, `build-opencl-loader-b/`, plus `llama-server-opencl-a`.
- Successful raw source dirs: `phone-20260826T203418Z-smoke` and `phone-20260826T203631Z-campaign`. Their finalized evidence is committed, so these ignored copies are not required for publication.
- Earlier transport/interruption directories remain locally for diagnosis. The counted transport preflight and provider-smoke/campaign evidence are committed separately; interrupted attempts must never be resumed or counted.

## 0033 LFM loaded routes

Ignored root size at handover: approximately 3.7 GiB under `experiments/0033-lfm2.5-2.6b-android-loaded-route/.local/`.

- Same pinned `llama.cpp`, OpenCL-Headers, and OpenCL-ICD-Loader commits/trees as 0035.
- `models/LFM2.5-2.6B-Q4_K_M.gguf`: 1,674,455,040 bytes, SHA-256 `02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed`; hardlinked locally to the 0029 model (inode observed `1079529`, link count 4).
- `android-stage-cpu/llama-server`: 9,844,576 bytes, SHA-256 `8ce2767eba7480326682d69963eeb483204ee1541c3b5b0c0ef409068ea2b217`.
- `android-stage-opencl/llama-server`: 12,313,808 bytes, SHA-256 `64409e6e96a7d003ed6c68ec12363f3e6d7c34d46af40bc439cb84f060cd4ced`.
- Build directories: `build-android-cpu/`, `build-android-opencl/`, `build-opencl-loader/`, and `opencl-link/`; logs are `build-cpu-a.log` and `build-opencl-a.log`.
- Successful raw source dirs: `phone-20260826T210418Z-campaign` (CPU) and `phone-20260826T221436Z-campaign` (OpenCL). Both are finalized into committed evidence and are not required for publication.

## Reconstruction

The ignored build trees and raw source directories may be deleted after review because committed recipes download/verify the exact model and source dependencies, rebuild hash-bound artifacts under `heavy-ram.lock`, and all finalized raw evidence is committed. Preserve model hardlinks if avoiding another multi-gigabyte download. Never treat ignored raw directories as newer evidence than their committed result/checksum manifests.

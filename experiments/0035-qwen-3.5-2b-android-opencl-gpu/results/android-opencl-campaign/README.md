# Qwen3.5-2B Android OpenCL/Adreno campaign

## Status

Complete canonical protocol-v2 campaign on the authorized Galaxy S23 Ultra. This is bounded mixed OpenCL GPU-offload execution evidence, not GPU-exclusive execution or a quality evaluation.

- Shape: one first short, five warm short, five warm medium, five warm long.
- Provider proof: `Adreno740v2`; QUALCOMM OpenCL 3.0 driver/compiler `E031.41.03.64`; Adreno-optimized source kernels; 25/25 layers; OpenCL model, KV/recurrent-state, and compute buffers.
- CPU boundary: CPU and CPU_REPACK model buffers and CPU compute buffer remain; Flash Attention is disabled because it is not supported on this route; HTTP/tokenizer/sampler/scheduler orchestration remains on CPU.
- Artifact: 12,313,808 bytes, SHA-256 `64409e6e96a7d003ed6c68ec12363f3e6d7c34d46af40bc439cb84f060cd4ced`.
- Model: 1,280,835,840 bytes, SHA-256 `aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223`.
- Setup: 17.112630361 seconds through health and provider proof, including vendor OpenCL kernel compilation and model/context readiness.
- Cleanup: scoped remote root verified absent before lock release.

## Measurements

First short: 477 generated tokens at EOS; TTFT 2.293631 s, reported prefill 78.8468 input tok/s, external decode 10.1332 output tok/s, total 49.268014 s.

Warm medians (five requests per tier):

| Tier | Input | Output | TTFT (s) | Prefill input tok/s | External decode output tok/s | Total (s) | Reset (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| short | 174 | 477 | 2.807856 | 64.6593 | 9.0845 | 55.204791 | 0.013681 |
| medium | 597 | 575 | 9.186424 | 66.7360 | 7.9314 | 81.529789 | 0.017426 |
| long | 1,926 | 645 | 22.969389 | 86.1004 | 8.6138 | 98.646607 | 0.017925 |

Peak sampled process PSS was 1,365,059,584 bytes and VmHWM was 1,377,951,744 bytes. KGSL samples ranged from 220 MHz to 719 MHz and observed up to 99% busy. These are operating observations, not calibrated energy or an isolated GPU-memory measurement. Battery remained at 91%, temperature moved from 32.5 °C to 42.5 °C, and thermal status moved from 0 to 3.

## Validation and limitations

All 16 requests completed at EOS. Every separately timed slot erase succeeded; every request reported `cache_n == 0`, full prompt evaluation, positive prefill time, and no truncation. No model reload, remap, accelerator recompilation, or retained prompt/KV reuse occurred between requests.

Every exact output passed only the narrow sensible-prose corruption check. Greedy outputs happened to be byte-identical within each tier; identity was observed, not required. No correctness, grounding, usefulness, style, or acceptance claim is made.

The post-prefill-to-first-token split remains null because llama.cpp exposes aggregate prompt timing but no alignable server-clock first-token timestamp. External decode excludes the first generated token. WSL-to-Windows ADB forwarding is included in delivery timings. Sampled process memory can miss brief peaks and does not isolate vendor-driver/GPU-private allocation. Calibrated power is unavailable and remains null.

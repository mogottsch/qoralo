# LFM2.5-2.6B Android OpenCL/Adreno campaign

Complete canonical OpenCL GPU-offload campaign on the authorized Galaxy S23 Ultra, separately launched and measured after the completed CPU arm.

- Artifact: 12,313,808-byte server, SHA-256 `64409e6e96a7d003ed6c68ec12363f3e6d7c34d46af40bc439cb84f060cd4ced`.
- Model: official LiquidAI Q4_K_M GGUF, 1,674,455,040 bytes, SHA-256 `02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed`.
- Provider: `Adreno740v2`, QUALCOMM OpenCL 3.0, Adreno-optimized public source kernels, 31/31 offloadable layers, OpenCL model and compute buffers.
- Mixed boundary: CPU orchestration and unsupported operations remain; this is not GPU-exclusive execution.
- Setup: 20.763595189 seconds, including vendor kernel compilation and route readiness.
- Cleanup: scoped OpenCL root verified absent before phone-lock release.

Warm medians:

| Tier | Input | Output | Stop | TTFT (s) | Prefill input tok/s | External decode output tok/s | Total (s) | Reset (s) |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| short | 171 | 1,488 | EOS | 2.888080 | 61.9668 | 7.9796 | 189.261284 | 0.013165 |
| medium | 600 | 2,048 | max tokens | 10.281889 | 60.5300 | 7.1423 | 296.001981 | 0.015220 |
| long | 1,922 | 2,023 | EOS | 31.328286 | 63.6488 | 7.0403 | 317.971720 | 0.015998 |

The first short request had TTFT 1.760388 s, prefill 102.1400 input tok/s, external decode 9.8695 output tok/s, and total 152.427323 s. Backend-dependent floating-point execution produced different deterministic outputs and stop lengths from the CPU arm; this is disclosed rather than treated as matched model-quality evidence.

All 16 logical requests completed. Short and long reached EOS; medium validly reached the 2,048-token ceiling. Every request proved successful separately timed slot erasure, `cache_n == 0`, exact full prompt evaluation, positive prefill time, and no server truncation. Native LFM reasoning continuation and exact prompt/token inventories remained unchanged from the CPU arm.

Peak sampled process PSS was 675,495,936 bytes and VmHWM was 758,554,624 bytes. These values do not include isolated vendor-driver/GPU-private allocation and must not be compared as total memory against CPU PSS. KGSL samples ranged 220–719 MHz and reached 99% busy. Battery remained at 89%, temperature moved 38.4 °C to 43.8 °C, and thermal status moved 1 to 3. No calibrated power was available.

Exact outputs passed only the narrow coherent-text corruption check. Medium outputs end at the ceiling. No correctness, grounding, completeness, usefulness, style, or acceptance claim is made.

# LFM2.5-2.6B Android CPU campaign

Complete canonical CPU-only campaign on the authorized Galaxy S23 Ultra, separately measured from the pending OpenCL arm.

- Shape: one first short plus five warm requests per short/medium/long tier.
- Artifact: UI-disabled llama-server, 9,844,576 bytes, SHA-256 `8ce2767eba7480326682d69963eeb483204ee1541c3b5b0c0ef409068ea2b217`.
- Model: official LiquidAI Q4_K_M GGUF, 1,674,455,040 bytes, SHA-256 `02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed`.
- Backend: `--device none --gpu-layers 0`, four CPU threads.
- Setup: 15.806043938 seconds.
- Cleanup: scoped CPU remote root verified absent before lock release.

Warm medians:

| Tier | Input | Output | Stop | TTFT (s) | Prefill input tok/s | External decode output tok/s | Total (s) | Reset (s) |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| short | 171 | 997 | EOS | 5.820890 | 30.3590 | 8.7516 | 118.925634 | 0.009501 |
| medium | 600 | 1,672 | EOS | 20.378456 | 30.3408 | 7.9389 | 230.932095 | 0.012724 |
| long | 1,922 | 2,048 | max tokens | 68.270532 | 29.0143 | 6.8722 | 366.145184 | 0.014053 |

The first short request had TTFT 3.400408 s, prefill 52.1245 input tok/s, external decode 11.3274 output tok/s, and total 91.328984 s. All short and medium requests reached EOS. All long requests validly reached the canonical 2,048-token ceiling and are recorded as `max_tokens`, not EOS or truncation.

All 16 requests passed separately timed slot erase, `cache_n == 0`, exact full prompt evaluation, positive prefill, and server `truncated == false`. Native LFM reasoning continuation was preserved and exact rendered/token inventories matched the pinned 0029 provenance. Outputs were coherent UTF-8 prose under the narrow corruption check; long outputs end at the ceiling, so no completeness or quality claim is made.

Peak sampled process PSS was 3,559,703,552 bytes and VmHWM was 3,560,947,712 bytes. Battery moved 91% to 90%, temperature 38.3 °C to 44.7 °C, and thermal status 1 to 4. No calibrated power was available. Sampled process memory can miss brief peaks and is not isolated model/KV memory.

# Qwen3.5-2B Android CPU campaign

## Status

Complete canonical artifact-revision-2 campaign on the authorized SM-S918B. This is Android CPU execution/performance evidence, not a podcast-quality evaluation.

- Shape: one first short request, then five loaded-route requests each for short, medium, and long.
- Isolation: one loaded llama-server and reused slot/session; a separately timed full slot erase preceded every request and is excluded from total-request timing.
- Artifact: UI-disabled Android server, 9,844,576 bytes, SHA-256 `8ce2767eba7480326682d69963eeb483204ee1541c3b5b0c0ef409068ea2b217`.
- Model: `Qwen3.5-2B-Q4_K_M.gguf`, 1,280,835,840 bytes, SHA-256 `aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223`.
- Setup: 2.936103108 seconds, from immediately before remote server launch through the first successful health response.
- Cleanup: scoped remote root verified absent before the phone lock was released.

## Measurements

The first short request completed at EOS with 520 generated tokens: TTFT 2.619398079 s, reported prefill 73.2393 input tok/s, externally timed decode 12.9111 output tok/s (first token excluded), and total 42.817386163 s.

Warm-request medians (five requests per tier):

| Tier | Input tokens | Output tokens | TTFT (s) | Prefill (input tok/s) | External decode (output tok/s) | Total (s) | Reset (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| short | 174 | 520 | 3.876351 | 49.0365 | 10.3439 | 53.405646 | 0.012422 |
| medium | 597 | 579 | 16.688611 | 38.7150 | 8.7677 | 81.021826 | 0.019124 |
| long | 1,926 | 1,180 | 61.837022 | 33.8041 | 6.4045 | 243.574563 | 0.021372 |

Peak sampled PSS was 2,833,463,296 bytes; process VmHWM reached 2,835,431,424 bytes. Sampling targeted 100 ms over the server lifecycle. Battery moved from 100% / 37.0 °C / thermal status code 0 to 93% / 44.3 °C / thermal status code 3 while USB-powered. No calibrated watt or OS energy measurement was available.

## Validation and boundaries

All 16 requests completed at EOS. Every slot erase succeeded; every final event reported `cache_n == 0`, the full tier prompt count, positive prompt time, and no truncation. Reset durations are retained separately, and the route records no model remap/reload, accelerator recompilation, or retained prompt/KV reuse.

The exact outputs look like sensible natural-language prose under the narrow corruption/gibberish check, so every output records `looks_sensible: true` and `issue_notes: null`. Greedy outputs were byte-identical within each tier; byte identity was observed, not required. This is not a correctness, grounding, usefulness, style, or acceptance judgment.

ADB ran on the Windows host and was reached from WSL. `raw/client-base.txt` binds the client to `http://172.27.80.1:8027`; request delivery timings therefore include the local WSL-to-Windows forwarding path. The post-prefill-to-first-token split remains null because llama.cpp exposes aggregate prompt timing but no alignable server-clock first-token timestamp. Sampled PSS can miss brief peaks, VmHWM is process-lifetime RSS rather than isolated model/KV memory, and missing power remains null rather than zero.

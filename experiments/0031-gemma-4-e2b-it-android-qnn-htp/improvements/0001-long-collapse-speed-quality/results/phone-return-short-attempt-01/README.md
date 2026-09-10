# Physical Gate A — one first-short/max16 compatibility query

- Run: `fp16-short-20260910T160857Z-01`
- One-use Pi slot: `pi-gemma-fp16-short-20260910-a`
- Controller/stage: unchanged reviewed `62b8a16` / `212f0d4`
- Frozen context SHA-256: `1d80d01637f032ab0c5ec3135e9458c648b4c18e034574a56d42dbfbdbdca9f8`

This is a **16-token engineering/noncanonical diagnostic**, not a replacement campaign or long-output/fidelity/speed acceptance.

The raw log establishes one context deserialization, one dialog/query, SMART_MASK selection, two AR128 and fifteen AR1 QnnDsp executions completed with status0. It has no CPU-backend/runtime-fallback or cache-quantization-error marker. The known `usesCrossAttention` capability message remains retained. These are bounded route observations, not a universal CPU-free or uniform-integer claim.

The runtime profile reports **170 input / 16 generated tokens**. Exact rendered prompt bytes were echoed, and both token logs match all 157 complete logged prefix tokens with one BOS; the fixed-length logger then truncates mid-number. The max16 setting was applied and reached. The independent EOS-versus-limit stop enum is not exposed, so the explicit stop-cause field is null with a reason; no EOS event is invented.

The coherent 89-byte output has SHA-256 `70711436da1fba6f0b7d869c319f8d97c0819d36affbd369e119c1c3f04d6357`, identical to the accepted BOS-corrected short/max16 baseline. Sanity is `true/null`; it does not evaluate long repetition or general quality.

Raw Genie profile observations include creation2,178,751us, query1,478,281us, reported TTFT486,106us and generation17.6189728tok/s. The runtime rate definition does not specify first-token inclusion; normalized decode remains null. No speed comparison is accepted. Process PSS/VmHWM and total HTP-private memory were not measured by this controller.

All query/provider/output/profile/transport/cleanup bytes are retained unchanged. Raw pull preceded optional processing and deletion. All three recorded process roles were absent on both checks, no signal was issued, the owned remote root was removed/verified absent, and the phone lock was released. The process had already finished at the first status poll, so there was no live-native PID sample; execution is established independently by the logs/profile/output, not by exit0.

## Battery privacy boundary

The two complete battery stdout dumps include unrelated learned sleep/charging histories. They remain **private, byte-for-byte**, at the paths and SHA-256 values listed in `result.json` under `privacy_retention`. They are not silently truncated or rewritten.

Public `derived/battery-before.json` and `derived/battery-after.json` contain only explicitly labeled core-field extracts. Battery stayed69%/31.9°C on USB; thermal status0→0, AP40.3→43.9°C, skin33.5→34.0°C. Full thermal snapshots are retained.

`raw/controller-original-SHA256SUMS.txt` is the original private collection's checksum inventory for provenance; it intentionally references the private battery files. Use the **top-level `SHA256SUMS`** to validate the publicly retained artifact set.

No retry, long request, rebuild, controller/stage change or follow-on phone action occurred. A precise long comparison requires new review and a new explicit slot. The completed baseline campaign and registry remain unchanged.

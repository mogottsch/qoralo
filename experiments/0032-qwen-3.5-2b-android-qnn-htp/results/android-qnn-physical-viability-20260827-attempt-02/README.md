# Physical QNN/HTP viability attempt 02

## Outcome

The explicitly authorized one-retry gate succeeded at physical model execution. The exact W4A16 Qwen3.5-2B PTE ran the canonical 174-token short prompt on the Samsung SM-S918B / SM8550 through four QNN HTP-v73 graphs. The provider log contains 696 graph starts and 696 status-`0x0` completions: all four graphs executed once for every input token. Detailed QNN profiling reports four HVX threads per graph execution, 241.087632 aggregate accelerator-execute seconds, 242.457724 aggregate RPC-execute seconds, and 61,322,321,662 aggregate accelerator cycles.

This was deliberately not a benchmark campaign. Setup took 3.661 seconds, the single request took 326.170 seconds, and prefill model execution took 325.745 seconds (0.534 input tokens/s). These are one viability observation, with no loaded-route request reuse or distribution.

## Output caveat

The one-token cap produced token ID 0, which the pinned tokenizer decodes to `!`. The pre-PTQ host calibration over the same canonical short prompt ended at argmax token 21365 (`Given`), so the physical output does not match that reference. The cause could be quantization, explicit-state/input transport, shard-boundary behavior, or output handling; this result does not choose among them.

Because only one punctuation token was authorized, the schema-valid narrow sanity state is `looks_sensible: null, issue_notes: null`. This does not claim sensible output. Campaign readiness remains unproven pending host-only diagnosis.

## Evidence retention

- Exact local and remote artifact hashes matched.
- `raw/generated.int32le` preserves token ID 0; `output.txt` is its exact one-byte UTF-8 decoding.
- `profile-summary.json` summarizes native-unit QNN delegate profile values from ETDump.
- The 104,402,838-byte provider log and 55,018,400-byte ETDump remain exact locally. Git contains lossless zstd copies plus both raw and compressed sizes/hashes in `compression-manifest.json`; decompression was verified to reproduce each raw SHA-256.
- Device, battery, thermal, hash, metric, pull, inventory, and cleanup files are retained under `raw/`.
- The experiment-owned process and remote root were verified absent after capture; Pi independently reverified cleanup and lock release.

## Claim boundary

This proves bounded physical exact-route QNN/HTP model execution. It does not prove useful or sensible generated text, quantized numerical fidelity, loaded-route reuse, campaign performance, model quality, or benchmark-registry eligibility. No further phone run is authorized by this result.

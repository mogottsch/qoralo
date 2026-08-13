# Android benchmark core

Minimal headless arm64 application for the experiment 0008 measurement contract. It accepts an externally staged descriptor, validates the descriptor and every deployed file beneath `getExternalFilesDir(null)`, loads sherpa-onnx from filesystem configuration with `provider=cpu`, and performs one cold plus at least three warm generations.

The synthesis timer uses `System.nanoTime()` and surrounds only `OfflineTts.generate`. Callback samples are observed only to capture the first non-empty callback; there is deliberately no playback path. Audio inspection, unique `CREATE_NEW` PCM WAV writes, and SHA-256 hashing happen after the timer stops. Memory evidence labels `VmHWM` as cumulative process-lifetime and phase peaks as sampled PSS/RSS.

Fetch the exact AAR with `python3 fetch-sherpa-aar.py`. The script checks size `49,095,090` and SHA-256 `6419cd8bc983e0c4fab06067f0fe0313fdc0f7103818ac1e7a08d50787b7a82b`. Generated AAR/APK/output files are not committed.

Run host tests/build from this directory:

```sh
../../../artifacts/gradle-8.10.2/bin/gradle testDebugUnitTest assembleDebug
```

Launch extras are `descriptor`, `descriptor_sha256`, and a unique `campaign_id`. The descriptor itself is JSON with `candidate`, `transcript`, `transcript_sha256`, `sherpa_config_path`, `files` (relative path to SHA-256), `provider`, `num_threads`, `warm_runs`, `speaker_id`, and `language`.

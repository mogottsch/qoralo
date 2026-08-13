# Android benchmark core

Minimal headless arm64 application for the experiment 0008 measurement contract. It accepts an externally staged descriptor, validates the descriptor and every deployed file beneath `getExternalFilesDir(null)`, loads sherpa-onnx from filesystem configuration with `provider=cpu`, and performs one cold plus at least three warm generations.

The synthesis timer uses `System.nanoTime()` and surrounds only `OfflineTts.generate`. Callback samples are observed only to capture the first non-empty callback; there is deliberately no playback path. Audio inspection, unique `CREATE_NEW` PCM WAV writes, and SHA-256 hashing happen after the timer stops. Memory evidence labels `VmHWM` as cumulative process-lifetime and phase peaks as sampled PSS/RSS.

Fetch the exact AAR with `python3 fetch-sherpa-aar.py`. The script checks size `49,095,090` and SHA-256 `6419cd8bc983e0c4fab06067f0fe0313fdc0f7103818ac1e7a08d50787b7a82b`. Generated AAR/APK/output files are not committed.

Run host tests/build from this directory with Gradle 8.10.2 and an Android 35 SDK:

```sh
gradle testDebugUnitTest assembleDebug
```

Launch extras are `descriptor`, `descriptor_sha256`, and a unique `campaign_id`. The descriptor itself is JSON with `candidate`, `transcript`, `transcript_sha256`, `sherpa_config_path`, `files` (relative path to SHA-256), `provider`, `num_threads`, `warm_runs`, `speaker_id`, and `language`.

`sherpa_config_path` names a hash-verified flat JSON file. Its `model_type` is `pocket`, `kokoro`, or `supertonic`; remaining model keys use the sherpa 1.13.5 configuration property names in snake case (for example Kokoro's `model`, `voices`, `tokens`, optional `lexicon`, `data_dir`, and `dict_dir`). Every path must also occur in the descriptor's verified `files` inventory. Optional `rule_fsts`/`rule_fars` are comma-separated inventoried paths. Pocket reference conditioning uses inventoried `reference_audio` (mono PCM16 WAV), optional `reference_text`, and optional `num_steps`. The adapter constructs `OfflineTtsConfig`/`OfflineTtsModelConfig` and calls `generateWithCallback` or `generateWithConfigAndCallback`; it does not depend on a non-existent JSON factory API.

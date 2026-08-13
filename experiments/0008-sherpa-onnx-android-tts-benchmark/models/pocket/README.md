# Pocket TTS deployment track

This track deploys exactly `sherpa-onnx-pocket-tts-int8-2026-01-26` with sherpa-onnx `1.13.5`, the CPU provider, and one inference thread. `model.json` is the Android-facing, filesystem-backed descriptor; `archive-inventory.json` pins every file observed after safe extraction.

## Voice condition

The complete pinned archive was inspected. It contains three packaged references (`bria.wav`, `loona.wav`, and `sample_fr_hibiki_crepes.wav`) and no provenance-verifiable Alba audio. The predeclared fallback is therefore recorded without relabeling:

- requested voice: **Alba**;
- actual reference: **`test_wavs/bria.wav`**;
- voice match: **false**.

The display name and selection reason also identify Bria. This deployment makes no claim that Bria is Alba or approximates Alba.

## Licensing boundary

The archive README says, verbatim, “It is for non-commercial.” Its bundled license is the Creative Commons Attribution 4.0 International Public License. Both original files are retained byte-for-byte under `evidence/` and pinned in `model.json`. The apparent discrepancy is not resolved here; the track is research-only pending legal review.

## Validation

After acquiring and safely extracting the archive through `tools/pinning.py`:

```sh
python models/pocket/pocket.py validate \
  --model-root /absolute/path/to/sherpa-onnx-pocket-tts-int8-2026-01-26
```

Validation fails for archive/date substitutions, changed hashes, non-INT8 component names, unverified references, Alba/Bria mislabeling, missing sample rate, providers other than CPU (including QNN), thread counts other than one, bundled-asset paths, traversal, and escaping links.

## Pinned host smoke

`pocket.py smoke` requires the exact two host wheels in `pins/assets.json`, CPython 3.11.9, Ubuntu 22.04 x86_64, and glibc 2.35. It synthesizes the byte-frozen experiment transcript and independently decodes the complete PCM WAV. The committed report intentionally contains no wall time or RTF:

```sh
python models/pocket/pocket.py smoke \
  --model-root /absolute/path/to/sherpa-onnx-pocket-tts-int8-2026-01-26 \
  --wheel-directory /absolute/path/to/verified-wheels \
  --output /ignored/artifacts/pocket-host-smoke.wav \
  --report models/pocket/host-smoke.json
```

This is configuration/audio validation only. **Host timing is not Android performance evidence.**

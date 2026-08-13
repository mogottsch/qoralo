# Supertonic 3 Android deployment track

This track admits only `sherpa-onnx-supertonic-3-tts-int8-2026-05-11` (archive SHA-256 `82fa96…c427`). `inventory.json` pins every archive member: four `.int8.onnx` components, `tts.json`, `unicode_indexer.bin`, `voice.bin`, and both bundled notices.

## M1 proof

`m1-proof.json` pins all ten upstream style JSONs and sherpa-onnx's `generate_voices_bin.py`. That script uses `sorted(input_dir.glob("*.json"))`; the resulting order is `F1`–`F5`, `M1`–`M5`, so M1 is zero-based SID **5**. Rebuilding from those pinned inputs produced a `voice.bin` byte-identical to the archive. This is a proof, not a guessed style index.

## Deployment and evidence boundary

`android-descriptor.json` selects filesystem-backed external storage, `provider=cpu`, one thread, English (`en`), and SID 5. `sherpa-config.json` contains no QNN or bundled-asset path. `conversion-provenance.json` pins source inference inputs and conversion tooling.

The archive's `LICENSE` is MIT sample-code text while its README says the accompanying model is OpenRAIL-M. `licenses.json` preserves both facts and `licenses/LICENSE.OpenRAIL-M` preserves the pinned model license; no reconciliation is asserted.

`host-smoke.json` records a full-transcript smoke with the pinned sherpa-onnx 1.13.5 CPython 3.11.9 wheel set. The generated WAV was fully decoded, finite, and non-silent. It deliberately contains no timing: this is host configuration validation, **not Android deployment performance evidence**. The WAV remains an ignored artifact.

Validate metadata with:

```sh
python models/supertonic-3/validate.py
python -m unittest models/supertonic-3/test_supertonic.py
```

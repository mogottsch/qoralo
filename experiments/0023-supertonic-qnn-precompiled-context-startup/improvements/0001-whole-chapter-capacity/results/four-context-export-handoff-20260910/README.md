# Eight-context-file reference layout for the new T2048/L2048 parity pack

**Handoff ready; not an app-pack manifest or trust authority.** `context-export.json` binds all eight actual existing files, their exact target `contexts/` paths, I/O and source/compile provenance. Total **298,579,984B**. Every source file was freshly stream-hashed against its accepted constructor receipt. No model/SDK call, copy/re-export, duplicate pack build or original-file mutation occurred.

Manifest SHA256:

```text
1c6d9e3442bc813842b303f9a0dbda2e69eca7f40d43f23768f9e3c94a6acbad
```

## Ownership and layout

- **Ben owns this eight-file source/layout/provenance handoff.** `files[].source_path` gives the protected LOCAL-ONLY bytes; `files[].layout_path` gives Janek's required destination. `CONTEXT_SHA256SUMS` is the checksum list relative to that destination layout.
- **Janek owns the one final schema2 app pack, debug trust and source/build-only long-narration harness.** New ID: `supertonic-3-t2048-l2048-parity`. Copy directly from the eight pinned source paths into that one final pack; no duplicate staging/build is required here.
- Existing descriptor names and embedded companion references already match `contexts/{duration,text,vector,vocoder}-context.onnx` and `contexts/{component}-context_qnn.bin`. **No descriptor rebinding is required. Preserve every descriptor/bin byte.**
- Janek separately copies and pins the five exact accepted companion assets: config, tokenizer, Unicode-indexer, voice data and voice-style data. These are not part of this eight-file export.
- No `.so`, runner, APK, executable or native9 replacement belongs in this data payload. The exported host-runtime pin list is compile provenance, not a request to copy host libraries to Android.

## Required claim boundaries

Four reviewed constructor/export pairs exist; context reload, model execution, Android compatibility, complete long narration and fidelity remain separate gates. The four nonfatal StridedSlice tiler warnings remain in the vocoder evidence and do not authorize a new graph tweak/recompile or block this handoff.

Preserve source provenance: official revision `724fb5ab…2c0b`; vector1000→2048 exact integer position extension with unchanged prefix/theta/learned bytes plus stable Softplus; only two vocoder Conv sites changed to batch1 parity branches after unchanged causal edge Pad, sharing original weights/bias and interleaving exactly. Larger padding and native FP16 behavior are not assumed quality-neutral.

Preserve M1/SID5, five steps, speed1.0, app English/NFKD normalization and chapter StableSeed/xorshift64*/Box–Muller. One logical render remains duration1/text1/vector5/vocoder1→one naturally trimmed complete WAV, not chunks or stitching. Future numerical comparisons require identical prepared arrays/masks/noise. The new ~90s narration probe is noncanonical and its natural duration is unknown until a separately released run.

The accepted production/current T239/L238 pack, all frozen APKs/native9 and original artifacts remain unchanged. No deployment/phone/Run permission is granted by this handoff. Pi controls the new phone slot; Moritz alone accepts an exact WAV. Push hold remains.

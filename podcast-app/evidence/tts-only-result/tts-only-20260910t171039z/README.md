# First canonical TTS request — WAV produced

**FINAL PASS — one profiled engineering request completed and produced a valid WAV.** [Nik's final saved-evidence review](nik-review.md) verifies actual per-component QNN/HTP execution and closes exact input/native/APK/guard/privacy/cleanup checks. This is not a warm benchmark campaign,1–2minute chapter or product-E2E result. **Listening: `not_reviewed`**; only Moritz may judge the exact sample.

[Canonical WAV](device/canonical-short.wav)

## Exact candidate and artifact

- Run: `tts-only-20260910t171039z`.
- Candidate SHA: `3cf46e271a515ed30125c09ac6f9891c808218e6871ef39adee7767b0e4c6fed`.
- App SHA: `024f5cd58761f5816163b907293e51867a5c0f3962b37c7aa6416c18ad47228d`.
- Test SHA: `7066cbee3abdeff69dbaa5bd0f1ff6031614061f444237488b407aa44bc3263d`.
- Guard closure: `3ad4c644a7733d1f1feeb7bbbe83532cc0be0f727f32f59dda00c951dd6e202d`; TTS controller: `a62d204c380a5b2d0c8f7c5bd94729b6f823e18200feed2ebe24fa73962bec3c`.
- Original app-owned archive SHA: `aac3e3ae19cd7e3121381ffe53e5ad40c27620da744b24d0c9a615042b110a6a`.
- WAV SHA: **`bcc277bce02cdb3042a853c91172abc6c99c325657cdce4829b2eabfc79c163a`**;1,379,546 bytes.

## Measured first request

| Item | Result |
|---|---:|
| Four-context adapter load |669.641354ms |
| Profiled render |6441.159529ms |
| Audio |689,751 frames /15.6406122449s |
| Format |44,100Hz /mono /PCM16 |
| First-request RTF |0.4118227233 |
| Generation-process VmHWM |345,848KiB |
| Driver collection |12,277ms |

Load and render are separate. Render includes normalization, native duration/text/five-vector/vocoder calls, WAV validation/publication and probe logging; it excludes pack verification/load/close. VmHWM is the process-lifetime high-water mark in retained `/proc/self/status` snapshots—not total DSP/system memory or a pure model-buffer allocation. Phase begin/complete records are retained in `device/events.jsonl`.

The exact submitted and normalized text are both226 bytes, SHA `424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67`. VoiceM1/SID5,5steps, speed1.0 and the existing chapter-seeded xorshift/Box–Muller settings are preserved. `tokenization-reconstruction.json` explicitly records a deterministic pinned-source/indexer reconstruction (235 active positions +4 padding), **not observed native tensor memory**. No waveform equality with differently seeded/speed-scaled upstream fixtures is claimed.

## Execution evidence, not configuration alone

One logical request used four newly loaded contexts. Saved ORT profiles contain actual Node `*_kernel_time` events: duration1, text1, vector5 and vocoder1. Nik's saved-only review found all attributed to QNNExecutionProvider with matching finite positive per-component ROOT RPC-execute microseconds and accelerator-execute cycles; vector has five matching execution records. These are not the earlier load-only Session events.

Raw ORT JSON, QNN CSV and binary profiler files are retained in `device/qnn-profiles/`. Native stdout/stderr are empty for this successful warning-level engine path; they are preserved as empty files, not fabricated verbose logs. No Gemma, splitting/stitching, deliberate capacity probe or retry occurred. Optional evidence warnings are empty. A valid PCM file and execution attribution do not decide speech quality.

## Cleanup and safe retention

All three guarded checkpoints passed. Cleanup records no errors/settings errors; actual internal app/generation/test names are absent and settings readbacks match. The controller released its canonical lock after cleanup. Separate authorized pre-run checks at `../pre-run-20260910t171037z/` found no process, so **no maintenance force-stop was needed** before the attempt.

`retained-manifest.json` binds306 safe public originals/extracted members (7,763,052 bytes). The archive contains only app-owned TTS records. Ten full DB/condition/logcat files remain **local-only**, hash-bound but not copied into Git. Public `conditions-core-*.json` are explicitly labelled derived numeric/bool core battery and numeric thermal extracts, never normalized data presented as raw. Full Samsung learned histories, sensor names and global logs are excluded. The duplicate convenience WAV at the original run root is omitted; its identical archive member is retained here.

Source/raw/WAV bytes are immutable. `summary.json` retains its initial review-pending state; `nik-review.md` and its hash-bound retention record supersede that status, not the original observations. Nik reviewed the original saved result; Janek/Pi's committed-blob packaging checks are separate provenance, not a duplicate Nik packaging audit. No follow-on phone call, automatic replay, listening verdict or push occurred during retention. Git push/external publication remains held for the separately coordinated historical privacy cleanup.

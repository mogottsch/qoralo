# One canonical TTS engineering request

**Source/build preparation authorized; physical execution requires the reviewed exact candidate and Pi's fresh slot.** No intermediate four-load-only phone gate is planned.

## Minimal delta

The candidate uses frozen diagnostic source3fd75c0, the proven optional public `libcdsprpc.so` declaration, one private debug `TtsOnlyService`, one opt-in `TtsOnlyTest`, pinned contract/text assets and a small debug-only QNN profile-directory hook. The existing `SupertonicQnnHtpEngine.load` / `renderChapter` / `close` path is unchanged. No Gemma instance/request, product generation job, splitting/stitching, deliberate capacity probe or retry is added.

The isolated build reuses exact native APK bytes, including the bridge; it disables only host CMake wiring in its private local.properties rather than recompiling C++. Main render code, ORT/QNN options, contexts and all nine packaged native libraries must match the proven manifest-only APK. The source proof enumerates the exact overlay and complete effective source tree. This is not a rebuild/approval of the polished UI candidate.

## Request and settings

- Exact226-byte/no-newline canonical asset, SHA `424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67`.
- Voice M1/SID5, T239/L238/144channels,5steps, speed1.0.
- Chapter ID `canonical-short`; unchanged native FNV-style chapter hash xor20260813, xorshift64star/Box–Muller, fresh per-request buffers and fresh engine sessions.
- Four session constructors, then **one logical render**. Expected internal Run calls are duration1/text1/vector5/vocoder1; profile callback counts are not a new fatal acceptance gate.
- Exact raw and normalized strings are retained. IDs/mask and seed are explicitly **deterministic reconstruction from the actual request, pinned indexer and unchanged native source**, not observed native tensor memory. No extra native capture is introduced.

This does not use upstream8steps/speed1.05/NumPyPCG64 and makes no waveform-equality claim against differently prepared0023 fixtures. Future fidelity comparison requires identical prepared arrays, not merely equal textual seeds.

## Bounds and evidence

| Stage | Hard bound |
|---|---:|
| Supertonic verification |60s |
| Four-context load |120s |
| One complete canonical render |90s |
| Close/profile finalization |30s |
| Service / instrumentation driver / host call |330s /345s /360s |

Existing install180s/pull120s/ordinary30s bounds remain. Same-process debug native work has an independent deadline that kills only the verified generation process on a hang. One first request is authorized, not a warm-up plus timed repeat.

The complete WAV is atomically retained before optional metrics/profile finalization. Keep setup-load vs render timing separate; render includes frontend/native stages/WAV validation and publication, not verification/load/close. Record actual WAV duration/format/hash and first-request RTF if available, process VmHWM snapshots with that measurement boundary, and labelled thermal/core-battery context. Missing optional evidence remains an explicit limitation and must not delete a valid WAV. Listening remains `not_reviewed` until Moritz judges that exact file.

Raw ORT/QNN/RPC/profile files are retained for independent execution attribution. Session/load events are not neural-execution proof; runtime-reported readiness is declarative until corroborated. This is one profiled engineering sample, not a warm median, canonical multi-run campaign, complete1–2minute chapter or product E2E.

## Controller, privacy and ownership

`run_tts_only_gate.py` reuses the reviewed PhoneGuard unchanged (closure3ad4c644…6e202d), with a separately approved TTS-controller hash and candidate hash. Its checks precede both installs and instrumentation under the same uninterrupted canonical lock, with descriptor closure and raw-first cleanup. Existing restricted eligibility and residual external-launch race remain explicitly applicable.

Full Samsung battery/thermal stdout goes directly into local-only `.private-conditions`; DB snapshots stay in `.private-db`, and unfiltered logcat stays private. Public conditions are explicitly labelled derived numeric/bool core-battery and numeric thermal extracts with source hashes—not normalized output mislabeled as raw. No histories/timestamps/sensor names are published. Current repository push restrictions remain independent of source/build work.

No physical call is authorized by this document. Any first failure stops and is retained without shortening text, changing voice/RNG/contexts/options, or retrying.

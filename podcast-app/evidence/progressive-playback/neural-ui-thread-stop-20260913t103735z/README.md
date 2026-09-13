# Genuine generation succeeded; concurrent Player E2E failed

**Not a complete E2E/deployment pass.** One normal owned AUDIO job completed, but the Player failed before explicit Play. No pre-Ready playback advancement was observed.

Run `provider-app-phase-live-20260913t103735z`, candidate `c6917458004aeffd3fa53f9f7221196983670306c4ec275debf34196c5465be0`, source `7b06a3fe`:
- App `939c731e75a47c535cce130474b5d734d05a6765879f036085396cb97ed1023c`.
- Test `1b2ef1c156233b1542f0b891eeacf1011a7d80b10bfd87ed814c21188ef1612f`.
- Owned episode `f029ddbe-5346-454b-9572-77662eb92826`, AUDIO attempt `75b87fb718c53af43ab177bb086fad85b56cead166c96c949de7bb5b8528cd97`.

## Actual neural result retained

15 provider segments/165 QNN/HTP calls completed and the episode reached FROZEN_READY without a recovery attempt. Master **`2194bce66f8abd05bdf10fefc5cf4aaef49cac647992f637db319b7d14be532a`**,18,538,292B,9,269,124 mono PCM16 frames at44.1kHz: **210.184217687s**. The waveform equals the prior2194app sample byte-for-byte; no new listening verdict is inferred.

The15 immutable stream chunks concatenate to the canonical master's exact PCM payload. Encoded silence is exactly14×13,230 frames; no truncation/stretch/repair/fallback. Chapter-render elapsed89,439.395ms (single functional-run render RTF0.42553, not a canonical warm benchmark). First closed/verified stream chunk appeared6017.814ms after chapter-render start; that is not first audible playback or TTFA.

The owned monitor recorded179 samples, minimum available memory2,906,812KiB, maximum temperature31.3°C, maximum sample interval517.751ms and a guarded close; no stop was requested. Own-process lifetime peakRSS355,984KiB does not include all DSP/DMA/global memory. The approved host3072MiB/pre-context2648MiB boundaries remained distinct; no startup credit, cleanup or threshold adjustment was used.

## First UI failure

The Player opened muted and paused with18.947s available while generation continued. Its only retained event is position0, not playing, playWhenReady=false. The actual background availability collector then called `EpisodePlayerSession.update` from `DefaultDispatcher-worker-8`; ExoPlayer required `main`. The saved stack identifies `PlaybackHostEffects` and the production repository flow. The Compose test continuation interceptor appears in that stack; implicit inherited-dispatcher assumptions were insufficient.

The driver retained that first exception, closed only its owned player and let the same already-requested AUDIO finish within its original bound. It did not stop/retrigger synthesis. The final COMPLETE/FROZEN_READY record and audio remain intact. The original claim of genuine concurrent playback must therefore remain **failed**, despite successful generation.

The targeted next step is explicit Player application-thread confinement plus a real repository IO-flow/ExoPlayer regression using staged copies of these exact retained chunks. Such a replay is non-neural and must not be relabelled HTP concurrency. Pi separately authorized one further clean genuine verification only after the fix, affected replay tests and new exact-APK guard proof pass; no automatic rerender was queued.

## Preservation

All12 previously existing episodes,18 jobs,67 episode files and other original user rows were unchanged, including the earlier ADMISSION failure and old2194failed/recovered evidence. Only one newly owned episode/source/revision/chapter/job, one chapter-audio row and58 owned files were added. No playback/export row was added. Cleanup errors0, settings preserved, processes/control/staging root absent, installed hashes verified and phone.lock released. Raw source text, WAVs, screenshots and original exception logs remain private/hash-bound.

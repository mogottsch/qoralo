# Genuine HTP playback observed; optional capture stopped the script

**Real concurrent playback is observed. The original all-in-one script remains FAILED on a capture-path exception; it is not retroactively a full E2E PASS.**

Run `provider-app-concurrent-20260913t123412z` used candidate13 `419c852bef5b563a3716b87b759d34c8cfa6a3817fda588c7f40ad3a2fd8af4a`, exact app `fe6ba7493bb1f3e3611a3994d0951f2a87006c983d9032349ebc6a3303ff5157` / test `359dbe7ac8392f1cb7a4a607a9be0d37ed4b4699d30736cffd3ee235c3a255d8`.

Owned episode `b8119444-092e-408e-b594-4e2e74e789a2`, job `e827aec4ad568ac804f5bc90c46ac9f71676c942aad71f51b413235cb4afb37b`:

| Observation | Actual evidence |
|---|---|
| First immutable chunk closed/verified |9801.837ms after explicit lock request|
| Listen first observed |10139.909ms after lock|
| Explicit muted Play; first observed advancement |10786.423ms after lock, position81ms|
| Sustained playback while actual AUDIO is RUNNING |Same player94686880 advances to1003ms;18.947s available; job/episode not complete|
| Actual live-tail underrun |Same player at18947ms, STATE_ENDED, not playing, wantsPlayback=true; no restart at0|
| Normal generation/publication |15 segments/165 QNN/HTP calls; same requested job reaches COMPLETE/FROZEN_READY without retry/recovery|
| Final master |`2194bce66f8abd05bdf10fefc5cf4aaef49cac647992f637db319b7d14be532a`,18,538,292B,9,269,124 mono PCM16/44.1kHz frames,210.184217687s|

All15 stream PCM payloads concatenate exactly to the master, including14×13,230 encoded zero-gap frames. Single chapter render89,643.558ms, functional-run render RTF0.42650; no canonical warm benchmark or microphone-confirmed TTFA claim. Owned process lifetime peakRSS338,408KiB is not total DSP/DMA memory.179 guard samples, minimum available2,732,280KiB, maximum30.1°C, maximum sample interval518.974ms; no stop, guarded native close recorded. Fixed3072MiB host/2648MiB pre-context policy and ongoing safeguards were retained.

## Capture failure and coverage boundary

Immediately after the real tail wait, the optional capture helper expected one `mCurrentFocus` line from `dumpsys window windows`. The field was absent and `.single` threw `NoSuchElementException`. No app/ExoPlayer thread error occurred. No screenshot was produced at that point. The exception was retained; the owned player closed and the same already-running AUDIO completed normally. No automatic new AUDIO or resynthesis occurred.

Pause-at-tail/new-arrival behavior, navigation/reopen, transcript/manual-follow and playing-through-Ready were not reached by this script. They must be separately recorded as retained-data replay observations, not fabricated as additional genuine-run events. Pi explicitly disallowed another neural run for this screenshot/I/O repair and directed a mixed-coverage handoff.

The capture repair treats missing/ambiguous focus as unknown, uses a targeted display dump, refuses to label foreign/changed-window output as paired, and makes optional capture failure nonfatal to functional checks. Focused tests retain the original missing-field failure case.

## Preservation

Original user rows/files and the earlier f029/75b87 failure+Ready/audio evidence stayed unchanged; only this new owned episode/job/audio evidence was added. Cleanup errors0, settings preserved, processes/control/staging root absent, exact installed pair reverified, phone.lock released. The preceding broader phone cleanup used explicit user authorization for one bounded pass over freshly checked ordinary user apps; targets/actions remain private. No app storage clear, system/ADB service kill, reboot or threshold ratchet.

Raw narration/audio and exceptions remain private/hash-bound. The exact waveform matches earlier2194 bytes but no new listening verdict is inferred.

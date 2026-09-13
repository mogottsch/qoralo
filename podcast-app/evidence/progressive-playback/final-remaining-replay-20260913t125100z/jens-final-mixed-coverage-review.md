# Final player/mini/transcript evidence review

Status: **UI implementation and the requested retained-data completion checks pass. Tested final APK pair is installed.** Evidence is deliberately mixed: genuine concurrent observations plus a zero-neural retained-data replay. The original interrupted genuine script is not relabeled PASS.

## Exact final identity and source continuity

- Installed app: `119e0f92640f258374065c134c14af22ba0131e3e866df17842e7d974f613c34`
- Installed test APK: `7ae210bf1e03db73f53cd298fcd17b7fe7da5cb06a69f0afdeb775e12f27d4d8`
- Verified against `provider-app-remaining-replay-20260913t125100z/installed-after.json`.
- Compared candidate13 genuine and candidate14 final-replay `source-bindings.json`: **all `app/src/main/` bindings are unchanged**. Differences are the two instrumentation drivers, optional debug capture helper, and its tests. Genuine observations came from app `fe6ba749…`; they are not falsely attributed to an identical APK hash.

## Coverage table

| Coverage | Genuine concurrent observation | Retained-data replay on final pair | Still unverified / limits |
|---|---|---|---|
| Play before generation completes | Muted player 94686880 advanced **81→1003 ms** while AUDIO RUNNING, first prefix 18.947 s available | Production repository IO flow drives Main-thread ExoPlayer without wrong-thread access | Not an audible-output measurement |
| Live-tail waiting | Same genuine player reached 18.947 s with playing=false, playback intent=true | Repeated with exact retained PCM | — |
| Pause through new audio; explicit and automatic resume | Not reached after optional capture-parser failure | Pause retained at **18.947 s** after prefix2; explicit resume to **19.549 s**; automatic resume beyond prefix2 frontier to **33.943 s** | Arrival is staged, not concurrent HTP in this replay |
| Minimize/navigation/reopen; speed; available-only seek | Not reached in interrupted genuine script | Same player **254896201** continues in mini Settings at **34.546 s**, reopens at **34.846 s**, changes to **1.25×**; seek bounds/no-autoplay checks pass | Production components in isolated replay host; Settings destination is a fixture |
| Transcript manual ownership and explicit follow | Not reached in interrupted genuine script | Real source text/audio: scroll **4124→4124** and same viewport across new chunks/passage advancement; explicit follow reveals measured segment highlight | Segment/chapter timing only, not word alignment |
| Generation Ready / same-player completion | The same genuine AUDIO job finished Ready after capture failure | Same replay player advances **49.906→50.689 s** across staged COMPLETE, then pauses at **50.765 s** | Genuine same-player Ready transition was not observed; pause is end of verification, not full-episode consumption |
| One uninterrupted genuine scripted E2E | **FAILED** at screenshot-owner parsing; original retained | Remaining functional checks pass independently, without another model call | No retroactive genuine-script PASS |
| Listening quality / full playback duration | Not reviewed | Muted only | No listening-quality, full-episode-listening, or word-alignment claim |

## Replay and visual checks

Replay source is exactly the newer retained episode `b8119444-092e-408e-b594-4e2e74e789a2`, job `e827aec4ad568ac804f5bc90c46ac9f71676c942aad71f51b413235cb4afb37b`, master `2194bce66f8abd05bdf10fefc5cf4aaef49cac647992f637db319b7d14be532a`.

Final receipt: `provider-app-remaining-replay-20260913t125100z/private-extracted-01/files/player-ui-captures/provider-app-remaining-replay-20260913t125100z/live-collector/.private-ui/replay.json` under `podcast-app/.local/progressive-ready/phone/`.

Receipt SHA-256: `89eb6dda0b5bd4279fbc31115e390a1cc29c3b8b21833656da4f3f23b94a5aba`.

Verified all ten required coverage flags plus no-autoplay and minimized advancement; every stage uses one muted Main player. `newModelCalls=0`, `newAudioJobs=0`, `replay=true`, `htpConcurrency=false`. All four optional retained-audio captures are genuinely paired to the owned window before/after, and PNG hashes/byte counts match their receipt entries. Viewed those four images: correct buffering/pause affordance at the available frontier, readable mini-player below the status bar, unchanged manual transcript browsing, and explicit current-segment highlighting after resume.

Viewed all eight final default/narrow-font2 synthetic images from `private-extracted-02`; validated sidecar SHA/size/identity and the exact 0→partial→COMPLETE viewport transitions. No new visual regression or source correction requested. This was an inline native review, with no new agent, phone session, or synthesis.

## Preservation and closure

`preservation.json` confirms all **14 existing episodes**, **20 existing jobs**, other existing rows, and **183 existing files** unchanged; no added real AUDIO/script/edit jobs in this final replay. Replay separately checks 36 copied source files and real source episode/job/playback state unchanged. `cleanup.json` has no errors, no data clear, all owned actual PIDs absent, and temporary control/remote files absent. Janek reports settings restored; final installed hashes were independently read from the controller's saved verification.

**No remaining concrete UI defect from the reviewed evidence.** This closes Jens's scoped implementation/review work for the mixed-coverage handoff requested by Pi. Keep the prior failure, genuine observations, replay evidence and remaining limits distinct in the user/dashboard summary. No additional synthesis is requested.

# Progressive playback — interim physical evidence

This is **not an E2E/deployment pass**. No genuine AUDIO inference has run in this campaign yet. The latest combined fix remains frozen but uninstalled because the unchanged device memory admission floor was not met.

## Frozen candidate

- Candidate04: `8693468326f052eaa59d54e61af2f0fd1111252327b307650810cc80d4a13d64`.
- App: `da9d015ebc69c5ee535abe6f84ccf9e07b1d16f17443b3795d2aa45086c2ee27`.
- Test: `173e4744fb30de9d778bbe84bf81e51f38e8df31295e92becd8aa3ce20a718bd`.
- Core `24b3961b`, paused-frontier repair `5303b45f`, Jens's geometry-invariant highlight `3afb0d64`. Controller also requires an explicit success receipt and verifies final installed APK hashes.
- 225 JVM tests passed;1 pre-existing optional long-pack test skipped.8 Python checks passed. Debug/test APKs and release Kotlin compiled. Existing debug Cursor `Recycle` lint diagnostic remains separately disclosed; lint is not claimed passing.
- All9 native library bytes and the provider manifest `423429c6642da131ac62511e3b233f1a121b97975aa5b6e9aa755bb13a927670` remain unchanged.

## First physical outcomes retained

1. `provider-app-progressive-20260912t14131789222385z`: first combined install. Default synthetic3/4 passed; paused-old-tail + arriving-chunk + explicit Play timed out. The transport treated the old item's ENDED state as the enlarged stream's frontier. Fixed by seeking the saved absolute cursor into newly available audio. No neural call/new job/owned episode.
2. `provider-app-progressive-20260912t141922z`: corrected candidate admission stopped before install/tests/models;3,367,140KiB available after own idle closure,33.9°C.
3. `provider-app-progressive-20260912t142140z`: candidate03 installed. Default4/4 passed, including the repaired paused-tail case. Narrow/font2 core2 + persistent-mini1 passed; manual transcript stability failed (axis2633→619). Highlighting changed paragraph geometry. Jens's subsequent fix preserves marker space and body weight; the strict assertion is retained, not relaxed. No neural call/new job/owned episode.
4. `provider-app-progressive-20260912t142833z`: latest candidate admission stopped before install/tests/models;3,314,420KiB,35.2°C after own idle closure.
5. `provider-app-progressive-20260912t143205z`: admission still stopped before install/tests/models;3,508,412KiB (~3.346GiB),35.4°C, below the unchanged3,670,016KiB (3.5GiB) floor. This is an admission observation, not an OOM minimum or a cause attributed to other experiments.

The original default mini screenshot also revealed a synthetic-fixture-only missing status-bar inset. Production already had the inset. Test-only `c78a7d9c` corrected the fixture; later default/narrow mini screenshots and assertions passed. Original screenshots and receipts were not overwritten.

## Preservation and resource limits

Fresh captures found11 current episodes,17 historical jobs and63 episode files, including user changes newer than the older nine-podcast inventory. All existing rows/files remained unchanged. User font/density settings were restored after synthetic profiles. Each controller retained failures and independently checked process/control/staging-root cleanup before releasing phone.lock.

The latest post-cleanup installed pair is still candidate03:
- App `0a487112b111d331271a35a564090a1648dba1463a8b6fa7dbe1093a9e699fc7`.
- Test `5785ffcedcaca628bca2894cd99219585b59048f3b83135d3aea96161ae2fb07`.

Existing authorization was used for background-only `am kill` requests to six individually identified cached ordinary apps, after checking user generation, foreground activity, audio and relevant services. A contemplated browser force-stop was blocked before execution because the process had already exited. No force-stop of those third-party apps, system/model process kill, reboot, data clear, swap change or memory-floor reduction occurred. The effect on available memory was not assumed to persist.

Raw inventories, DB/WAL snapshots, screenshots, package logs and detailed receipts remain private under `.local/progressive-ready/`. No listening verdict transfers to future generated audio. The pending next step is both synthetic profiles on candidate04, followed by exactly one normal owned AUDIO/muted progressive-player E2E when fresh resource guards admit it; deployment requires explicit E2E success, preservation and final installed hashes.

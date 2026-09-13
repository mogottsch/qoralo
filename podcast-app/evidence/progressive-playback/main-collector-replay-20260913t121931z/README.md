# Main-thread collector repair: retained-audio replay passed

**PASS for the focused non-neural validation; not a clean concurrent-HTP E2E pass.**

Jens `130b7a2a` explicitly confines host opening, collectors, restores and ticking to the Android main/application looper while retaining IO-dispatched file/receipt work and ordered cancellation/stale-session checks. Controller `9c90177f` requires its retained-audio replay proof before renewed genuine testing.

Candidate12 `acc277880adb6c4c806e82afd00450349f4e06aa55dbd17f96484f439cef0b3b` installed and tested:
- App `fe6ba7493bb1f3e3611a3994d0951f2a87006c983d9032349ebc6a3303ff5157`.
- Test `359dbe7ac8392f1cb7a4a607a9be0d37ed4b4699d30736cffd3ee235c3a255d8`.

## Actual focused device result

Run `provider-app-collector-probe-20260913t121931z` passed10 Android cases: owned blocked-teardown guard, the new real production-collector replay, and default/narrow UI4+4.239 JVM tests and15 Python checks passed at freeze;1 pre-existing optional test skipped. Native/model bytes unchanged.

The replay used exact retained2194PCM from the failed-before-Play genuine attempt, a separate cache ArtifactStore and in-memory database. Actual IO publication staged1→2→5→15 immutable items through `PodcastRepository.observeAudioAvailability` into the shared PlaybackHost/real ExoPlayer. It did not inject updates only on the main thread. All stages kept player75975702, main application looper, volume0 and speed1.25. Paused position stayed500ms during arrival; explicit Play advanced to935ms before **fixture** completion and1308ms afterward without replacing the player.36 source files and real episode/job/playback rows remained unchanged. Zero new model calls/AUDIO jobs; `htpConcurrency=false` is explicit.

The guard's owned non-neural blocked-teardown check recorded durable failure before self-only termination and59.734531ms stop-to-observed-process-absence. This is not a measured DSP cancellation/teardown guarantee. Both UI profiles passed and Jens reviewed the replay/visual evidence without requesting further source changes.

All original user rows/files/settings were preserved; cleanup errors0; installed hashes reverified and phone.lock released. Earlier USB failures are retained; this complete wave had working transport, not proof of permanent USB stability.

## Distinct genuine attempts and current boundary

Candidate13 `419c852bef5b563a3716b87b759d34c8cfa6a3817fda588c7f40ad3a2fd8af4a` uses the same APK pair and hash-binds the successful guard/replay/8UI proof. It skips redundant UI warmup before genuine AUDIO.

- `provider-app-concurrent-20260913t122244z`: whole-start check stopped before instrumentation/jobs/models at2,901,420KiB,30.9°C.
- Pi authorized one fresh selection and at most two background-only closes. Fresh foreground/job/audio/service checks identified two cached ordinary apps; only `am kill` was requested, no force-stop/system action. One bounded settling interval observed3,244,044KiB; no attribution or persistence guarantee was assumed.
- The one subsequent fresh gate, `provider-app-concurrent-20260913t122726z`, stopped before instrumentation/jobs/models at **3,135,664KiB**,30.2°C,10,064KiB below the unchanged3,145,728KiB whole-start boundary. No further cleanup/polling/retry chain followed.

The approved3072MiB whole-start/2648MiB pre-context policy and1280MiB/42°C/stale/identity/durable-teardown safeguards remain unchanged. Fixed-build actual playback while HTP generates remains unverified; the original successful165-call audio generation and its wrong-thread Player failure remain separate retained evidence. The exact fixed APK is installed, but no full E2E/deployment pass is claimed.

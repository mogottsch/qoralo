# Long probe paused before controller invocation

At the authorized pre-run identity/PID check on2026-09-10, actual package `dev.vibevoice.podcast.internal` had MAIN PID4813. Generation and test-package PID probes reported absence. The authorization allowed maintenance only for a sole stale test package, so Janek **stopped without killing anything**.

This was not a long-TTS runtime attempt or failure. No controller invocation, installs, model-pack staging, DB snapshots, constructors, neural Runs or WAV occurred. No data was cleared; no settings were changed. The pre-run lock was released. The main process was deliberately left present: no clean-idle/process-absence claim, and no speculation about why it was running or whether its state is safe to close.

Pi is obtaining Moritz's permission for any main-app force-stop (including unsaved-UI risk). Further phone work requires that explicit decision and fresh continuation authority. Exact candidate `b86008708cc459c855149eee49c58a7468e079d24c9de4842eab56a5bcef325d` and its independent source/pack/staging approval remain unchanged; no rebuild or repeated readiness review is required.

`retained-manifest.json` binds42 unchanged original files/2,277 bytes from `.local/tts-long-maintenance/20260910t192219z/`. No battery/thermal, DB or global logcat was captured in this check. No retry or push occurred. There is no long listening sample; the accepted short sample is unaffected.

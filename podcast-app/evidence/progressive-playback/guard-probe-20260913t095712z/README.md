# Owned non-neural guard check

**PASS for the injected-condition blocking-worker check and two affected progressive-player regressions. Not a genuine AUDIO E2E or proof of in-flight QNN cancellation.**

Run `provider-app-guard-probe-20260913t095712z` used frozen source `6f60226f`, candidate `11f92e628b117871b3d09e82c812767380a6e3d91bde9bc5661077b6d66ce994`.

Exact tested/post-cleanup installed APKs:
- App `5d39bf1ddabdf9099650e909ffbd9f34889f496f57732ae2876870b2dbd4b80c`.
- Test `01abcf633460f9f0e8c2ab359140aa1c1a3fd2c4f408f8527186a671c0a4edcd`.

## What was exercised

The dedicated non-sticky `:guard_probe` process authenticated its synthetic plan, PID and process-start ticks. An independent sampler read actual device fields but injected a low available-memory value after a separate worker blocked in a long sleep. No real memory pressure was created. The independent watchdog detected the low sample, committed its exact owned private worker row to FAILED, durably wrote the receipt, rechecked the process/plan lease and terminated **only itself**.

The instrumentation observer measured **38.001198ms** from stop decision to absence of that process. Durable failure preceded termination. The private fixture contained one synthetic worker row; the user's podcast database received zero AUDIO/SCRIPT/EDIT jobs. No model construction or neural call occurred. The controller's probe branch returned before any AUDIO entry.

All3 Android cases passed: this guard probe plus the two progressive ExoPlayer regressions.234 JVM tests passed with1 pre-existing optional skip;10 Python checks passed for the freeze. Host cases cover admission/proactive thresholds, thermal/unknown/stale/future samples, plan/PID-start identity mismatch, a blocked sampler, lost ownership, uncommitted failure, lease closure, and retained partial audio without Ready/retry.

## Safety and limits

The provisional guarded policy is opt-in for the exact owned debug evaluation, not a global production relaxation:3GiB start, proactive stop below1280MiB or at42°C,600MiB emergency reserve,2s maximum sample age and600s run bound. Ordinary/historical neural gates retain3.5GiB. This non-neural probe used the separately allowed2GiB floor.

Sampler and watchdog run on separate threads, independently of the JNI execution thread. Provider cancellation remains `CancellationException`; managed boundaries check it, and the service uses NonCancellable owned failure persistence. There is no exposed in-flight QNN cancellation API. The fallback's measured latency above is for this non-neural worker and private SQLite transaction, **not a proved DSP teardown latency or universal allocation bound**. A missing current lease or unsuccessful durable failure transaction refuses destructive termination.

All11 existing episodes,17 jobs,63 episode files and other user rows remained unchanged. Cleanup errors0; processes/control/staging root absent and phone.lock released. Native libraries/model pack bytes were unchanged. Genuine AUDIO+livePlayer testing remains pending; any changed APK must revalidate the exact guard-proof binding before neural entry. Original earlier UI failures and resource stops remain retained.

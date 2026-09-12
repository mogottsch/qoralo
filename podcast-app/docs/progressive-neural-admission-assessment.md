# Progressive neural admission assessment — 2026-09-12

**Assessment only. No neural floor change, monitoring implementation or new neural attempt is authorized by this document.** The frozen controller's neural floor remains3.5GiB. Its separately authorized2GiB mode runs only the eight synthetic UI cases and returns before the neural entry point.

## Budget and a possible evaluation threshold

The retained [provider memory assessment](provider-memory-assessment.md) provisioned1920MiB plus a600MiB emergency reserve, or2520MiB. It includes four QNN contexts (1GiB provision), serial context-read/copy allowance256MiB, managed/UI/framework512MiB, explicit buffers64MiB and WAV/page-cache64MiB. The actual binary metadata is not a proved upper bound; opaque QNN/DSP/DMA allocations and device-wide variation remain unaccounted-for uncertainties. Process RSS is not total route memory.

Progressive playback adds a durable copy of about18MiB of speech chunks for this reference, ExoPlayer buffering/decoding and additional private UI/telemetry capture activity. The existing512MiB framework allowance already includes main/instrumentation/generation processes, but this combined workload has not been measured with neural generation running. Retain a further **128MiB provisional allowance** rather than claiming these additions cost zero. Revised planning envelope:2048MiB +600MiB reserve =2648MiB.

Consequently2.5GiB (2560MiB) is no longer a prudent proposed starting point for this combined diagnostic workload. **3GiB (3072MiB) is a plausible tightly guarded evaluation threshold**, leaving424MiB beyond the additive envelope/reserve. It is not a demonstrated safe minimum or a recommendation to change the neural validation gate without the controls below. The current3.5GiB rule was conservative, not an observed OOM boundary; repeated host-only tests cannot prove a lower neural floor.

## What the current implementation can actually stop

- `ProviderNative.create` synchronously creates all four contexts. There is no managed callback between constructors.
- `ProviderNative.renderSegment` synchronously performs eleven graph calls (duration, text, eight vector steps, vocoder). Its ORT call uses ordinary `RunOptions{nullptr}`; there is no exposed termination/cancellation handle or checked deadline between those native calls.
- Kotlin progress callbacks occur at segment boundaries. `GenerationService.onDestroy` cancels its coroutine scope, but coroutine cancellation cannot interrupt an in-flight JNI/QNN call. Android's data-sync foreground-service timeout is not a prompt low-memory guard.
- Provider load/render catch generic `Throwable` and wrap it in `InferenceRouteException`. A cancellation thrown inside these blocks can therefore lose its distinct cancellation type before reaching the service's `NonCancellable` cancellation-persistence branch. The watchdog can later reconcile orphaned owned work, but that is not proven prompt cooperative cancellation.
- The existing host controller authenticates the owned episode/job and can close its app processes, then use the normal watchdog to retain failure history. It currently samples headroom before/after inference, **not continuously during context creation or a segment**. A600/660-second test bound is not a memory-safety monitor.

Thus the present APK/controller cannot honestly promise to stop a low-headroom run before the600MiB reserve is exhausted. It must not simply have its neural constant changed from3.5 to3GiB.

## Minimum controls before evaluating a lower neural floor

1. **Bind the monitor to one attempt.** Freeze APK/native/pack/plan/episode/revision/job identities. Record the generation PID and `/proc` start ticks; re-check ownership before stopping it. Reject stale PID reuse, changed active work or unknown user playback. No generic package/process killing or retry.
2. **Monitor while native code is blocked.** Use an independent bounded sampler during constructor/graph work, not only Kotlin segment callbacks. Capture `MemAvailable`, temperature, owned-process RSS and timestamps; treat stale/missing samples as a stop condition. Keep the phone lock for monitoring and all cleanup. Process RSS remains supporting evidence only.
3. **Use a proactive reserve.** A candidate evaluation policy could request stop below1280MiB available or at42°C;600MiB remains an emergency boundary, not the normal trigger. The680MiB gap is intended to cover detection/stop latency and one large allocation, but neither burst size nor latency is proved bounded by the current evidence. A second, lower hard-stop boundary cannot replace proof of timely ownership checks and termination.
4. **Make cancellation explicit and testable.** Preserve `CancellationException`, check cancellation/admission at managed boundaries and provide an authenticated cancellation signal. Native constructor/graph boundaries need stop checks or an independently verified owned-process termination fallback. Do not claim in-flight QNN cancellation exists when it does not. Prove failure persistence and retained validated chunks, with no Ready/export publication, no automatic AUDIO retry and no transfer of another attempt's playback state.
5. **Validate the guard without neural work first.** Deterministically inject low/stale/thermal samples and stale identities; verify stop decisions, deadlines and owner checks. Exercise an owned non-neural blocking worker to measure termination/cleanup latency. A fake worker proves orchestration, not QNN's actual cancellation latency; retain that distinction for the eventual single guarded neural run.

The source scope should remain small, but some production cancellation/native-boundary work or a proven external owner-bound termination path is needed for a credible lower-floor evaluation. That work is **not needed for synthetic UI isolation** and was not added to the already-tested UI-only APK.

## Current physical boundary

`provider-app-ui-only-20260912t143635z` passed default4/4 and narrow/font2 4/4 using the explicit2GiB synthetic-only mode. It made zero model constructions/calls/new AUDIO jobs and left the exact tested `da9d015e…ee27` / `173e4744…18bd` pair installed. This result supports the UI-only stage, not the proposed neural budget or monitoring policy. User data/settings were preserved and the phone lock released.

# Review qualification: a generation-time override also changes effective speed semantics

This is an additive qualification to option2 in the sealed `998ffd2` duration-source trace. Its31Slice/4Clip/no-fixed-prefix conclusion remains unchanged. No new model case, inference, graph/native/app change or execution permission is created here.

## Documented control and equivalence

Pinned upstream `supertonic`1.3.1 exposes `speed`, with documented/validated range0.7–2.0 and default1.05. The core computes `duration = DP / speed` **before** constructing the latent mask/noise. Its public `synthesize` and low-level `__call__` signatures do not expose a requested-duration argument. The internal `sample_noisy_latent(duration)` helper is not an existing app/debug duration toggle or an endorsed high-level duration override.

Consequently, replacing the generated-time budget with D is conditioning-equivalent to an effective speed `DP/D`, apart from floating-point conversion details, within the same mask/noise construction. It is not PCM time stretching, but it is **not unchanged speed semantics** merely because a reported field remains1.0.

Using the retained CPU predictions of~29.81s, a hypothetical D=90s corresponds to effective speed~0.331, below the public0.7 minimum. At the documented minimum0.7, source arithmetic yields only~42.6s. These are calculations from saved outputs, **not additional model runs or a90s trial**. The documented range is not proof of a training limit or of behavior outside that range.

## Correct option boundary

Any future length-conditioning proposal must be called an **explicit experimental generation-time/speed-semantic override**. It changes the effective pacing, latent mask/noise and inference contract. It therefore requires an explicit relaxation of the current DP/speed1 semantics, a separately justified target, fresh native/debug control and candidate review, exact tensor/budget binding, new execution authority and coverage/listening evidence.

It is not a source-preserving cap fix, an already-approved option, a product remedy or a way around the speed constraint. Merely retaining the label`speed=1` would be misleading. No such control was implemented.

Under the unchanged DP-output/speed1/full-text/one-render contract, this investigation has identified **no validated remedy** for the short long-input narration. Do not remove sentence-token/relative-alignment slices, use hidden chunks, replace DP, repeat full TTS, or infer that a longer WAV would be complete. The short product-plumbing work remains separate.

Nik supplied this qualification and then accepted the complete source trace as a scoped negative finding; Pi received it. Independent audit: `/home/moritz/.cache/nik-podcast-reviews/duration-source-trace-20260910/independent-audit.json`. Final source-mapping review is distinct from any future experiment authorization. Source passages, previous-result identity and source-only arithmetic are retained in `source-evidence.json`. No push.

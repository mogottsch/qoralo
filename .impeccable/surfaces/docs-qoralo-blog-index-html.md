---
version: 3
slug: docs-qoralo-blog-index-html
primary_target: docs/qoralo-blog/index.html
related_targets: [docs/qoralo-blog/style.css, docs/qoralo-blog/article.js, docs/qoralo-blog/README.md, docs/qoralo-blog/REVIEW.md, docs/qoralo-blog/evidence/source-audit.md, docs/qoralo-blog/evidence/bos-zero-replay.json]
---

# Local source-to-podcast technical article

Mode: Read. Audience is technical. Keep the narrative short, explain a real engineering mechanism, and give one concrete takeaway. NotebookLM-inspired local phone inference is the subject; Qoralo is the prototype name, not the headline. Moritz rejects subtext, repeated qualifications and AI-sounding copy, and wants to edit the text himself. No new phone activity, model inference, app/runtime/deck changes or public publication.

## Direction contract

THESIS (gist first in plain words; no meaningless values; the step-by-step explanation was cut on request): Explain WHY the early Pocket TTS Android port went wrong, as the main point. The graph treats a NaN first input as "use the learned start vector"; on the phone the first input was observed to be zeros; zeros compound over the autoregressive loop until the stop score never crosses its threshold. The fix actually applied (NPU-oriented fixed-cache graphs) gets one short section. Moritz does not want the buffer-lifetime finding presented as "my fix".

OWN-WORLD: Inherit the presentation's #0b1017 canvas, mint #8ee8c2 HTP, lilac #c2a9f4 GPU and blue #9bbdff CPU, plus a warm amber for the failing zero input. Flat technical drawings, restrained local sans. No decorative gradients/cards/hero metrics/eyebrows, generated mockups or invented data.

STORY: NotebookLM prompts the phone question; the intro is plain placeholder text for Moritz to rewrite. Phone placement, the first Android port with exact historical recordings, then the WHY with a real stop-score chart, then the applied fix and one takeaway.

CLAIM LIMITS: the phone check is observed, so no "inferred" hedging in the main text; zeros are labelled as seen in the instrumented build (2 of 2), NaNs with the buffer kept alive (2 of 2), the four kept-alive runs stop at 53, and the second unmodified run differed (nondeterministic). Keep in the notes, not in the way of the explanation: old executable not retained (rebuilt, NDK 27); original graph missing (reconstruction reproduced the failing recording byte for byte); dump build may perturb allocation; no explanation of why this allocator returned zeros; no listening verdict on new audio; the zero-encoder/invalid-Bria failure is a separate cause. The 10.72 s clip is Android CPU, not HTP.

FORM: Three progressively enhanced figures: processor route; one generation step (start vector or previous frame in, one internal state out, read twice as the next 80 ms frame and the stop score; the stop-check rule); and the WHY figure (input-path rows, a baked-in SVG stop-score chart generated from `evidence/bos-zero-replay.json`, an input toggle and a keyboard frame scrubber whose readout gives audio time and the stop-check verdict). Native exact-file players, inline plain-text editing with local restore, `Save HTML copy`. The static chart and all text stay meaningful when JavaScript fails. No external fonts, UI dependencies, analytics or raster assets.

## Editing contract

`[data-edit]` text becomes `contenteditable="plaintext-only"` on request. Only edited paragraphs are stored (localStorage keyed by path) or exported, so untouched text keeps inline `<code>`. Saving builds from the original page source, not the live DOM, strips editor state, and adds a `<base>` so the copy finds its assets. Never writes into the repository.

## Motion and interaction thesis

Focal moment: the user flips the first input between NaN and zeros and watches which stop-score line the retained phone run follows; a scrubber gives exact per-frame values. Transitions are short opacity changes, removed under reduced motion. Route buttons emit one illustrative signal. Meaning survives reduced motion and failed JavaScript through the static chart, text and border/colour states. No endless animation; audio never autoplays and players do not overlap.

## Finish record

See REVIEW.md. Browser suite passed chart data against the evidence JSON, five widths × three input modes with geometry checks, keyboard scrubber exact readouts, wording guards against overclaiming, reduced motion, exact WAV decoding, editing, local restore, a saved copy reopened from disk with a working chart, print and script-failure fallback. Pi independently reran the replay and directed the claim limits; no new three-pass review of this copy.

Disposition: finish at this scope for Moritz to edit and review. Final app demo/audio and any public publication remain separate.

## Agenda update

Approved by Moritz: title, intro and question frozen; demo video right after them (missing-asset notice until the file exists); then what we tried and a small benchmark table (RTF explained in a small note box, plain values within comparable groups only); then the full-system flow diagram (computer preparation separate from phone inference); then the Pocket TTS failure; the ending is "If you wanna take a look, here it is" (private repository link). No "what is left" section. Everything condensed; numbers only if a reader would care (RTF yes, frame cap no).

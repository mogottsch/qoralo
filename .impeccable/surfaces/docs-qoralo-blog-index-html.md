---
version: 3
slug: docs-qoralo-blog-index-html
primary_target: docs/qoralo-blog/index.html
related_targets: [docs/qoralo-blog/style.css, docs/qoralo-blog/article.js, docs/qoralo-blog/README.md, docs/qoralo-blog/REVIEW.md, docs/qoralo-blog/evidence/source-audit.md, docs/qoralo-blog/evidence/bos-zero-replay.json]
---

# Local source-to-podcast technical article

Mode: Read. Audience is technical. Keep the narrative short, explain a real engineering mechanism, and give one concrete takeaway. NotebookLM-inspired local phone inference is the subject; Qoralo is the prototype name, not the headline. Moritz rejects subtext, repeated qualifications and AI-sounding copy, and wants to edit the text himself. No new phone activity, model inference, app/runtime/deck changes or public publication.

## Direction contract

THESIS: Explain WHY the early Pocket TTS Android port went wrong, as the main point. The graph treats a NaN first input as "use the learned start vector"; on the phone the model behaved as if it got zeros; zeros compound over the autoregressive loop until the stop score never crosses its threshold. The fix actually applied (NPU-oriented fixed-cache graphs) gets one short section. Moritz does not want the buffer-lifetime finding presented as "my fix".

OWN-WORLD: Inherit the presentation's #0b1017 canvas, mint #8ee8c2 HTP, lilac #c2a9f4 GPU and blue #9bbdff CPU, plus a warm amber for the failing zero input. Flat technical drawings, restrained local sans. No decorative gradients/cards/hero metrics/eyebrows, generated mockups or invented data.

STORY: NotebookLM prompts the phone question; the intro is plain placeholder text for Moritz to rewrite. Phone placement, the first Android port with exact historical recordings, then the WHY with a real stop-score chart, then the applied fix and one takeaway.

CLAIM LIMITS (must stay visible): zeros are inferred from a host replay, not observed; nothing read the phone's memory. The retained source is not bound to the old binary. The original graph is missing; a same-size reconstruction reproduces the retained desktop run. The scan is 62 prefix/suffix patterns, not exhaustive. No replay audio. The 10.72 s clip is Android CPU, not HTP. The zero-encoder/invalid-Bria failure is a separate cause.

FORM: Two progressively enhanced figures: processor route, and the WHY figure (input-path rows, a baked-in SVG stop-score chart generated from `evidence/bos-zero-replay.json`, an input toggle and a keyboard frame scrubber). Native exact-file players, inline plain-text editing with local restore, `Save HTML copy`. The static chart and all text stay meaningful when JavaScript fails. No external fonts, UI dependencies, analytics or raster assets.

## Editing contract

`[data-edit]` text becomes `contenteditable="plaintext-only"` on request. Only edited paragraphs are stored (localStorage keyed by path) or exported, so untouched text keeps inline `<code>`. Saving builds from the original page source, not the live DOM, strips editor state, and adds a `<base>` so the copy finds its assets. Never writes into the repository.

## Motion and interaction thesis

Focal moment: the user flips the first input between NaN and zeros and watches which stop-score line the retained phone run follows; a scrubber gives exact per-frame values. Transitions are short opacity changes, removed under reduced motion. Route buttons emit one illustrative signal. Meaning survives reduced motion and failed JavaScript through the static chart, text and border/colour states. No endless animation; audio never autoplays and players do not overlap.

## Finish record

See REVIEW.md. Browser suite passed chart data against the evidence JSON, five widths × three input modes with geometry checks, keyboard scrubber exact readouts, wording guards against overclaiming, reduced motion, exact WAV decoding, editing, local restore, a saved copy reopened from disk with a working chart, print and script-failure fallback. Pi independently reran the replay and directed the claim limits; no new three-pass review of this copy.

Disposition: finish at this scope for Moritz to edit and review. Final app demo/audio and any public publication remain separate.

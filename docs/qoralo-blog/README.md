# Qoralo visual article

Open `index.html` directly, or serve the repository root and visit `/docs/qoralo-blog/`. Static HTML, CSS and inline SVG; no build, CDN, analytics, API, audio playback or model execution.

This replaces `../qoralo-linkedin-draft.md`. It is a short article draft committed to the private repository, not a LinkedIn post or public release.

## Confirmed brief and scope

Moritz requested a very short, beautifully designed article with at least two or three custom visualizations, more visuals than prose, simple human wording and no marketing voice. He explicitly authorized three real reviewer passes. Pi instructed no phone/model work and requested consultation with the existing owner Hermes if accessible. Reader assumption: technically curious people encountering this project for the first time. The final app demo and exact-output listening review remain pending.

The article extends the existing presentation's dark canvas, mint HTP, lilac GPU and blue CPU roles into a responsive reading layout. It is not a deck or a replacement app design. No global product/design files are changed. Its three evidence-based visuals explain compute placement, four-session setup, and emitted chapter audio. The last two have real proportional geometry; symbolic document/audio icons in the first are diagrams, not model captures.

## Source boundaries

- Gemma GPU and Supertonic HTP are separate model routes, with CPU orchestration. The diagram does not assert all operations run on one accelerator or that both models run simultaneously.
- Startup bars: experiment 0023, source `21.6129s` versus context `0.497816s`, medians of three fresh processes per arm, same fixed legacy input/runtime. This is four speech-session construction only, excluding offline compilation and speech generation. Source/context HTP output equality is not CPU/HTP numerical equality.
- Chapter bars: CPU outputs for the same 487-word input. Experiment 0036: `1,304,030` frames, rejected. Experiment 0037: fifteen native outputs total `9,077,760` frames plus fourteen `13,230`-frame gaps, total `9,262,980` at `44,100Hz`, accepted. HTP's corresponding experimental file was also accepted, but is not the plotted bar. Multiple recipe settings changed together. No fixed 30-second model cap, isolated segmentation causality or general quality guarantee follows.
- Original numerical failures remain unchanged. Experimental acceptance is exact-file acceptance; no verdict is transferred to a new app WAV. Later complete headless SCRIPT results do not constitute a final normal-UI-to-audio demonstration.

## Reviews and verification

See `REVIEW.md` for the actual review passes, incorporated edits, Hermes consultation and browser results. The page's expanded records provide concise links to the owning source/result files. Private repository links are internal references, not an offered public code release.

The final page has 299 main-article words including diagram labels/captions. Three actual peer reviews were performed by Thomas, Pi and nik; no new reviewer agent was launched after the launcher failed. The original author alone applied edits. Hermes supplied narrow style guidance through the existing gateway.

To repeat the browser checks, serve the repository root and open the article using the Chrome skill wrapper, then pass `browser-checks.js` to its `run-code` command. The callback checks five widths, exact data geometry, source-disclosure keyboard operation, loaded-page offline operation and print presence. Static file/data checks additionally compare the bars with the owning experiment JSON. No model or phone is involved.

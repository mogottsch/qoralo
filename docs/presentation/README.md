# Project presentation

Open [`index.html`](index.html) directly in a modern browser. CSS, JavaScript and diagrams are inline, with no external runtime service or build step. Two optional recordings live in `audio/`; keep that folder beside the HTML when sharing or moving the deck.

For a local preview, from the repository root:

```bash
python3 -m http.server 8766 --bind 127.0.0.1
```

Visit <http://localhost:8766/docs/presentation/>. Serve the repository root so the notes can open both `docs/` pages and the reconstruction's relative experiment/app evidence links. The deck still works directly from `index.html` without a server.

## The seven-slide main story, with optional details

```text
Main: Our journey → GPU vs NPU → Architecture × deployment → Our phone → How models run → Models & results → [Supertonic 3 → HTP]

Optional paths:
  Our phone      → Inside Hexagon             → How models run
  How models run ↔ QNN backend map
  Supertonic 3 → HTP (root slide 7) ↔ 11-step reconstruction walkthrough
  Models & results ↔ Supertonic 3 architecture
                       ↔ Why Supertonic splits long text
  Models & results ↔ Gemma 4 E2B architecture
```

The default arrow-key path follows **seven main-story slides**. **Models & results** is slide 6, followed by the **Supertonic 3 → HTP** one-page overview as the final root slide 7. **Inside Hexagon**, **QNN backend map**, **Supertonic 3 architecture** and **Gemma 4 E2B architecture** are optional. The GPU/NPU comparison continues directly to architecture × deployment. The phone's hardware detail rejoins at **How models run**. The backend catalog opens from and returns to the deployment slide; continue from there to the models and results.

Reach the **Supertonic 3 → HTP** one-pager with the right arrow or the **Supertonic on HTP** button on slide 6. On slide 7, **Walk through 11 steps** enters the optional subslideshow. Arrow keys and visible Previous/Next controls follow its eleven steps; both ends return to root slide 7. Every detail also has an immediate **HTP overview** exit. The one-pager is part of the main story; only the eleven details are optional. Right arrow at root slide 7 stays there rather than entering the details automatically.

The hardware detail offers **Back to choices** and **How models run**. The backend catalog has **Back to model path**; either arrow key also returns to deployment. The Hexagon block on the phone slide remains clickable. Select the prominent **Supertonic 3** or **Gemma 4 E2B IT** architecture entry on slide 6 for its architecture; either arrow or **Models & results** returns there. Within Supertonic architecture, **Why short chunks?** opens a separate nested detour. Both arrows and its return button go back to the architecture, so normal architecture navigation does not force this additional detail.

## Presenting

- The **Models & results** slide links to the [TTS benchmarks and audio](../android-benchmarks/index.html) and [LLM benchmarks](../android-llm-benchmarks/index.html). Links open in new tabs so the presentation keeps its place. Model names are a short index, not a ranking; detailed evidence stays in the registries.
- **Map** or **M** opens the overview. Jump to any main slide or optional detail; the map marks the current location.
- **← / →**, **Page Up / Page Down**, and **Space** follow the current route. Space still activates a focused button normally.
- **Home / End** go to the first/last main-story slide, never into an optional appendix by accident.
- **N** or **Notes** opens the current slide's talk track, caveats and references. This is an on-screen dialog, not a separate presenter display.
- Every card on the optional **QNN backend map** opens a detail dialog with two focused sections: **Execution** and **Sample use cases**. Short bullets carry the main points; compact paragraphs provide the technical detail and limitations.
- **F** or **Fullscreen** toggles fullscreen. **Esc** closes a dialog or exits fullscreen. Branch choices and return buttons remain available inside the slides when fullscreen hides the toolbar; **M** still opens the map.
- The GPU/NPU illustrations on slide 2 are static. Background and qualifications remain in speaker notes; there is no separate deep-dive slide or AI-specialist popup.
- The toolbar counter is **route-relative**: `4 / 7` in the main story, `1 / 1` inside a single-slide detour, or `7 / 11` inside the HTP walkthrough. The walkthrough also retains its step count and controls inside the canvas for fullscreen use. The route label and optional-slide headings explain the context.
- Slide hashes use stable IDs. Direct links, refresh, and browser Back/Forward preserve the destination and infer the right route.
- Every viewport fits a fixed 1920×1080, 16:9 stage. Portrait phones letterbox rather than rearranging the diagrams. Browser printing includes all slides, including optional details, but omits navigation buttons.

## Current content and links

### Main story

1. [From models to an app](http://localhost:8766/docs/presentation/#slide-1) — the five-step journey: **VibeVoice → smaller TTS**; **TTS on HTP**; **Local LLMs**; **LLM backends**; **App prototype**. Each phase has one short detail beneath its label; the full opening stays under 85 words without cards. Detailed evidence remains in notes.
2. [GPU vs NPU](http://localhost:8766/docs/presentation/#slide-2) — illustrated GPU work-array and NPU matrix/data-reuse panels compare broad parallel computation with neural-network specialization. Both graphics are static. Both can accelerate AI; specialization is not a speed guarantee. Under 80 visible words, with background and qualifications in speaker notes based on the [NPU wiki](../wiki/concepts/npu.md). No Snapdragon software-route strip.
3. [Architecture × deployment](http://localhost:8766/docs/presentation/#slide-3) — four quadrants, two vendor/product examples per quadrant, and naming caveats in notes.
4. [Inside my Galaxy S23 Ultra](http://localhost:8766/docs/presentation/#slide-4) — the CPU, Adreno 740, Hexagon/HTP V73 and shared RAM; **this is the branch point**.
5. [How models run: From model to Hexagon](http://localhost:8766/docs/presentation/#slide-5) — development-machine preparation and phone execution, with QAIRT/QNN, target-specific contexts, and compatibility caveats. **Always on the main path; the hardware detail rejoins here.**

6. [TTS & LLM models and results](http://localhost:8766/docs/presentation/#slide-models) — two softly tinted collections in the deck's existing mint/lilac palette, with speech/text graphics, larger architecture entries, secondary model lists and aligned benchmark links. Existing typography and all model information are preserved; prominence indicates an available deep dive, not a ranking. TTS: Supertonic 3, Pocket TTS, Kokoro, MOSS-TTS-Nano and the VibeVoice family. LLM: Gemma 4 E2B IT, Qwen3.5-2B and LFM2.5-2.6B. Two direct benchmark links; no copied measurements or new quality verdicts.

7. [Supertonic 3 → HTP](http://localhost:8766/docs/presentation/#slide-supertonic-htp) — the deployment one-pager closes the root presentation. Its button opens the eleven-step detail route; every detail can return here.

### Supertonic → HTP: one-pager and nested walkthrough

Open [the HTP one-pager](http://localhost:8766/docs/presentation/#slide-supertonic-htp) as **root slide 7**, after **Models & results**. It summarizes host preparation and Android execution, with a prominent entry into the eleven-step reconstruction and a direct link to [the source Markdown](../supertonic-android-htp-reconstruction.md).

The walkthrough maps one-to-one to the document, not to a fictional clean success path:

| Step | Slide ID | Main visual / lesson |
|---|---|---|
| 1 | `slide-htp-reference` | We ran the complete model on CPU first to establish a reference; architecture retained |
| 2 | `slide-htp-runtime` | Our packaged ORT lacked QNN support; recorded Android build options show how we enabled it |
| 3 | `slide-htp-shapes` | Actual dynamic-shape rejection, then concrete T239/L238 sizes |
| 4 | `slide-htp-int8` | Actual CPU / mixed / HTP placement; INT8 did not mean full offload |
| 5 | `slide-htp-softplus` | Why official FP32 avoided the INT8 quantized-op blockers; then the remaining Softplus rewrite |
| 6 | `slide-htp-proof` | Numerical comparison failed, but Moritz accepted the final audio; both checks mattered |
| 7 | `slide-htp-contexts` | Long startup prompted precompilation; exact-scale 21.6129s vs 0.497816s setup bars |
| 8 | `slide-htp-android` | APK library visibility; load-only proof separate from short synthesis |
| 9 | `slide-htp-capacity` | From short clips to one full chapter; play the actual rejected ~30s CPU/HTP WAVs |
| 10 | `slide-htp-recipe` | The provider's four-step long-text recipe and its accepted exact chapter samples |
| 11 | `slide-htp-reusable` | Integrating that recipe into the app with a reusable pack; app output still not reviewed |

The one-pager is a summary of the resulting route; the detail slides preserve chronology, failures and qualifications. Speaker notes cite the reconstruction, owning records and exact result/tool paths. A mathematical identity is not promised bitwise backend equality. Failed numerical gates stay failed. The 0037 recipe changed several factors, so segmentation alone is not declared causal. The new app WAV remains `not_reviewed`; its zero-inference publication recovery is not a second synthesis run. Current Qoralo naming is distinguished from historical package identities.

The walkthrough is written as a report: what we tried, what failed, what changed and what happened. Implementation details such as native-edge indices and the publication-recovery mechanism remain in Notes rather than crowding the main explanation. Dynamic-shape rejection is distinguished from the separate ORT Pad-selector crash. Observed ~30-second long-input outputs are not presented as a demonstrated hard cap.

No new inference, phone benchmark, listening verdict or hardware measurement was produced for these slides. Diagrams are authored HTML/SVG, and the startup chart uses the exact retained ratio. The compilation command shows the actual options from the saved August 13 ORT build log through the standard `./build.sh` wrapper; the log did not retain the outer shell invocation. [Build provenance](evidence/qnn-build-record.json) records that distinction, source hash and required container paths. This is not a turnkey SDK installation guide.

### Rejected whole-input recordings

The two players on [step 9](http://localhost:8766/docs/presentation/#slide-htp-capacity) are unmistakably labelled **REJECTED**. They are failure examples Moritz judged unusable, not the later accepted provider-recipe output.

- CPU: `audio/0036-cpu-rejected.wav` · SHA-256 `9b1c8587308fb2a98ef1d600549e8f06beec86c3419684789279a143b17c46d2`.
- HTP: `audio/0036-htp-rejected.wav` · SHA-256 `3ae276f2d61eae37b05df23c334704e69434700dbd9360f74768c075ad40a69c`.

Both are byte-identical copies, with no re-encoding, trimming, normalization or new synthesis. [Audio provenance](audio/manifest.json) binds their source paths, byte counts, sample counts and rejected listening records. Native controls require explicit playback; `preload="none"` avoids loading audio merely by navigating. Starting one recording pauses the other. Leaving the slide or hiding the page pauses playback; returning does not resume it. Arrow/Space media controls do not navigate the deck. Download links remain available if playback fails. Browser playback tests are muted technical checks, not new listening assessments.

### Other optional details

- [Why Supertonic splits long text](http://localhost:8766/docs/presentation/#slide-supertonic-long-inputs): an optional detour from the architecture, backed by the [existing long-form wiki note](../wiki/concepts/supertonic-long-form-synthesis.md). A dated quote establishes the original release's up-to-30-second training segments; the visible version-3 qualification prevents transferring that exact cutoff. A shared-scale chart compares the same 487-word chapter's emitted CPU audio: 29.57 seconds / 89.09% ASR word error / rejected versus 15 provider segments / 210.04 seconds / 2.42% / accepted. Each lower-bar segment and 0.3-second gap uses retained sample counts, not an invented waveform. The slide explicitly distinguishes emitted audio from generation time and a complete recipe change from isolated segmentation causality. Source links, HTP qualifications and the `e7803e99` exact-WAV acceptance record are in Notes.

- [Supertonic 3 architecture](http://localhost:8766/docs/presentation/#slide-supertonic-architecture) — four-graph flow diagram with separate duration/text branches, compact Gaussian latent, repeated ConvNeXt/cross-attention estimation and waveform decoding. Written from the [architecture note](../wiki/models/supertonic-3.md) after checking the pinned release configuration; parameter counts and dimensions are not benchmark results. Rich implementation detail and research/release qualifications remain in speaker notes. **Open computation explorer** opens the [standalone Supertonic laboratory](../explainers/supertonic-3.html) in a new tab: actual arithmetic with explicitly untrained teaching weights, a release comparison and a local real-run capture importer. It is not official model execution or speech synthesis.

- [Gemma 4 E2B architecture](http://localhost:8766/docs/presentation/#slide-gemma-architecture) — text-token feedback, seven groups of four local and one full-attention layer, per-layer inputs, and fifteen KV producers feeding twenty later reusers. All 35 layers still execute. Written after the [Gemma architecture note](../wiki/models/gemma-4-e2b.md), with pinned configuration/implementation sources and model-size, K≠V, multimodal and deployment caveats in notes. No benchmark claims.

- [Inside Hexagon](http://localhost:8766/docs/presentation/#slide-7) — tensor/HMX, vector/HVX, scalar work and local memory. A conceptual explanation, not a die layout or measured instruction trace.
- [QNN backend map](http://localhost:8766/docs/presentation/#slide-8) — six hardware targets and four special-purpose backends. Every card opens a two-part execution and sample-use-case view.

## Extending the deck

Edit the same `index.html`. Each slide is a sibling `<section class="slide">` inside `.stage`, with a unique stable ID, heading ID, `data-title`, `.page`, and `<template class="speaker-notes">`.

- Slides without `data-branch` form the main path in DOM order.
- `data-branch="hardware"`, `data-branch="backends"`, `data-branch="supertonic"`, `data-branch="supertonic-length"`, `data-branch="gemma"` and `data-branch="supertonic-htp-steps"` assign slides to optional routes. Multiple slides with the same value form a multi-slide detour in DOM order. Main-story slides have no branch attribute.
- `data-branch-origin` and `data-branch-resume` define each optional route's boundaries. They can point to another optional slide: `supertonic-length` returns to `slide-supertonic-architecture` at both boundaries. The original `data-branch-point` and `data-resume-point` remain compatibility defaults for the hardware route.
- Buttons use `data-enter-branch="…"`, `data-back-story`, `data-resume-story="slide-id"`, or `data-go-slide="slide-id"` for a specific walkthrough step. The overview is generated from the same route definitions.
- To add another detour, add its `data-branch`, `data-branch-origin`, and `data-branch-resume` slides plus a choice button, then add a friendly label in the script's `labels` object.
- Put further experiment/result slides after the rejoin slide in main-route order. Keep optional slides marked as such; their physical DOM position does not insert them into the main path.
- Do not renumber IDs when inserting content. `.page` and the toolbar counter are derived from routes, not ID suffixes.

The `.slide-content` group preserves the original artwork proportions inside the fixed canvas. `.active`, `inert`, and `aria-hidden` control visibility and keyboard access. Destination headings receive focus after in-app jumps. Route history is session-local browser history, with no storage or network dependency.

## Browser checks

`browser-checks.js` is an async Playwright callback that verifies all 23 slides at six viewport sizes, including the five-step journey; overflow and overlap; aligned model collections, readable labels and intact architecture entries; the seven-slide main route ending at the HTP one-pager; its root slide7 numbering and continuation from Models & results; all eleven optional detail steps, visible controls, source link, step numbering, bidirectional return boundaries, deep links/history, SVG label bounds, report wording and recorded compile options, failure/quality/causality boundaries and exact-scale startup bars; both rejected audio hashes, decoded durations, no preload/autoplay, muted playback, mutual exclusion and pause-on-exit; both benchmark links opening real result tables in separate tabs; removed-slide recovery; all five original optional detours and their exits, including both model architecture entries and the nested long-input route, return boundaries, SVG labels, history/reload, fullscreen and offline behavior; exact sample-count chart proportions and the visible training-version/causality qualifications; Gemma's 4:1 layer tiles and 15/20 KV-sharing split; all ten backend detail dialogs; overview; keyboard/focus; direct links, refresh and browser history; the static GPU/NPU illustrations; notes; fullscreen; offline behavior; invalid hashes; and print visibility.

The HTP overview/walkthrough extension passed the full 23-slide/six-viewport browser suite on September 20, 2026. All twelve new slides were visually inspected at 1280×720 and 390×844. Moritz then requested the one-pager as root slide7 rather than an optional deployment detour; the final route and visible slide6 continuation are covered by the updated checks. The nested walkthrough has no external runtime or inference dependency; its two optional audio files are local copies only. Review was performed in-session because no extra agent spawning was authorized. The detector reported incumbent font/palette/copy warnings and template-heading warnings; notes render beneath the dialog's existing h2 title, so their h3 sections are intentional. No redesign of unrelated slides was made. Layout checks explicitly neutralize pointer hover before each viewport sweep so the pre-existing benchmark-link arrow animation does not create a spurious overflow report.

The later report-style revision also passed the full 23-slide/six-viewport suite, including muted playback of both exact recordings, byte hashes, decoded durations, no audio fetch during ordinary navigation, keyboard handling, mutual exclusion and pause-on-exit. All twelve HTP slides plus the audio-error state were visually reviewed at 1280×720 and 390×844. The build command's option/value pairs were independently compared with the original saved log. No new build, inference, phone action or listening verdict was produced.

The earlier long-input addition passed the full suite and an in-session visual review at 1280×720 and 390×844; no separate review agent was spawned. It preserves the existing deck palette, typography, fixed-stage geometry and computation-explorer link. The design detector's remaining warnings concern the incumbent palette/font, uppercase labels and existing notes hierarchy; this scoped addition does not redesign those surfaces. The new slide has no added eyebrow or shipping raster assets.

```bash
PW="$HOME/.pi/agent/skills/chrome-browser/scripts/pw"
"$PW" -s=project-slides open --browser=chrome --persistent http://127.0.0.1:8766/docs/presentation/
"$PW" -s=project-slides run-code "$(python3 -c 'from pathlib import Path; print(Path("docs/presentation/browser-checks.js").read_text())')"
"$PW" -s=project-slides close
```

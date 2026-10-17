# Building a NotebookLM-like podcast on my phone

Open `index.html`, or serve the repository root:

```sh
python3 -m http.server 8766 --bind 127.0.0.1
# http://127.0.0.1:8766/docs/qoralo-blog/
```

A short technical article about a source-to-podcast workflow with local phone inference. Qoralo is the experiment's app name, not the article's subject. The prototype generates a script and narrates it in one voice; this is not a reproduction of NotebookLM's conversational format or an established quality match.

## Three explanatory interactions

1. **Processor routes:** trace Gemma/GPU or Supertonic/NPU HTP through the phone. CPU orchestration stays visible. One-shot signal motion is illustrative, not measured timing.
2. **Runtime divergence:** step through inputs, first AR end-of-speech scores and outcomes, or play a bounded explanation. Desktop/original Android share inputs; the recovered Android route has a different fixed-cache graph. Two native players use the exact historical original/fixed Android CPU recordings already retained under `docs/android-benchmarks/media/`.
3. **Chapter assembly:** explore all 15 actual Supertonic CPU pieces using a keyboard-accessible range control. Bar extents use real sample counts, including fourteen actual 0.3-second gaps. Audio duration is not synthesis latency.

The narrative is **253 words**. The main article at the default outcome state is **561 visible words including all controls, figure labels, captions and explanations**. Deeper source details are collapsed.

`article.js` is a small local progressive enhancement. No external libraries, fonts, analytics or remote runtime requests. Nothing starts playing automatically. Audio files load only on request; starting one pauses the other. Reduced motion removes spatial effects. With JavaScript unavailable, all three figures retain meaningful static content and the native players/source disclosure still work. No audio was generated, trimmed, normalized or re-encoded for this page.

## Evidence and review

- Pocket sources: `experiments/0014-pocket-fp-onnx-qnn-htp/RESULTS.md` and `results/{android-alba-original-cpu,quality-recovery-listening}.json` beneath that experiment.
- Chapter sources: experiments 0036 and 0037. Earlier threshold failures and exact-file acceptance remain distinct.
- The 21.6129→0.497816-second four-session setup result is now an expandable detail, not the headline or an episode-latency claim.
- All inference is on the phone. Model preparation/context compilation happened on a computer. No final app UI-to-audio demonstration or new listening approval is implied.

`REVIEW.md` distinguishes the initial version's three peer reviews from Pi's later factual/copy review of this revised story. It does not claim the new copy received the old review passes unchanged.

## Browser checks

Serve the root, then use the Chrome skill wrapper:

```sh
PW="$HOME/.pi/agent/skills/chrome-browser/scripts/pw"
"$PW" -s=qoralo-story open http://127.0.0.1:8766/docs/qoralo-blog/
"$PW" -s=qoralo-story run-code "$(python3 -c 'from pathlib import Path; print(Path("docs/qoralo-blog/browser-checks.js").read_text())')"
"$PW" -s=qoralo-story close
```

Checks cover five widths × three diagnostic states, exact sample geometry, keyboard interaction, bounded playback/interruption, muted WAV decoding/playback, reduced motion, loaded-page offline interaction, print and script-failure fallback. Browser playback tests are not human listening verdicts. Static validation additionally checks retained source values and hashes.

Private draft only. No public article, Google integration or app release is announced.

# Chapter-opening candidate: saved phone evidence

**Code candidate committed; writing-quality acceptance is pending Moritz's review.**
This is the closeout of the existing round-2/3 work, not a new prompt experiment.
No phone access or model inference was used for this offline closeout. Start with
[round 3](evidence/bench-round3.md) and its [same-candidate repeat](evidence/bench-round3b.md).
The [old baseline](evidence/baseline.md) is only a before/after reference.

This is an application SCRIPT-generation exercise, **not** the canonical
[Android LLM performance campaign](../../protocols/android-llm-benchmark/README.md).
Do not publish these times as comparable model benchmarks, tokens/s, or audio durations.

## What is being preserved

Round 1 (`a0055548`) already supplied preceding chapter titles and the latest
chapter's bounded ending, asked the outline to assign fact ownership, discouraged
padding, and requested grounded, conversational narration.

The candidate adds the opening sentence of **each** preceding chapter, bounded to
120 characters per chapter. `GenerationCoordinator` extracts those sentences;
`ChapterRecap.opening` carries them; `singleChapterInstruction` quotes them and
derives the previous first words dynamically. The next chapter is asked to avoid
those run-ups and to begin on a concrete subject. There is no fixed phrase list.

Round 2 injected the actual opening sentences. Round 3 additionally named their
first words. The dirty runtime files reviewed at closeout are that round-3
candidate, unchanged; there is no new prompt variant here. The opening text is in
the **system instruction**; the existing request-body recap still carries titles
and the latest ending. No `NativeEngines.kt` or runtime configuration edit is part
of this closeout.

## What the saved outputs show

All four saved results have `outcome=complete` and `jobStatus=COMPLETE`:

| Saved run | Chapters | Narration characters | Largest/smallest chapter | Literal greeting starts | Duplicate first words | Mean vocabulary overlap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Round 1c | 4 | 3,721 | 1.85x | 0 | 2 | 0.134 |
| Round 2 | 5 | 4,357 | 1.86x | 0 | 2 | 0.093 |
| Round 3 | 5 | 4,318 | 1.61x | 0 | 0 | 0.130 |
| Round 3b (repeat) | 4 | 2,970 | 1.63x | 0 | 0 | 0.109 |

The old five-chapter transcript had 9,805 characters, a 2.24x length spread,
four literal greeting starts and three repeated first words. It predates round 1,
so baseline-to-round-3 differences are not attributable to opening injection alone.

Definitions: a greeting start is the narration beginning with `welcome`, `hello`,
`hi` or `greetings`, case-insensitively. Duplicate first words count repeats beyond
the first occurrence. Characters use Python `len(text)`, not bytes or token counts.
Vocabulary overlap is the mean pairwise Jaccard overlap of lowercase ASCII word
sets of at least four characters; it is a crude descriptive diagnostic, **not**
a semantic repetition, factuality, or quality score. Titles such as "Welcome to
Sandyford" are not counted as narration openings.

Recompute all four rows, without Android, Gradle, or a model:

```bash
python3 podcast-app/promptlab/summarize.py
(cd podcast-app/promptlab && python3 -m unittest -v test_summarize)
(cd podcast-app/promptlab && sha256sum -c SHA256SUMS)
```

`SHA256SUMS` binds the exact saved JSON, readable transcript copies, and scenario.
The JSON files are unmodified copies of the bench results. Markdown is a derived
reading view; the original source is the public Wikipedia extract in
[scenarios/sandyford.json](scenarios/sandyford.json), including its recorded URL,
revision and timestamp. It is input evidence, not independently verified history.
The result files record source character count, not a contemporaneous source hash.

### What these observations do not establish

- The two round-3 runs reproduce distinct first words, not overall writing-quality
  acceptance. Run 3 still repeats facts from its introductory overview in later
  chapters, pads the history chapter around one fact, and uses brochure-like
  language. Run 3b still has conversational run-ups. These remain for human review.
- Trivia/quiz coverage is not a closeout blocker: Moritz explicitly accepted its
  omission. No new word floor, trivia requirement, or duration policy was added.
- Same-candidate output varied from 5 to 4 chapters and from 4,318 to 2,970
  characters: **31.2% less text and 20% fewer chapters** in the repeat. Two samples
  do not establish a noise floor or confidence interval. The earlier statement
  that "anything below 30% is noise" was unsupported and is withdrawn.
- The route uses `topK=1`, `topP=1.0`, `temperature=1.0` and a fresh conversation
  per logical request. We observed different outputs despite that configuration;
  the cause was not measured. Previous text can propagate a divergence through
  later prompts, but does not explain the initial divergence. Neither token-level
  determinism nor thermal effects on output were proven.
- Round 3 elapsed 351,545 ms and round 3b 224,691 ms. Round 3 overlapped another
  session's large pack transfers and real GPU/HTP work; it is not a clean timing
  sample. No matched thermal/power measurements exist for the repeat either.
- This is one English, 4,818-character source and two round-3 transcripts, not a
  multilingual, maximum-20-chapter, long-context, or model-family evaluation.
- The bench stops at SCRIPT_DRAFT. It does not freeze, synthesize, listen to, or
  export audio. Its retained drafts are not evidence of an audio-generation failure.

## Reliability: keep the two failure stories separate

1. **Original chapter JSON failures: cause still unknown.** The two documented
   pre-fix cases failed at `JSON_PARSE` after prior chapters had completed. Raw
   failing responses were not captured. Malformed escaping, extra prose and
   output truncation remain hypotheses, not proven diagnoses. Runtime token
   counters were null, so `reachedOutputLimit` did not establish truncation. See
   [chapter JSON notes](../docs/chapter-json-failure-notes.md).
2. **Introduced grammar-rejection regression: mitigated separately.** The first
   constrained schema pinned identity with `const`; a chapter failed at `SEND`
   with `LiteRtLmJniException` after about 1.7 seconds. `debd4040` removed those
   schema constructs and added a once-only unconstrained re-send for a constrained
   `SEND` failure. The exact SDK message was not captured, so the specific refused
   construct is not conclusively identified. The fallback can also fail; it is
   not a guarantee that every episode will complete.
3. **Positive device coverage, not proof of eradication.** Session-inspected
   diagnostics for round 1c, round 2 and round 3 showed exactly 4, 5 and 5 chapter
   requests respectively, all complete, with no extra failed `SEND` requests.
   Those observations support acceptance of the revised grammar without fallback.
   The raw request metrics were not retained in this evidence bundle; the saved
   result JSON alone cannot prove which internal attempts ran. Round 3b adds a
   further COMPLETE result, not a separately audited retry trace.
4. **Still unexercised on device:** the automatic shorter-chapter retry ladder
   (300-word target, then 240/180-word ceilings) and the unconstrained `SEND`
   fallback. Host tests cover schema shape, retry policy, failure-phase selection
   and quiet retry progress, but there was no deliberate phone fault injection.
   The separate user-facing **Try again** path was observed completing an earlier
   five-chapter retry (`f0a5b452`, about 224 seconds); that does not exercise the
   automatic brevity ladder.
5. A diagnostic file for round 3 was last observed as `outcome=running` with null
   `wallMs`, despite its COMPLETE job/result. A later test-APK install could have
   interrupted final metrics persistence; that explanation is plausible, not
   proven. Use job/result status alongside metrics rather than interpreting a
   stale metrics record as a dead job.

## Source, APK, and host-test provenance

These runs used dirty shared-checkout source, not an isolated source commit.
Committing the reviewed candidate now makes it recoverable; it does **not**
retroactively bind the original APK to a clean commit or make a later rebuild
phone-tested. The saved outputs are phone evidence for the existing candidate,
not a qualification of nik's final offline build.

The last installed/pulled app verification after round 3b matched the retained
local app APK:

```text
app-debug.apk SHA-256
677f8d6fbe25d4ed8b438af1f55f198c0cf7cd135dceaf2a66fbe40151eec46d

retained test APK SHA-256 at offline closeout (no per-run test-APK hash receipt)
21293c4c80e237fdae7491b48b099ee6a081adf0b41930163f46a4679f207f4b

lib/arm64-v8a/libpodcast_runtime.so inside that app APK
2d9ece14775d86528cd658995ad09a770ddc3b083f2db7c0b91c19521d3b414a
```

The app dex contains `Those chapters opened with`, `Your first word must not be`
and `Begin on a concrete subject`. This confirms prompt marker presence, not a
reproducible source-to-binary proof. The native-library hash differs from the older
accepted `44a41cd4…c62c22` reference; that discrepancy remains open. NDK is pinned
at `28.1.13356709`; this closeout changes no native inputs.

Recorded route: SM-S918B / SM8550, Android 16, package
`dev.qoralo.podcast.internal`, Gemma 4 E2B INT4 QAT on LiteRT-LM 0.16.1 GPU,
8,192-token engine context and 4,096-token chapter output ceiling, no CPU fallback.
Gemma pack manifest pin:
`9fb627ef9a4eb0ed49056c32bc16f2846e6edf68dc8d854b02af90e24e4e96cd`.
These are application settings and prior observations, not a fresh device check.

Retained host XML from the round-3 source build reports **293 tests discovered,
280 executed, 13 skipped, zero failures/errors** (2026-09-20). Of these,
`GemmaChapterPromptTest` has 10 tests and `GenerationCoordinatorTest` has 9,
all executed successfully. Earlier "293 passed" wording included skips and was
imprecise. New coverage specifically checks bounded opening extraction, dynamic
opening/prefix injection and propagation of the spoken opening to the next chapter.
The instrumented bench was built and exercised on phone; its default behavior is
to skip unless explicitly opted in. At offline closeout, the five new stdlib Python
summary tests also pass (including saved-file checksum/scenario verification).
nik owns the serialized final host test/build
and immutable APK freeze after the source commit; record that result separately,
without relabeling it as a new phone qualification.

## Instrumentation harness contract (future authorized windows only)

`app/src/androidTest/java/dev/qoralo/podcast/e2e/PromptBenchTest.kt` queues one real
production SCRIPT job and polls the repository. It must **not** invoke the
coordinator directly: doing so races the production dispatcher. It creates its own
episode and intentionally retains its source and draft for inspection.

To invoke it, supply these arguments to the
`dev.qoralo.podcast.internal.test/androidx.test.runner.AndroidJUnitRunner` runner
via `am instrument --user 0 -w -r`:

| Argument | Required value |
| --- | --- |
| `class` | `dev.qoralo.podcast.e2e.PromptBenchTest` |
| `promptBench` | `script-v1` (otherwise the test is skipped) |
| `benchRun` | Unique `[a-z0-9-]{1,64}` identifier; existing directories are refused |
| `sourceFile` | Absolute UTF-8 file path readable by the **target app**, with the scenario source text |
| `sourceTitle` | Scenario source title (defaults to `Source`) |
| `instructions` | Exact scenario instructions, shell-quoted as **one** value |

Result: app-private `files/prompt-bench/<benchRun>/result.json`, retrievable via
personal-user `run-as` when authorized. Check `outcome` and `jobStatus`, not just
JUnit's `OK`: generation errors are recorded rather than asserted as test failures.
Polling stops after 900 seconds; it does not cancel the production job. A running
job may continue after a bench timeout. Setup errors before the harness's `try`
block can prevent any result from being written; preserve command/stderr evidence
as well. The harness is a development tool, not a release gate or hardened runner.

Before any future phone use: coordinate ownership, acquire the existing
`artifacts/locks/phone.lock`, and do not interrupt an existing generation. Use
Janek's updated install tooling; any app **or test** install must explicitly pass
`adb install -r -t --user 0` so the work profile stays clean. There are deliberately
no build, install, ADB, or inference side effects in `summarize.py`.

## Weekend/public-post boundary

Safe claim: the app generated complete drafts on the phone, and passing actual
preceding openings into later chapter prompts eliminated repeated first words in
two saved candidate runs. Do not claim accepted prose quality, solved hallucination,
a measured speaking duration, deterministic generation, a proven root cause for
the original JSON failures, a device-exercised automatic retry ladder, or a newly
phone-tested final offline APK. Moritz's writing-quality decision remains pending.

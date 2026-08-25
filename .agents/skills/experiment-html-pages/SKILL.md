---
name: experiment-html-pages
description: >-
  Create or update human-readable HTML pages for experiments in this repository.
  Use whenever the user asks for an experiment page, experiment HTML, research
  write-up, visual experiment summary, per-experiment progress page, or links
  from the project site to an experiment. Keep the page broad and narrative: a
  status header followed by exactly three primary sections—Experiment
  description, Progress, and Results.
---

# Experiment HTML pages

Create consistent, readable experiment pages without turning presentation requirements into new experiment gates.

## Core page structure

Every experiment page has one compact header and exactly three primary content sections:

1. **Experiment description**
2. **Progress**
3. **Results**

Do not replace these with a narrower checklist such as setup/provider/metrics/reproduction sections. Those details may appear inside the three broad sections when they help the story, but they are not mandatory subsections.

### Status header

Show:

- experiment number and title;
- current status: active, completed, blocked, stopped, or deferred;
- last committed update;
- a concise statement of the current position;
- links to the owning experiment directory and the benchmark overview.

Status is presentation, not an execution gate. Use the owning committed evidence; do not infer status from chat, ignored work files, agent presence, or a running process unless that state has been committed into the page source.

### Experiment description

Explain the experiment in a flexible narrative. Cover the motivation, question, approach, relevant setup, and scope to the degree useful for that experiment. Diagrams, tables, commands, graph lineage, model/runtime/device details, and links are optional tools rather than required fields.

A reader should understand what was attempted and why without reading raw JSON.

### Progress

Present durable committed progress, including meaningful attempts, discoveries, failures, changes of direction, blockers, completed milestones, the current position, and the next action when one exists.

Prefer a clear chronological narrative or timeline. Keep failures and abandoned routes visible when they explain the current direction. Do not import ephemeral Messenger updates or claim that an uncommitted local run is durable progress.

### Results

Explain what the experiment has actually established. For active work, report results so far without pretending the experiment is complete. Include metrics, provider proof, audio, listening status, limitations, missing evidence, and project consequences when relevant.

Keep these evidence classes distinct:

- technical execution;
- structurally valid audio;
- numerical/acoustic comparison;
- Moritz's exact-sample listening verdict.

A blocked experiment may have a useful result even with no benchmark or WAV. Render unavailable values honestly rather than filling the page with invented data.

## Source and output layout

Keep generated pages under:

```text
docs/experiments/<full-experiment-directory-name>/index.html
```

Use a Markdown presentation source beside the page:

```text
docs/experiments/<full-experiment-directory-name>/page.md
```

The page source is a human-facing synthesis, not new measurement evidence. It must link back to the owning committed experiment files and must not override them.

Use this minimal source shape:

```markdown
---
experiment: 0023-supertonic-qnn-precompiled-context-startup
status: active
summary: One-component context reload works; four-component work is next.
---

# Experiment 0023 — Supertonic QNN precompiled-context startup

## Experiment description

...

## Progress

...

## Results

...
```

The three headings are stable; content beneath them is deliberately free-form. Do not impose additional required headings.

Generate the HTML deterministically with a repository script rather than hand-maintaining generated markup. Extend an existing generator if it already owns experiment pages; otherwise create a small standard-library generator under `scripts/` that can rebuild one page, selected pages, or all discovered `page.md` sources.

## Evidence sources

Read the owning experiment's available committed files before writing:

- `README.md` for purpose and high-level state;
- `PLAN.md` for intended and unfinished work;
- `RESULTS.md` for durable conclusions;
- `REPRODUCING.md` for reconstruction context;
- committed `results/*.json` and protocol files for exact claims;
- `docs/android-benchmarks/registry.json` for normalized route metrics, listening status, and retained media.

Use Git history only to establish dates or understand transitions. Do not treat a commit message alone as measurement evidence.

When the experiment owner is actively editing its directory, do not edit that directory. Work only under `docs/experiments/` and shared page-generator paths, and coordinate before summarizing a result that has not yet been committed.

## Visual and navigation behavior

Use one shared responsive template for all experiment pages. Keep it readable as a local `file://` page and as a deployed static page.

Provide:

- top navigation among the three sections;
- clear status styling without relying on color alone;
- readable tables and code blocks on narrow screens;
- visible keyboard focus and semantic HTML;
- relative links that work from the generated page location;
- an audio player or direct listening link when a retained benchmark WAV exists;
- a link back to `docs/android-benchmarks/index.html`;
- source paths and source commit/hash metadata so staleness is visible.

Do not duplicate WAV files. Link to the retained dashboard media. Avoid external JavaScript, fonts, trackers, and network dependencies.

## Claim and writing discipline

Write for a technical reader who wants the story, not merely a data dump.

- Be direct about what happened.
- Preserve negative results and course corrections.
- Do not generalize a route result to a model family.
- Do not call host QNN execution physical phone HTP proof.
- Do not turn a missing metric into zero.
- Do not transfer a listening verdict to a new WAV or route.
- Do not add speculative constraints to the experiment while documenting it.
- Do not make page completion a prerequisite for running the experiment.

## Validation

At minimum, validate that:

- the HTML was regenerated from `page.md`;
- the page has one status header and exactly the three primary sections;
- all local links resolve or have an explicit unavailable explanation;
- audio links, when present, target committed retained media;
- displayed benchmark metrics match the normalized registry and owning result;
- active/stopped/completed wording matches committed evidence;
- generation is deterministic;
- `git diff --check` passes.

Keep generated-page commits scoped to the page sources, generated HTML, generator, and its tests. Do not modify owning experiment evidence merely to make a page look complete.

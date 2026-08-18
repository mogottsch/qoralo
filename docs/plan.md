# Current plan

## Goal

Find a text-to-speech model that can become the local voice of a future NotebookLM-like Android experience. It should sound pleasant and natural over sustained listening, with podcast-like delivery rather than merely intelligible speech.

A convincing two-speaker conversation would be useful, but it is not required. A strong narrator or persistent voices generated turn by turn can also meet the goal if the deployment runs well on a modern phone.

## Current phase: choose the next bounded question

Experiment [`0010`](../experiments/0010-supertonic-qnn-htp-feasibility/) is complete. It demonstrated a working fixed-transcript Supertonic hybrid with physical HTP evidence and `37.2%` lower warm generation latency. The same route required `26.965` seconds of session creation, reached `2.512×` CPU peak `ru_maxrss`, remained explicitly mixed rather than full HTP, and failed its prospective waveform gate. Moritz nevertheless reported that the randomized CPU and hybrid samples sounded exactly the same.

The current deployment decision is therefore conservative:

- keep Supertonic CPU as the supported Android reference;
- retain the experiment-0010 hybrid as a bounded research baseline;
- do not claim arbitrary-shape support, numerical acceptance, full-HTP success, or production adoption.

No new experiment or export route is approved yet. A possible source-model-first or full-HTP follow-up is only under discussion with Moritz. The next plan should be written only after that direction is explicitly chosen, with its own correctness, listening, latency, memory, and device gates.

Completed experiment details are in the experiment [`PLAN`](../experiments/0010-supertonic-qnn-htp-feasibility/PLAN.md), final [`HANDOFF`](../experiments/0010-supertonic-qnn-htp-feasibility/HANDOFF.md), and canonical [`E2E checkpoint`](../experiments/0010-supertonic-qnn-htp-feasibility/results/e2e-hybrid-cpu-checkpoint.json). The condensed outcome is in [`history.md`](history.md).

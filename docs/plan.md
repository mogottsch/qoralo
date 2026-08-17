# Current plan

## Goal

Find a text-to-speech model that can become the local voice of a future NotebookLM-like Android experience. It should sound pleasant and natural over sustained listening, with podcast-like delivery rather than merely intelligible speech.

A convincing two-speaker conversation would be useful, but it is not required. A strong narrator or persistent voices generated turn by turn can also meet the goal if the deployment runs well on a modern phone.

## Current phase: test QNN acceleration

Supertonic 3 is the current Android CPU default. Experiment [`0010`](../experiments/0010-supertonic-qnn-htp-feasibility/) tests whether selected Supertonic components can run correctly on the Galaxy S23 Ultra's Qualcomm HTP and improve complete synthesis enough to justify the extra complexity.

This phase must answer four questions:

1. Can the selected components run on physical HTP without hidden CPU fallback?
2. Do their outputs remain numerically and audibly correct?
3. Does acceleration improve complete Android synthesis rather than only an isolated control graph?
4. Is the benefit worth the startup, memory, packaging, transfer, and integration costs?

The phase can finish with either a useful CPU/HTP deployment or a reproducible decision to keep the simpler CPU path.

Detailed steps and gates are in the experiment [`PLAN`](../experiments/0010-supertonic-qnn-htp-feasibility/PLAN.md). The current technical resume point is in its [`HANDOFF`](../experiments/0010-supertonic-qnn-htp-feasibility/HANDOFF.md), and the canonical physical-phone evidence is in the [`phone checkpoint`](../experiments/0010-supertonic-qnn-htp-feasibility/results/phone-probe-checkpoint.json).

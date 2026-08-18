# Visual explainers

Durable, standalone HTML documents that explain architecture and runtime concepts used across experiments.

These files are canonical visual documents rather than generated mirrors of Markdown sources. Experiment-specific evidence and conclusions remain in the corresponding `experiments/NNNN-*` directory; temporary listening reports and raw artifacts remain under ignored `work/` directories.

- [Dynamic vs static quantization](supertonic-dynamic-vs-static-quantization.html) — how activation scales are selected, why dynamic quantization is convenient on CPU, and why static quantization is generally easier to compile for QNN HTP.
- [Why the dynamic-INT8 Supertonic vector estimator did not fully delegate to HTP](supertonic-dynamic-int8-qnn-blocker.html) — the exact experiment-0010 blocker, observed unsupported operators, partition behavior, and the distinction between INT8 hardware capability and graph/compiler compatibility.

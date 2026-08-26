# Noncanonical Android CPU reset diagnostic

This directory preserves the complete first 16-request Android CPU run. It must not be used as a canonical campaign or registry source.

The first request for each prompt tier performed genuine prefill. Repeated identical prompts after `RewindToStep(0)` reused LiteRT-LM prefix/KV state, producing microsecond prefill durations and impossible throughput values. The outputs and observations are retained because the benchmark protocol requires expensive failed or invalidated runs to survive analysis.

`output_sanity` is intentionally unchecked. The diagnostic demonstrates reset incompatibility; it does not establish a campaign distribution.

See the experiment README and `../host-reset-probes/` for the bounded reproduction and proposed fresh-Session adaptation. `SHA256SUMS` binds every retained file in this directory.

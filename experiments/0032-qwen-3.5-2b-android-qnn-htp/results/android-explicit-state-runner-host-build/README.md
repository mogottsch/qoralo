# Explicit-state Android runner host build

The experiment-specific runner cross-compiled successfully as a stripped Android arm64 API-30 executable. Its local-only binary is 3,444,472 bytes with SHA-256 `4b05bf24f6b55d349383dfdcfa54c0d968ea944a7b7ce6bb7971f348850aec58`.

A metadata-only host inspection bound the runner to the exact compiled PTE ABI: 51 inputs (token, mask, position, and 48 explicit states) and 49 outputs (logits and 48 next states). The runner performs greedy generation from int32 token IDs, inserts one-token full-attention K/V outputs into the next cache inputs, copies complete Gated DeltaNet recurrent/convolution states, and records QNN/ETDump and timing outputs.

This binary deliberately supports only one logical request per process. It is ready for the bounded physical viability gate, but it cannot satisfy the canonical campaign's loaded-route reuse requirement yet.

## Claim boundary

This is host cross-build and PTE metadata evidence only. Neither the runner nor PTE was staged or executed on Android. There is no physical QNN/HTP, generated-output, output-sanity, or performance claim. Phone use remains prohibited until Pi explicitly transfers priority.

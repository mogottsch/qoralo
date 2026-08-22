# Experiment 0022 plan

This is the durable implementation plan for comparing source-ONNX QNN startup with precompiled-context startup. The repository, not chat or ignored `.local` state, is authoritative.

## Current state

**Stopped at the first required design gate.** No implementation, context generation, phone staging, benchmark output, or WAV exists. Jere owns only this experiment path; other sessions own their experiments and dashboard paths.

The approved comparison was source ONNX QNN compilation (arm A) versus external precompiled QNN EPContext reload (arm B) for the exact stable-Softplus all-HTP Supertonic graph set. The comparison cannot proceed under the frozen scope because exact canonical-v2 semantics and exact T239 graph identity are jointly incompatible.

## Resolved compatibility gate — failed

The historical 0011 runner hard-codes T239/L238/729,746 samples. Canonical v2 is exactly 226 bytes, so `<en>` plus canonical v2 plus `</en>` is T235. The predeclared policy tested right-side positions 235–238 with filler ID `0`, semantic masks `1.0`, and padding masks `0.0` against the official dynamic-T235 source graphs under ORT 1.27.1 CPU.

The zero masks made all seven probed filler IDs byte-identical, so filler payload is masked. Sequence extent is not neutral:

- duration `max_abs = 0.2244882583618164` (limit `0.00001`);
- semantic text-embedding prefix `max_abs = 0.11101388931274414` (limit `0.0005`);
- semantic text-embedding prefix `RMSE = 0.006290534672319703` (limit `0.00001`);
- semantic text-embedding prefix cosine `0.9998871625637002` (minimum `0.999999`).

The exact frozen T239 duration/text graph identities reproduce the padded dynamic-T239 result within the specialization tolerances, confirming that they compute the changed T239 semantics rather than the canonical dynamic-T235 result. Therefore the mandatory action is to stop. Never use the legacy transcript, regenerate differently hashed graphs, generate contexts/output, or access the phone for 0022.

## Terminal checklist

1. Reserve only `experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/` during coordinated work. **Done.**
2. Run the contract tests and verify the working tree did not contain pre-existing 0022 changes. **Done.**
3. Reconstruct the exact graph identities and verify their SHA-256 values. **Done for the compatibility proof.**
4. Predeclare the padding policy, inputs, oracle and limits. **Done.**
5. Resolve the T235-to-T239 padding/mask gate. **Failed; proof committed as terminal evidence.**
6. EPContext inspection/generation, runner implementation, WAV generation and phone work. **Forbidden under this failed frozen scope.**
7. Report the scoped blocker commit and missing-reason evidence to Pi. **Required after commit.**

## Exact validation command

```bash
python3 -m unittest discover \
  -s experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/tests \
  -p 'test_*.py' -v \
&& git diff --check
```

## Exact proof reproduction commands

With Python containing ONNX 1.17.0, NumPy 1.26.4 and the pinned ORT 1.27.1 CPU runtime, reconstruct the ignored exact graph artifacts and rerun the proof:

```bash
EXP=experiments/0022-supertonic-canonical-v2-precompiled-qnn-context
"$EXP/tools/reconstruct_frozen_graphs.sh" \
  "$PYTHON" "$OFFICIAL_SUPERTONIC_SNAPSHOT/onnx" "$EXP/.local/reconstructed-frozen"
PYTHONPATH="$ORT_1_27_1_PYTHONPATH" "$PYTHON" \
  "$EXP/tools/prove_masked_padding_compatibility.py" \
  --source-onnx "$OFFICIAL_SUPERTONIC_SNAPSHOT/onnx" \
  --voice "$OFFICIAL_SUPERTONIC_SNAPSHOT/voice_styles/M1.json" \
  --frozen "$EXP/.local/reconstructed-frozen" \
  --transcript "$EXP/protocol/transcript.txt" \
  --policy "$EXP/protocol/padding-compatibility-policy.json" \
  --output "$EXP/results/t235-t239-masked-padding-compatibility.json"
```

Do not continue to EPContext work after reproducing the failed decision.

## Known portable hashes

- Canonical transcript: `424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67`.
- Duration graph: `8a1875ef0f6960ca16fc06814509b1c3258e8f50b04a5d590d3ab6db8c775016`.
- Text graph: `769fd1d257674e8624bdea941f7a903d9460051f9845b604cd2c2980f281a8c3`.
- Stable-Softplus vector graph: `f2318c54726a034dcc89aa9818a91f1c3db0e3067b9932c7c2dae65957897c7b` (source specialized vector `723316adfcff378c8ac72ee9db34cadf3b890e4167fa9a76f07398e0d4ff5b92`).
- Vocoder graph: `35b90eeae4a01d06f82dccc903a63d23c95eb2d9095ffa0d62f2cf151817c7c7`.
- Android ORT 1.27.1 library: `40bc591798287525f365e8ded4bbc40e0c4e9440737e876026ec09ba359ac041`.
- QAIRT baseline: `2.49.0.260730`; all QNN library hashes are in the machine contract.

## Claim boundaries

- “All HTP” covers the four neural sessions only; frontend, orchestration, trimming, and WAV encoding remain CPU work.
- Fallback must be disabled. A successful session/load alone is not provider or physical proof.
- Host source assignment and EPContext reload are gates, not physical-phone HTP evidence.
- QNN’s internal arithmetic precision is not established; “official FP32 source” must not become “FP32 on HTP.”
- Report context generation as offline cost and arm-B cold readiness separately.
- Do not transfer 0011 or 0021 listening acceptance. Every new byte-different WAV is `not_reviewed` until Moritz reviews its exact SHA-256.
- Do not edit `docs/android-benchmarks/`; Marius owns dashboard ingestion.

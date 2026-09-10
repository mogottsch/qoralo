# Paired position-1 QNN control and saved-vector analysis

**The single paired QNN call completed. Identical input values improve agreement, but both current-call discrepancy and prior-state effects remain.** This is one host QNN-x86 control, not a full trajectory, physical run, or accuracy result.

## Exact control

The QNN call used the reviewed QDQ-origin position-1 pack, token 8678, header `ec381857…43cd392`, logical input-values digest `4251bbce…c78e4`, exact PTE `7f30be3d…ff3fea`, and the separately accepted QDQ result `7137d83a…43519`. Both backend calls had unchanged input-value fingerprints and no detected input mutation.

The new QNN raw result is `8c41cda7641f3acf383416bc3b93d65e55adc179cb44696bd59d511940b7c285`; its 73-output bundle is `b771c49e1fc20e52293befa0d6dfe4b5b7b373a195bf8f781afce1f77dc51e00`.

Original runtime float32 metrics against the new same-pack QDQ reference:

- cosine **0.8879938126**, versus **0.6792200804** for the earlier own-state QNN position 1;
- maximum absolute error **6.222187**;
- mean absolute error **0.852588**;
- argmax **198 / 198**.

Worker wall time was 123.844 seconds, supervisor wall time 124.709 seconds, below the 300-second host limit. These include setup, checks and persistence, not Android or matched benchmark timing. The worker was reaped, its process group absent, and disk-backed scratch empty. No additional call, resume, full replay or phone operation followed.

## Vector decomposition, not scalar attribution percentages

Saved-data analysis inspected all **73 outputs from each of three bundles**: new QDQ control, new QNN control, and original own-state QNN position 1. All 219 tensors were finite. It did not execute a model.

Let `Q_own`, `Q_control`, `D_control`, and `D_historical` denote the four retained logit vectors. The stored float32 terms are:

| Term | Definition | L2 magnitude |
|---|---|---:|
| Current-call discrepancy | `Q_control - D_control` | 539.396 |
| Prior-state effect through QNN | `Q_own - Q_control` | 719.275 |
| Historical reference shift | `D_control - D_historical` | **0** |
| Original observed difference | `Q_own - D_historical` | 866.342 |

The first three **vectors** sum to the fourth, with a retained float32 rounding residual of at most `4.76837e-7`; independent float64 recomputation has zero residual. **L2 norms and cosines are not additive and are not percentages of causal attribution.** Original vectors were not modified.

The float64 saved-data logit comparisons are 0.887989275 for same-input current-call agreement, 0.760262283 for own-QNN versus controlled-QNN, and 0.679215150 for own-QNN versus new QDQ. Small differences from the original float32 metrics are reporting precision, not new model outputs. Both sets are retained separately.

## Earliest saved-output discrepancies and layer curve

`analysis/all73-comparison.json` retains current-call, prior-state-effect and total comparisons for every output. These are saved output endpoints, not an operation-by-operation trace.

- Residual current-call difference is visible already at **layer 0**: recurrent-state cosine 0.999935, convolution-state cosine 0.999948, hidden-output cosine 0.997409.
- Prior-state effect is also nonzero at layer 0; hidden-output cosine between the two QNN results is 0.999306.
- Same-input hidden agreement declines through later layers: layer 17 **0.956764**, layer 20 **0.895558**, layer 22 **0.856769**, layer 23 **0.885774**.
- The original own-state QNN versus new QDQ layer-23 hidden cosine is about **0.80769**. Earlier hidden discrepancies also propagate into later layers within each call; these endpoints do not isolate a particular operator.

A narrower saved-data observation is in `analysis/layer0-conv-slots.json`. For layer-0 convolution-history output slot 2, channel 6053:

| Value | Observation |
|---|---:|
| Identical common input (previous history slot 3) | 23.7218952179 |
| QDQ output | 22.1315498352 |
| QNN output | 23.7218971252 |

QDQ changes this retained-history value while QNN nearly preserves it. The newly projected current-token slot has maximum QDQ/QNN difference only 0.0040884. **This is not proof of QNN copy corruption, not proof the slot causes hidden/logit drift, and not evidence of which route is closer to FP32.** It motivates a source/encoding audit of Q/DQ/cast/clamp boundaries, not a root-cause conclusion.

## Retention and reproduction

Git contains all three complete 73-output bundles, the historical QDQ logit vector, raw difference vectors, all-output analysis, input/result bindings, logs and resource data. Six compressed recoveries were checked; each raw/compressed size/hash is in `compression-manifest.json`. Existing raw originals, the input pack and protected 174-position reference archives remain unchanged.

The analyzer only reads saved output tensors:

```bash
E=experiments/0032-qwen-3.5-2b-android-qnn-htp
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  artifacts/venv-executorch-1.2/bin/python "$E/tools/analyze_position1_pair.py" \
  --qnn-result "$E/.local/diagnosis/controlled-p1-qnn-call-20260910T122428Z/run/control/result.json" \
  --own-prefix-directory "$E/results/host-qnn-trajectory-prefix-000-003-20260910" \
  --output-dir "$E/.local/<fresh-saved-data-analysis>"
```

It never loads or executes a model/PTE. The original local retrieval paths are bound in the analysis metadata; all paired tensor bytes are also recoverable from the committed compressed copies if the original paths must be restored during migration.

## Next gate and limits

After review, inspect saved graph metadata/source and selective small encoding constants around the layer-0 history slot, including whether 22.131550 is a representable-range limit. Do not load/execute the whole model for that audit. Distinguish QDQ reference range behavior from backend optimization.

No individual operator root cause, full trajectory fidelity, FP32 accuracy, generated text, physical HTP result, campaign readiness or registry claim is established. Physical baseline `23ac8abd…d2c506` remains unchanged. No new runtime call is authorized.

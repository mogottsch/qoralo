# Experiment 0010 handoff — paused after physical HTP control

## Current status

Work is paused after a successful tiny-graph HTP proof and a fail-closed vocoder investigation. The canonical checkpoint is [`results/phone-probe-checkpoint.json`](results/phone-probe-checkpoint.json). [`results/host-checkpoint.json`](results/host-checkpoint.json) is the earlier pre-phone snapshot and is retained as history.

**What is proven:** a six-node QDQ add graph executed on the Galaxy S23 Ultra's SM8550 HTP with CPU fallback disabled. Its detailed QNN profile contains RPC finalize/execute events, QNN accelerator timings and cycles, and four HVX threads.

**What is not proven:** the Supertonic vocoder has not executed on HTP. No vocoder output, audio, component latency, speedup, vector-estimator result, or end-to-end accelerated synthesis exists.

The phone stage `/data/local/tmp/vibevoice-qnn-0010` was removed after evidence capture. The phone lock is not held. Do not run a new phone command without reacquiring `artifacts/locks/phone.lock` and reconfirming Moritz's availability.

## Physical-phone result

Device identity was reconfirmed as Samsung `SM-S918B`, Qualcomm `SM8550`, arm64, Android 16/API 36.

The first tiny session failed closed because the staged QAIRT 2.49 set omitted `libQnnHtpPrepare.so`. QAIRT loads that library dynamically, so it does not appear as an ELF `NEEDED` dependency of `libQnnHtp.so`. After staging the exact library (SHA-256 `db0a4c4811fe0947f6f237978190cbaf4cea8fa8bd607ea14fda67d375403c9e`), the no-fallback tiny control passed:

- session creation: `0.413961` s;
- measured inference: `0.00196151` s;
- profile SHA-256: `e4cca7e966c99696d6ee836448587fdec7241b3e5a883c933f10500ec09a0e90`;
- profile evidence: RPC finalize/execute, QNN accelerator finalize/execute, accelerator cycles, four HVX threads.

The fixed-shape released-vocoder derivative then crashed during **session creation only** with exit `139`/`SIGSEGV`. No inference ran. The Android tombstone reports a null-pointer read at address `0xb0` in `libonnxruntime.so`.

## Crash root cause

The phone failure reproduced the x86 HTP-emulator failure, so the emulator-only hypothesis is rejected. Host GDB localized the top frame and call path to:

```text
onnxruntime::QDQ::PadNodeGroupSelector::Check
onnxruntime::QDQ::NodeGroupSelector::GetQDQSelection
onnxruntime::QDQ::SelectorManager::GetQDQSelections
onnxruntime::QDQ::GetAllNodeUnits
onnxruntime::QNNExecutionProvider::GetCapability
```

ORT 1.27.1 permits `dq_nodes.size() == 0` in `PadNodeGroupSelector::Check` and then dereferences `dq_nodes[0]`. Microsoft fixed this exact bug upstream in commit `a08e17aab393a922d619736a4150cfe43bc7f8ec`, PR #28733.

The minimal source backport is tracked at [`patches/onnxruntime-a08e17-pad-empty-dq.patch`](patches/onnxruntime-a08e17-pad-empty-dq.patch). It changes only the production guard from `num_dq_inputs > 2` to `num_dq_inputs < 1 || num_dq_inputs > 2`. The experiment's ignored local ORT source already has this patch applied.

## Patched host result

The patched host runtime no longer crashes. It instead reaches a useful fail-closed capability result:

| Model | QNN-supported nodes | Partitions | Remaining unsupported nodes | Result |
|---|---:|---:|---|---|
| fixed released-vocoder derivative | 338 / 354 | 9 | 8 `Erf` + 8 weight-only `DequantizeLinear` | rejected, fallback disabled |
| fixed + eight weight-only DQ tails folded | 338 / 346 | 9 | 8 `Erf` | rejected, fallback disabled |

The combined folded-and-fixed derivative is SHA-256 `ee6760340a128e6f1f397ccee84c1fdd50165524d4ac7de76d522dec679fff14`. Under the same patched ORT 1.27.1 CPU build and session options, its output is bit-identical to the fixed released-vocoder derivative. That is derivative-equivalence evidence only, not an HTP numerical pass.

Graph optimization levels `0`, `1`, `2`, and `99` were tested. Levels 1/2/99 retain exactly the same eight unsupported `Erf` nodes; level 0 delegates substantially less. Implicit ORT CPU fallback remains disallowed and was not used to manufacture a passing result.

The eight remaining `Erf` nodes are inside standard decomposed GELU patterns. QNN has a native GELU operation, but ORT's QNN fusion does not recognize these QDQ-wrapped forms after DQ duplication.

## Consequential decision for the next session

Review this choice with Moritz before changing the graph:

1. **Recommended:** create a separately labeled derivative that replaces only the eight proven standard `Div → Erf → Add → Mul → Mul` GELU decompositions with explicit `com.microsoft.Gelu` nodes. Record every matched/replaced node, source/output hashes, and CPU comparison. Freeze the formal numerical gate before inspecting any HTP output.
2. **Alternative:** construct an explicit CPU/HTP split around the eight GELUs. This is more integration work but can preserve the original operators. Merely enabling ORT CPU fallback is not an acceptable substitute because it would invalidate the fail-closed delegation proof.

Do not start the vector estimator until a vocoder session runs with fallback disabled, produces finite output, has detailed physical-HTP evidence, and passes frozen numerical criteria.

## Retained ignored state — do not delete

All large, proprietary, generated, or raw artifacts remain under ignored experiment paths:

- `.local/onnxruntime-v1.27.1-source/`
  - exact ORT `df2ba1cf8108aa63627cf4cdf8f807880b938616` source;
  - the tracked `a08e17` backport is currently applied as an ignored working-tree diff.
- `.local/ort-v1.27.1-qnn-2.49.0-host-patched-a08e17/`
  - reusable patched x86_64 QNN build;
  - patched `libonnxruntime.so.1.27.1` SHA-256: `bc9df5a7df1b5d9de4d87adcaa4cc864bbde0f790e80d48e00ce0e4253a2ae11`.
- `.local/ort-v1.27.1-qnn-2.49.0-android-arm64/`
  - reusable successful Android build from before the backport;
  - its `libonnxruntime.so` is **unpatched** and must not be used for another vocoder attempt;
  - after the host/model gate passes, incrementally rebuild/relink it against the already-patched local source rather than deleting it.
- `work/`
  - fixtures, derivatives, staged-file manifests, phone profiles/logs, Android runner, host runs, GDB evidence, and optimization sweep.

The retained host build was moved out of `/tmp`; no critical build now depends on a temporary path. SDKs remain outside the repository at their side-by-side installed locations. `/home/moritz/opt/qairt/current` was not changed.

A typical incremental Android relink, only after the next host gate passes, should mount the retained source at `/src`, the retained Android tree at `/build`, QAIRT 2.49 read-only at `/opt/qairt`, and the Android SDK read-only at `/opt/android-sdk`, then build the narrow targets rather than cleaning the tree. The Android QNN integration is static, so rebuild `onnxruntime` and any runner/perf-test executable being staged.

## Key ignored evidence

Hashes and bounded conclusions are in the canonical JSON. Important raw files include:

- `work/device/qnn-smoke/smoke-qnn-with-prepare.csv` — accepted physical HTP profile;
- `work/device/qnn-smoke/logcat-crash.txt` — Android native tombstone excerpt;
- `work/device/qnn-smoke/logcat-main-system.txt` — full relevant Android/QNN initialization trail;
- `work/device/qnn-smoke/host-gdb-vocoder.txt` — symbolized host crash stack;
- `work/ort-qnn-2.49-patched-a08e17/vocoder-l238-host-htp/run.stderr.log` — patched exact fixed graph support report;
- `work/ort-qnn-2.49-patched-a08e17/vocoder-folded-weight-only-fixed-l238-host-htp/run.stderr.log` — patched folded/fixed support report;
- `work/derived/vocoder-fold-weight-only-qdq-fixed-l238/same-runtime-cpu-equivalence.json` — bit-identical derivative comparison;
- `work/device/qnn-smoke/device-cleanup.txt` — scoped phone cleanup proof.

## Safety and publication

- Experiment 0008 remains the immutable CPU baseline.
- No experiment 0009 source or result was modified.
- No root, system tuning, firmware change, or system-library mutation occurred.
- No Qualcomm binary, header, license text, profile, model, tensor, APK, or audio is tracked.
- Any future Qualcomm login, terms, consent, or export gate still requires Moritz.
- The raw phone evidence may contain platform/runtime details and remains ignored locally.

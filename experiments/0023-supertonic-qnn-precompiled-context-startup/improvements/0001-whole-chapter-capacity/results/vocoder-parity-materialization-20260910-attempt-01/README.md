# One two-site batch1-parity vocoder derivative — structurally ready

Pi's conditional implementation/materialization release became active after Nik accepted the exact `49281cb` source design. **One** real derivative was written, from the immutable failed-vocoder source SHA `539f8ef7850292b3b5add1b9b29012e6bff86c13caebad06ef802cec261df792`. No SDK/ORT constructor, model forward, context generation, phone or pack change occurred.

## Actual artifact and allowed delta

LOCAL-ONLY `vocoder-parity.onnx`: **101,455,228B**, SHA:

```text
5c13592238dc5af15b29a923213a9c87d780296c3dca9026257de2870dc8ad07
```

Exact path in `local-artifact.json`; actual bytes remain under `.local/vocoder-parity-materialization-20260910/attempt-01/data/` with `PRESERVE.md`. Preserve the actual bytes, not only hashes. Originals and both failed constructor attempts remain protected.

-401→415 nodes: only the original `convnext.1` and`.4` depthwise Convs are replaced, each by8 nodes.
- Each replacement: even/odd axis2 Slice(step2) of the existing padded tensor → two batch1 dilation1/kernel7/group512 Convs sharing original weight/bias → Unsqueeze → Concat on the parity-last axis → Reshape to the original output name/order.
- All103 original initializer serialized bytes/order remain identical. Seven shared **non-learned INT64 control initializers** are appended; no coefficient expansion/re-encoding.
- Existing causal `Pad(mode=edge)` nodes and their complete control DAGs are unchanged; the bounded integer DAG evaluates to `[0,0,12,0,0,0]` at both sites.
- Every non-target node byte/order, model/graph metadata, original ValueInfo and public I/O byte is unchanged. Fourteen new ValueInfo records describe only the added plumbing.

`attempt-01/data/structural-delta.json` contains exhaustive source/derived node hashes and all original/appended initializer identities. A normalized-protobuf comparison checks all other graph/model fields, not just selected names.

## Shape proof and scope

The helper strictly infers each small parity subgraph with independently bound metadata inputs `[1,512,12300]`, weight `[512,1,7]`, bias `[512]` **without weight values**. Both branch inputs/outputs infer `[1,512,6150]`→`[1,512,6144]`; parity-last stacking/interleaving restores `[1,512,12288]`. The full real derivative passes ONNX full checker validation.

This does not pretend the original whole graph's symbolic intermediate annotations became independently concrete. Those original annotations are preserved. Embedded model initializer protobuf bytes were parsed/copied structurally under the materialization release; learned values were not evaluated. Only tiny integer Pad controls were decoded.

Helper SHA `4a79e134fc6e3eeb3f6e6223aff661e249cf1c89056f6c27ef1fac3101713fb7`. **Seven focused structural/gate tests passed** in0.082s, including tampering, source preservation, exact output-consumer names, batch1/dilation1 shape proof, real Pad-builder algebra, collision/repeat refusal and pre-load approval denial.

The single materialization took0.962957s (external guard1.202115s), peak process `ru_maxrss`990,180KiB, within180s/8GiB/4CPU/thread bounds. Test/materialization PIDs1946523/1946974 were reaped; groups absent; owned disk scratch empty. No automatic retry.

## Next constructor: NOT APPROVED

A source/output-only rebind of the accepted verbose/cgroup worker is prepared at `protocol/vocoder-parity-constructor.request.NOT_APPROVED.json`, SHA:

```text
8557ca10877c15718f75fbb6a60b8bd98ba809aec22cf000823432f06daec001
```

Worker `ae827a55…fd6b61`, launcher `13f02b43…e9d27`, runtime/image/provider/IO/logging/cgroup/bounds remain unchanged. Only the new source identity and fresh phase/output/release/container/scratch paths differ. `constructor-plan.json` is plan-only, not execution. The runtime phase and actual approval do not exist.

Nik/Pi must review this real derivative and request before a separately released constructor. Backend support, actual tiling, absence of re-fusion, native FP16 fidelity, physical execution and whole-chapter quality remain unproven. There are still only the prior duration/text/vector contexts; this source derivative is not a fourth context.

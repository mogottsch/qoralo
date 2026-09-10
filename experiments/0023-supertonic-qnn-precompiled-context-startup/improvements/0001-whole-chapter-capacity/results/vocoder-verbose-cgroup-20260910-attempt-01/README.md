# Unchanged-vocoder v2 diagnostic — target tiling/VTCM failure localized

One separately released unchanged-source constructor, **zero Run**, failed again at QNN finalization. Worker body2.157880s, outer launcher3.100215s, process peak492,208KiB. There is no completed-constructor timing, actual-session I/O receipt, descriptor/binary or post-constructor pin-verification receipt. Missing observations remain missing; this did not create a fourth context.

The exact request `e03e62ccb6b3406484fe0eb89f056771a736c4d77265da513da413648c5191a5`, source/worker/launcher snapshots and approved release are retained. Source/shape/ORT/QNN/image/provider/8GiB/4CPU/520+20/zero-Run options are unchanged from the first failure; only verbose logging, cgroup observability and fresh output identity differ.

## Actual own-container telemetry

Both global/session verbose settings took effect (`stderr.log:1,98–99`), including the real QNN callback bridge. Container PID7 reports `0::/` in its private cgroup namespace, mounted at `/sys/fs/cgroup`. Capture/write/scope errors are null.

| Cgroup field | Before | After |
|---|---:|---:|
| memory.current |27,926,528|427,311,104|
| memory.peak |27,926,528|427,532,288|
| memory.max |8,589,934,592|8,589,934,592|
| memory.events max/oom/oom_kill/oom_group_kill |all0|all0|

Values are bytes. The own-container peak stayed below the8GiB limit with no recorded limit-hit/OOM events. This is not a global-host-RAM measurement and says nothing by itself about accelerator VTCM or target-session VA.

## Concrete compiler chain

Complete verbose stderr is3,695,160B, SHA `338ec3e2133a3b6cc299dbece3388517859126b6f1eecce4d8ca04925c2d14dc`. Exact bounded passages and source-name counts are in `compiler-chain.json`:

1. Line42141: compiler VTCM total8,388,608B.
2. Lines42209/42211 and42345/42347: depthwise-dilation operators lack a valid time splitting rule; default time12288; reported minimum tile12,920,320B, shape `[1,1,12288,32]`.
3. Line42931 onward: generated `q::DilatedConvLayer_s1.fp16` operators are not sufficiently tiled for TCM; each reported requirement12,605,440B exceeds that VTCM capacity.
4. Lines43006–43068 map16 generated errors each to `/decoder/convnext.1/dwconv/net/Conv_token_16_2` and `/decoder/convnext.4/dwconv/net/Conv_token_49_2`.
5. TCM scan/migration fails → Fatal Optimize17 → graphFinalize1002.

This localizes the failure to **two backend depthwise-dilated convolution tiling/VTCM sites**, not the8GiB host cgroup or dense attention. The compiler's requirement is not a standalone source-tensor byte count, and32 generated messages must not be summed as measured live memory. It is distinct from documented target32-bit session VA limits. Source lowering/proposals remain separate, source-only work; no operator or RAM change was tried here.

Nik independently audited exact bindings, logging, source mappings, cgroup scope, missing observations and cleanup; report at `/home/moritz/.cache/nik-podcast-reviews/vocoder-verbose-cgroup-20260910-attempt-01/`. No review-triggered rerun occurred.

## Preservation and cleanup

Raw logs/receipts/telemetry were copied before interpretation, and originals remain under `.local/constructor-vocoder-verbose-cgroup-attempt-01/` with `PRESERVE.md`. Artifact list is empty. The first failed attempt and all successful duration/text/vector contexts are protected.

Host worker PID1933002 reaped; PID/group/container absent; disk scratch empty. Cleanup retains the reviewed non-atomic unique-name/label boundary. Release consumed. No retry, other-component constructor, model forward, phone/pack change or push. Whole-long-speech readiness remains blocked pending a separately reviewed source-level remedy.

# Unchanged-vocoder diagnostic candidate v2 — NOT APPROVED

This is source/mock readiness for **one separately released diagnostic constructor**, not an execution. The failed vocoder attempt in `b652a2c` remains immutable. Same L2048 source graph, I/O hash, ORT1.27.1/QAIRT2.49.0.260730,13 runtime pins, image, providers,8GiB/4CPU/network-off/520s+20s bounds and zero Run. No operator/shape/RAM change or new materialization.

## Minimal diagnostic changes

- Set actual ORT global default severity0 and verbosity1 **before construction**, plus session severity0/verbosity1.
- The inspected QNN bridge (`../vocoder-diagnostic-readiness-20260910/logging-source.json`) emits callbacks through the global default VERBOSE logger while choosing QNN log level from the session/backend logger. Both severity settings are needed; no invented provider option is used.
- Capture `/proc/self/cgroup`, its exact cgroup2 mountinfo line/resolved directory and raw `memory.current`, `memory.peak`, `memory.max`, `memory.events` before constructor and after exception/session close. This is the worker's own cgroup scope, not a substituted host root. Missing/unreadable fields remain null with errors.
- Cgroup capture/persistence is optional diagnostics: failures are caught and embedded in the primary result so they cannot mask the original QNN constructor failure. Before capture is also inside result-preserving handling. Relative, parent-traversal and escaped membership/mount paths are rejected.
- SIGKILL/native process death can prevent a final receipt; absence must remain null with a reason, not an invented after-snapshot. The existing launcher/cleanup lifecycle is unchanged, including its disclosed non-atomic name/label boundary.

## Exact candidate

Request: `protocol/vocoder-verbose-cgroup-v2.request.NOT_APPROVED.json`

```text
e03e62ccb6b3406484fe0eb89f056771a736c4d77265da513da413648c5191a5
```

Worker `ae827a55cbc7056141964b8fdcd8bede9ad6fe607861cfa14730d97356fd6b61`; launcher `13f02b432561ff7aa3092b7a82580ec7c5a9297492f2e809f4b3b1bcc1fe9d27`.

The new runtime phase is `.local/constructor-vocoder-verbose-cgroup-attempt-01/`; the separately bound approval file does not exist. `plan.json` is plan-only output, not a Docker/native execution. Source diffs against the consumed batch worker/launcher are retained here.

## Review and validation

Nik identified two issues in the initial unapproved draft: unprotected optional cgroup write could mask the primary exception, and unsafe scope paths needed rejection. Both are fixed in v2. The original draft request `15807e…49c02c`, source snapshot and44-test receipt remain in the preceding readiness folder; they were never executed.

**46 tests passed in0.360s**, including seven diagnostic mock methods: real API-call ordering via fake ORT; own namespace-root and full-hierarchy cgroup resolution; unavailable/ambiguous metrics; unsafe path rejection; exact diagnostic release binding; and original constructor failure preserved through before/after capture/write failures. No runtime import, model constructor, graph load or Docker call was used in these tests. Test PID1930927 reaped/group absent; scratch empty.

Await Nik's direct minimal-delta review and Pi's separate release. Verbose diagnostics may change logging overhead; they do not justify a blind RAM increase or establish the failed allocation. Source graph has no MatMul/Softmax, so no dense-attention/tiling diagnosis is claimed. Documented v73 target address-space limits remain constraints under investigation, not this failure's proven cause.

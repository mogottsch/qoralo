# Precision-path candidate: frozen short stage and guarded lifecycle

Host preparation only. No ADB, physical inference or new output is claimed here.
The accepted canonical campaign and previous FP16-interface exact-long negative
remain unchanged. This package is not a registry/campaign result.

## Bound artifacts

- Paired precision-path context: 1,186,381,824 bytes,
  SHA-256 `27e19e32ef479dfb39b53e6530cd25105c3c8e9ccf9fa4b9e9af4b5d770fabdd`;
  context and official metadata evidence in `ef0bbb0`.
- Fresh private stage: `.local/frozen-stages/value-path-short-20260911T115043Z-01`.
- External frozen-manifest SHA-256:
  `206ca960a69f915f81cb5c61dde5684259f8fbee8a37e14ef8b8bbf9fcafc78b`.
- 21 independently copied payloads, 4,003,806,609 bytes. Runner is read-only
  executable (0555); all other inputs are read-only. No baseline inode is linked
  or chmodded. Model/context, tokenizer, LUT and SDK/runtime binaries stay private.
- Exact accepted short prompt and single-BOS 170-token identity. One fresh dialog,
  one max16 compatibility request, not the canonical max2048 campaign. The exact
  1929-token long input is present but there is no long script or request here.

`prepare_value_precision_stage.py` changes four count-checked bindings in the
hash-pinned preparer: context evidence path/digest, context digest and provenance
commit. Its inverse test reconstructs the original preparer byte-for-byte.
Preparation copied and hashed all payloads, then independently read-verified the
complete resulting stage. The saved verification receipt is authoritative for
stage verification; the service's independent exit code was not captured before
unit collection and stays null. The completion watcher is not service exit proof.

## Guarded collection

`phone_value_precision_short.py` uses the preserved phone lifecycle with eight
fixed substitutions: stage/digest, new output/remote namespaces, scope labels,
an audit receipt and the already tested direct-nohup launch. Shell control and
watchdog source are unchanged. Inverse substitution reproduces the original
controller exactly. Original sources and consumed slots are not overwritten.

The default CLI is plan-only. Execution requires an actual Pi-granted one-use
slot, a fresh run ID, the external stage digest and `--execute`. The complete
`artifacts/locks/phone.lock` lease covers all ADB identity, staging, inference,
raw pull and cleanup calls. Its FD is non-inheritable/CLOEXEC and child processes
use `close_fds=True`. An existing busy lock causes zero ADB calls and no slot
consumption. A slot is consumed before the first ADB call and cannot be retried.

The 1800-second process deadline and independent remote watchdog remain. Any
signal rechecks the exact PID/starttime/executable/NUL-argv identity; this is a
sequential check then numeric-PID signal, **not atomic/pidfd-bound**. Unknown
identity prevents signals and destructive cleanup. Partial evidence is retained;
remote roots are removed only after verified process absence and complete raw
pull. Optional telemetry/parser gaps cannot erase raw results. No app install,
app-data access, hidden fallback, altered sampling, extra warmup or output repair.

## Validation and next boundary

All 190 host tests passed, including the inherited adversarial fake-ADB lifecycle
suite against the new scope. No real ADB or model inference occurred in these
tests. Saved plan CLI and workload checksum checks returned zero. Raw test/plan
stdout, stderr, actual child exits, source materializations and preparation
receipts are retained here.

A coordinated short phone slot is the next step. If compatible, a separately
frozen exact-long/max2048 request will test the saved repetition failure. Neither
DLC precision gates, compiled interfaces nor this stage proves finalized kernel
arithmetic, numerical fidelity, CPU-free execution, quality or speed improvement.

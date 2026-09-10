# Gate B exact-long readiness — preparation only

Gate A (`81f4ede`) is accepted as bounded short-query compatibility. This is a **separate frozen stage and lifecycle scope**, not permission to run it. The first-short stage, controller/shell sources, evidence and completed campaign are unchanged.

## Frozen long inputs

Private stage (relative to this track):

```text
.local/frozen-stages/stage-freeze-long-20260910T163842Z-01
```

Manifest SHA-256:

```text
047dd808fe49656105934a9afed521fc3c4acdd0c6d278d0ed5685a98a0b846e
```

The 18 payload files total 4,003,852,753 bytes. They are independent read-only copies, with runner0555 and private directories0700. The context is unchanged `1d80d016…ca9f8`; config remains byte-identical `f8008e04…7eba`; tokenizer, LUTs, libraries and BOS suppression are unchanged.

The only query script is `exact-long.script`: one new dialog, optional setup profile, explicit max2048, exact `prompts/long.txt`, raw `evidence/long-output.txt`, optional long profile, then release. No preceding short query, prefix reuse, retained KV state, padding, custom stop, retry or second request is added.

Exact inputs are inherited by byte identity from the reviewed stage:

- workload SHA `092840fb…aad8`;
- rendered long SHA `450b519d…f260` (10,589 bytes);
- token-ID SHA `3b5c04fe…2b64` (1,929 expected tokens);
- BOS config `-1`, with the existing single BOS in the rendered input;
- context4096; 1,929 + 2,048 = 3,977 fits without truncation.

This preparation copied/hashed files only. It did not retokenize, load or run the model, use ADB, or recompile anything.

## Narrow lifecycle reuse

`tools/phone_return_long.py` loads only the exact hash-pinned reviewed short controller and shell templates (`62b8a16`). It materializes isolated modules with an enumerated, count-checked substitution list:

- fixed long stage name/digest;
- fixed `exact-long.script` argument and long/max2048 scope labels;
- separate host long-output root;
- an explicit adaptation provenance receipt;
- the narrowly changed launch redirections below.

An inverse-substitution regression recovers the exact original controller text; the short files/module are not edited or mutated. The two shell-template script-name substitutions happen before any run-specific remote path is rendered. This avoids accidental replacement inside user-supplied run IDs.

All authorization, shared one-use slot ledger, full lock, descriptor isolation, identity/hash/mode checks, deadline, raw-first/optional-metric, scoped PID/starttime/executable/argv checks and retained-root failure behavior remain from the reviewed lifecycle. Numeric-PID signalling is still **not atomic/pidfd-bound**; the disclosed final check-to-signal race remains. Unknown identity still refuses signal/destructive cleanup.

The adapter pins accepted Gate A's result hash before materialization. That provenance check is not a new phone-slot grant. The old short-stage digest cannot authorize this long controller. No arbitrary prompt, script, model, token-cap or backend override is exposed.

## Launch-pipe correction and bounded host regression

Saved Gate A command-file mtimes suggest roughly4.08s between local client PID recording and launch-command completion, versus about3.66s for Genie create+query. These filesystem timestamps are only a clue, not a dedicated timing measurement, proved cause or benchmark.

The reviewed short launch used a background `cd && nohup ...` AND-list with redirections on the child command. Such framing can leave an intermediary shell retaining the transport pipe. The long adapter removes that possible path: direct `nohup`, absolute script/stdout/stderr paths and `/dev/null` stdin, with no outer `cd`/AND-list. The wrapper already sets its own working directory.

A focused **host-only** regression launches a short owned shell dummy blocked on a FIFO. The transport shell closes its own streams and waits for its child. The test observes pipe EOF while the dummy is still blocked/unfinished, then releases the FIFO; the shell waits/reaps its child and Python waits/reaps that shell. This proves the direct command's child-pipe property on the host. It does not establish actual Android/ADB detachment or runtime behavior. No ADB/model is used by this test.

## Predeclared comparison after a separately approved run

Use the existing repetition implementation in `tools/analyze_long_collapse.py` without changing thresholds after seeing output:

1. 4/8/16-token n-gram counts and unique ratios;
2. first128-token window with four-gram unique ratio <=0.25;
3. longest exact periodic suffix with period1–64 and at least two cycles;
4. actual output bytes/hash/count/stop observations and narrow sanity.

The retained QNN baseline's five long outputs are identical (`f0e9d284…97b2d`), with the declared rolling criterion at generated-token index83 and period9 suffix from index478 covering1,570 tokens. Compare one complete new long diagnostic against those retained outputs; do not rerun or replace the baseline campaign and do not demand identical candidate output.

Raw Genie rates retain the unspecified first-token-inclusion caveat. Normalized decode remains null unless an authoritative definition is established. One diagnostic is not a warm performance distribution or speed acceptance. Text/repetition changes do not identify internal logit/state divergence or establish general quality.

Keep full raw battery dumps private and hash-bound; publish only explicitly labeled core-field extracts. Do not include learned sleep/charging history in public evidence. Raw query/provider/output/profile/cleanup evidence stays exact; incomplete pulls retain the remote root.

## Commands and remaining gates

Safe plan-only command:

```bash
python3 experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/tools/phone_return_long.py
```

Only after this exact stage/lifecycle is reviewed and Pi grants a fresh long slot:

```bash
python3 experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/tools/phone_return_long.py \
  --execute \
  --reviewed-stage-digest 047dd808fe49656105934a9afed521fc3c4acdd0c6d278d0ed5685a98a0b846e \
  --pi-slot "$PI_GRANTED_LONG_SLOT_ID" \
  --run-id "$NEW_EXACT_LONG_RUN_ID"
```

Unset values are rejected. This example grants no permission. Keep app work highest priority, one new run/output root, independent1800s host/remote deadlines and existing cleanup budgets. No native call, model load, physical ADB, long output or repetition result has occurred in this preparation. Git pushes/publication remain held under the separate privacy coordination.

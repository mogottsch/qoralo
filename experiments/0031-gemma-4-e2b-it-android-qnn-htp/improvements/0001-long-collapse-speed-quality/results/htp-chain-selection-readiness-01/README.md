# Only the two missing chain cases, under one continuous lease

The isolated Power case is already a valid physical result and is **not requested again**. This controller selects only `normalization_chain` and `normalization_exposed`, using the same immutable stage/context/inputs/grids.

## Selection and count contract

The actual qnn-net-run CLI supports `__` in an input-list position to skip a graph. Each selected case runs in its **own native process** with one input-list record and `--num_inferences 1`:

- chain: `__,<chain-input-list>,__`;
- exposed chain: `__,__,<exposed-input-list>`.

A bounded actual-host-runner fixture loaded three authored one-addition CPU graphs and separately selected only the middle and last graph. Each invocation reported **one inference**, wrote only its selected output, and produced the expected distinct value (11 and 101). No first-graph output appeared. This validates scheduling/selection, not HTP arithmetic or memory behavior; CPU client buffers were used for that host-only test. Host and Android stripped binaries are not claimed source-identical.

## Lease and ownership design

One parent controller acquires **one phone lease and one fresh Pi slot**, stages the unchanged bundle once and keeps the lease through both phases, raw collection, postflight and cleanup.

Each phase has separate immutable PID/starttime records, launch/watchdog scripts, logs, limits readback and output directory. Both Python and shell identity guards bind the exact selected-case argv. First-phase process absence is established before the second launch. Job/playback/RPC admission is repeated before each case. A first-phase failure, unresolved ownership or newly active user job prevents the second invocation without retrying anything.

The parent performs one final raw pull before deleting the owned root and runs the actual independent postflight hook while still holding the lease. Partial pulls retain the remote root. All PID signalling remains sequentially checked, not pidfd-atomic.

## Bounds and claim limits

- **90 seconds maximum per native process**, at most 180 seconds native time across the two selected cases; staging, owned cleanup and pull have separate existing finite deadlines.
- Same **AS12 GiB**, actual **8 MiB FSIZE** readback, shared-buffer mode and 16 MiB polled evidence-directory budget.
- Expected raw outputs: **1,180,416 bytes**.
- No Power execution, new graph/context, learned weights, LLM/full-reference run, CPU fallback, guessed pole policy or automatic retry.

The exposed variant still changes fusion/materialization opportunities. The unexposed variant does not prove a particular fusion. Actual selected graph counts and raw codes must be checked after the future window.

Pi authorized one fresh two-case phone window after this freeze/tests and fresh identity/lease/job checks admit; no additional user-approval loop is needed. Preparation itself performs no phone access.

The first host-only phase-module materialization failed because its dynamically compiled dataclass module was not registered in `sys.modules`; that failure and source snapshot are retained. The correction preceded all device use. Fake-ADB tests exercise the actual two-phase lifecycle, shared lease, first/second failures, between-case job blocking, partial pull, postflight failure and unknown-identity signal refusal.

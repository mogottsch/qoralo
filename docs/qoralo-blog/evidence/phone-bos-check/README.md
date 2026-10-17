# Phone check of the old Pocket runner's first-step input

A bounded CPU-only run on the Galaxy S23 Ultra (SM-S918B, SM8550, Android 16, serial pinned). It tests whether the old runner's dangling start-of-sequence buffer matters on the phone. No QNN/HTP, no app changes, no new listening verdicts.

## What was run

The retained source `experiments/0014-pocket-fp-onnx-qnn-htp/tools/pocket_alba_cpu_runner.cc` was rebuilt with NDK 27.0.12077973 against the same ONNX Runtime 1.27.1 Android library as the original build. `runner_variants.cc` / `runner_variants.patch` add two compile-time switches and nothing else:

| Binary | Change |
|---|---|
| `runner_orig` | none (unmodified retained source) |
| `runner_dump` | `-DDUMP_BOS`: at step 0, copy the 32 words behind the BOS tensor to stderr immediately before `Run()` (no heap allocation in the dump) |
| `runner_fixed` | `-DFIX_LIFETIME`: the `bos` vector is declared outside the `if` so it outlives `Run()` |
| `runner_fixed_dump` | both |

Each ran twice (8 planned runs, one window, no retries) with identical inputs: the 0024 same-size reconstruction of the four graphs, the retained Alba cache (`eb6e2d71…`) and the retained noise prefix (`c130a822…`), temperature 0.3, 134-frame cap. Hashes are in `stage.sha256` and `FROZEN.sha256`. The remote stage was verified against `stage.sha256` before any run.

## Results (`results.json`, built by `summarize.py` from `raw/`)

| Run | BOS words before `Run()` | First stop score | Stop frame | Frames | WAV |
|---|---|---:|---:|---:|---|
| `runner_orig-1` | not printed | −10.2709 | none | 134 | `cdf77f6e…` = retained failure recording, byte-identical |
| `runner_orig-2` | not printed | −4.37185 | none | 134 | `d4297712…` (different) |
| `runner_dump-1`, `-2` | 32 × `00000000` | −10.2709 | none | 134 | `cdf77f6e…`, byte-identical |
| `runner_fixed-1`, `-2` | not printed | −9.8847 | 53 | 56 | `465ac270…` |
| `runner_fixed_dump-1`, `-2` | 32 × `7fc00000` (NaN) | −9.8847 | 53 | 56 | `465ac270…` |

The `465ac270…` audio correlates 0.999996 with the accepted fixed-cache recording `e0638f35…`. No one has listened to it. Only `runner_orig-2.wav` and `runner_fixed-1.wav` are stored here; the other WAVs are byte-identical to those or to the retained failure recording (`wav-sha256.txt`).

## What this supports, and what it does not

Supported by this rebuilt test: the original lifetime hands the model zeros instead of NaNs (observed in the instrumented build), the original source on the phone reproduces the retained failure recording byte for byte, and keeping the buffer alive alone brings back the correct stop at frame 53.

Not shown: the retained old executable (`a11685f5…`) was not retained, so nothing is bound to it. The graph is the reconstruction (`ce8d8701…`), not the lost original (`021288bd…`), although it reproduced the failing recording exactly. The dump build may perturb allocation. The unmodified build's BOS bytes were never printed. `runner_orig-2` gave a different wrong answer, so the failure is nondeterministic undefined behavior, and its backing contents are unknown. No explanation is offered for why this allocator returned zeros.

## Protocol record (honest, including defects)

- Slot: scheduled by Pi; `phone.lock` held; serial `R5CW81PR8SY`; no app was stopped or changed.
- Pi reviewed the first controller and required fixes before any run: one 300 s window with a 40 s native bound per run (host wait 75 s), owned-process identity, explicit cleanup states, and a fresh no-user-work/headroom/thermal preflight. `run_bos_phone.sh` is the controller as run (`FROZEN.sha256`).
- Two read-only preflight-only invocations preceded the window to validate the parsers (nothing pushed). They found that the audio check matched unrelated log lines (fixed to count real `AudioPlaybackConfiguration` entries) and that `MemAvailable` was 1.99 GiB. **The memory gate was lowered from the 3 GiB used by the repo's heavy QNN scripts to 1.5 GiB**, about twice the 712 MB peak this CPU runner recorded in the retained run. That is a protocol change, not a pass against the original 3 GiB gate.
- Preflight in the window passed: load 1.2, battery 29 °C, thermal status 0, 17 audio players listed with none started, launcher in the foreground, Qoralo not running (`preflight.txt`).
- **Controller cleanup was incomplete.** Its terminate step timed out (host limit 30 s, rc 124). The device-side `/proc/*/cwd` scan was too slow. The controller correctly reported `cleanup_incomplete_owned_process_not_terminated` and kept the stage (`cleanup-proof.txt`, `terminate.out`). All eight runs had already exited normally (rc 0).
- **Manual cleanup, performed and verified separately** under `phone.lock` (`manual-cleanup-*.txt`): all eight recorded PIDs were gone by start identity, no process had its cwd in the stage, exactly the stage directory was removed, the device answered `ABSENT`, and no other `pocket-bos-check` directory existed. The raw results had already been pulled. Do not reuse `ctl/terminate_owned.sh` as is; replace the full `/proc` scan with the recorded PIDs plus a single `ls -l /proc/*/cwd`.
- The raw `dumpsys` captures used by preflight are not committed because they list unrelated apps on the phone.

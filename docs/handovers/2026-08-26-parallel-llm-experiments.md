# 2026-08-26 — Parallel Android LLM experiments

Persistent cross-device handover for the parallel Gemma, Qwen, and LFM experiment sessions completed on 2026-08-25. This records the state as observed during transfer; later experiment documents and commits supersede it where they differ.

## Source conversations reviewed

The parallel Pi sessions from 2026-08-25 were read before preparing this handover:

- Pi/orchestrator: `01a038be-5f10-7672-b2a1-ab87467dafc4`
- Jere / Gemma 0025: `01a038bd-f2fa-7bbd-9aef-8f38b0b808b3`
- Ben / Qwen 0027: `01a039db-e7d5-719e-ad59-b0fddf211aee`
- Jens / LFM 0029: `01a039db-dd3c-7487-b4b8-5e708a0dd8cc`

Their local JSONL files are not needed on the next workstation; the actionable state and expensive ignored evidence are preserved below and in the owning experiment directories.

## Repository and machine state at handover

- Branch: `main`.
- The last completed pre-handover commit was `c4cb384` (`Record Qwen3.5 2B Android CPU smoke`).
- No benchmark, build, ADB, llama.cpp, or LiteRT-LM process was still running when checked.
- Neither `artifacts/locks/phone.lock` nor `artifacts/locks/heavy-ram.lock` had an owner.
- The authorized phone `R5CW81PR8SY` was disconnected, so the interrupted Qwen phone stage could not be inspected or cleaned from this workstation.
- No worktree or side branch exists; all sessions edited the same `main` checkout.
- The shared Android LLM registry/dashboard and experiment HTML have not been updated for 0025, 0027, or 0029. The publisher was waiting for a complete committed campaign handoff.

## 0025 — Gemma 4 E2B IT

Committed before this handover:

- `eab21d2`: locked official CPU/GPU route contract;
- `a2201e3`: first Android CPU smoke;
- `f474f61`: persistence-first campaign runner.

Current result:

- The Android CPU short smoke is valid and committed.
- The first full 16-request CPU run completed but is **not canonical**. `RewindToStep(0)` retained reusable prefix/KV state, so repeated prompts showed microsecond prefill and impossible throughput.
- The complete invalidated Android run is now retained under `experiments/0025-gemma-4-e2b-it-android/results/android-cpu-reset-diagnostic/`.
- Bounded host probes under `results/host-reset-probes/` prove:
  - one rewound Session reuses prefix/KV on request two;
  - one loaded Engine with a freshly created Session per request performs genuine full prefill;
  - the observed Session recreation cost was about 41 microseconds.
- Probe support in `tools/litert_lm_canonical_runner.cc` and diagnostic finalization support are preserved in Git.

Decision required before another phone campaign:

> Approve or reject the experiment deviation “one loaded Engine, fresh Session per logical request.”

It preserves loaded-model reuse and full conversation/KV isolation but conflicts with the shared contract's literal `session_reused: true` / same-session wording. Do not silently treat it as canonical. If approved, amend the experiment/shared contract explicitly, recreate the Session before every logical request, record recreation separately, add tests, then rerun CPU from scratch before GPU work.

Ignored local state that is intentionally not transferred: about 6.0 GB (`.litertlm` artifacts, LiteRT-LM checkout/build, Android stage). Recreate it from the pinned URLs/revisions and hashes in the committed contract/README.

## 0027 — Qwen3.5-2B

Committed before this handover:

- `033c33d`: locked llama.cpp/Q4_K_M CPU route;
- `c4cb384`: valid Android CPU short smoke.

Current result:

- Smoke: setup 2.247 s; 174 input tokens; TTFT 2.315 s; prefill 76.12 tok/s; decode 16.41 tok/s; total 6.163 s; peak sampled PSS 2.804 GB; output SHA-256 `0f0d70ee…086c8`.
- The first full campaign was interrupted after eight complete requests: first short + five repeated short + two medium. `medium-03` was in progress.
- Every complete request passed the early reset proof: successful slot erase, `cache_n == 0`, full prompt count, and positive prompt time.
- The pulled partial result, outputs, events, server log, and memory samples are retained under `experiments/0027-qwen-3.5-2b-android/results/android-cpu-campaign-interrupted-20260825/`.
- It is **not canonical** and must not be resumed or published. Rerun the full campaign from the start.

First action with the phone connected:

1. acquire `artifacts/locks/phone.lock`;
2. inspect only `/data/local/tmp/vibevoice-0027-qwen-3.5-2b-android` and the PID/cmdline claimed by its `server.pid`, if present;
3. kill/remove only that scoped experiment process/stage;
4. verify the path is absent;
5. release the lock, then use a fresh lock hold for a complete rerun.

Ignored local state intentionally not transferred: about 5.5 GB (llama.cpp checkout/build, 1.28 GB model, Android stage). Recreate it from the committed contract, hashes, and tools. Experiment 0028 (Qwen3.5-4B) has not started; begin it only after 0027's route completes canonically.

## 0029 — LFM2.5-2.6B

Current result:

- Official ungated `LiquidAI/LFM2.5-2.6B-GGUF@84022ce711b28455e8c4fc364ce68c00cf995875` Q4_K_M artifact selected.
- Artifact: 1,674,455,040 bytes, SHA-256 `02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed`.
- Runtime: llama.cpp build 7446 / commit `5c0d18881e0e9794c96b2602736b758bac9d9388`.
- A bounded host smoke passed with `llama-completion`, 171 prompt tokens, 41.65 prefill tok/s, 23.39 decode timed-runs/s, and output SHA-256 `3f703023…f52`.
- Two earlier `llama-cli` attempts are invalid; one entered automatic conversation and produced a 9.2 GiB runaway stdout before it was terminated and deleted.
- The Android NDK build was interrupted during compilation and produced no executable. No ADB/phone work occurred.
- The route README, continuation plan, renderer, exact pinned license, host smoke, and tests are now retained under `experiments/0029-lfm2.5-2.6b-android/`.

Continue from `experiments/0029-lfm2.5-2.6b-android/PLAN.md`. Finish the full tokenizer/template/quantization contract and bind a completed Android binary before phone use. Ignored local state intentionally not transferred: about 1.8 GB, dominated by the 1.6 GB model and source/build directories.

## Other queued work

- 0026 Gemma 4 E4B IT: selected but not started.
- 0028 Qwen3.5-4B: selected but not started.
- No Android GPU TTS result exists. A bounded Supertonic Android GPU portability experiment was recommended, but it was not started and should not interrupt the LLM campaigns.
- Publishing order remains: commit complete owning evidence first, then send a structured handoff for independent registry/dashboard/HTML publication. Do not publish host smokes or interrupted/reset diagnostics as Android rows.

## Suggested resume order

1. Pull `main`, read this file and the three owning experiment READMEs.
2. Connect the authorized phone and perform the scoped 0027 stale-stage check/cleanup.
3. Rerun the complete 0027 CPU campaign from scratch; validate and commit it.
4. Decide the 0025 fresh-Session protocol deviation, then rerun CPU if approved.
5. Recreate 0029 artifacts, finish its contract and Android build, then run its first bounded phone smoke.
6. Continue 0025 GPU, 0028, and 0026 only after their prerequisite routes are stable.
7. Add a newer dated handover if work pauses again; retain this file as historical context.

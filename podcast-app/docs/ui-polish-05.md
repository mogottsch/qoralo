# Final PNG/tree pairing and bounded transition subsets

Small debug-driver/test-only follow-up to `2820168`. Production UI and its regression sources are unchanged from polish-04. No form WIP, native/model changes or physical work is included. Polish-04 emulator execution was held before any run; its frozen artifacts remain untouched.

- `$frame-initial.png` is retained immutably before tree work, for partial/failure evidence.
- Current-frame content is validated against existing production landmarks/state in fresh, owned, cache-refreshed windows.
- A distinct candidate PNG is then captured, bracketed by frame/token/PID/fresh-window ownership checks. Only after both checks pass is it published as `$frame.png`.
- Metadata binds the final PNG and tree hashes, actual installed source APK hash, before/after identity snapshots and capture phase. Initial or failed candidate images cannot be presented as a validated final pair. Failed candidate PNGs remain available even when post-capture ownership fails.
- `galleryFrame=library,sources` permits a genuine within-run transition smoke. Selections are nonempty, unique, whitelist-only and capped at15; mixed `all` is rejected. IME/hold remain single-frame-only.
- Supervisor bounds:100s single/IME,40s×N for multi-frame subsets,600s full15-frame matrix. The content wait remains10s, with512-node/5s extraction budgets and previously established acknowledgement/window bounds.

Four additional deterministic tests cover subset validation, ownership checks around a final image, wrong-content rejection and retention without publication after a post-image ownership failure. Host success is not an emulator pairing verdict.

Nik alone should verify the exact revised candidate, then run a subset transition smoke and a separate dialog/IME smoke. Inspect finalPair hashes against actual files and ownership before/after. Continue to the full matrix and pending polish-04 layout tests only if those checks pass. All previous raw reports, failed trees and APKs remain immutable.

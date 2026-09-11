# Nik — exact installed-pair reuse delta

Reviewed candidate72f74545e341cb7fe4632aecc9be79ded36c0ce965b20ae9c18b863ff916a5a9/source9bf2c97327b2d04bf9148d41222f5d5759a3f435; controlleraaa8b3540464b73b5f6432a45db4f0d1b64b9e924308b47c9c9f366804446e86.

Both APKs remain byte-identical to the reviewed c34cf10 diagnostic appff32bb…aaadb/testd4cbfe…c5e17. All145 compiled-source file pins are identical and all16 candidate evidence bindings match. There is no app, prompt, model, build-config or native delta. Candidate priorInstalled now correctly names the actually installed ff32/d4cb tuple.

Only the host install loop changes: after verifying the exact currently installed hashes, install an APK only if it differs from the target, record reuse/install explicitly, then retain the existing installed-target and stable pre-instrument checks. Four host fixtures executed the actual parsed AST branch and confirm0/1/1/2 installs for identical/app-only/test-only/both-changed pairs. No Device or model call was made by Nik.

All other identity, ownership, privacy, preservation and independent-cleanup code is unchanged. The next run is the separately preserved invalid-source-notes user case, not another repeat of the successful five-chapter case. It retains the existing source-note guard and prompt to distinguish empty from oversized returned notes using private evidence. No speculative prompt fix, no automatic output repair and no extra approval gate. Outcome review follows the actual saved run.

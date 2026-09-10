# Frozen manifest-only FastRPC declaration candidate

**Host preparation complete; independent review and a fresh physical slot required.** No device action or inference was performed for this candidate.

- Overlay/tool source: `cc473f8904439cffd57d72cc5eda4910689c6232`.
- Base diagnostic source: `3fd75c06481bcc709d45da5c4933347f348e9079`.
- Effective source tree: `0b9d10dc5f47cbe97c4c363f74cc97a239e21120` (only main-manifest declaration differs from frozen3fd).
- Directory: `podcast-app/.local/duration-native-library-ready/cc473f8/`.
- App SHA: `78488901d63032b87d2d575c6bec5b7f578b3a7ee38c92e3c633ed943dcb96ab`.
- Test SHA, unchanged baseline: `120420d6925283ccf44478b58aef29a12e4575bbf6f1027df9a3d98e83cf2c8c`.
- Candidate SHA: `ac4d325f7f5b66ca5ff144590b991775d616c18bfb9ac56065f3c66c6af89fb2`.
- Approved host closure, unchanged: `3ad4c644a7733d1f1feeb7bbbe83532cc0be0f727f32f59dda00c951dd6e202d`.

The only manifest semantic change is optional `uses-native-library` for `libcdsprpc.so`, confirmed both by the complete parsed-tree comparison and Android aapt2's dump (exactly three added declaration lines). `required=false` permits installation without the library; the diagnostic still reports failed loading and CPU fallback remains disabled. No native library is added to the APK: the declaration requests the device-advertised public library through Android's supported mechanism.

`entry-proof.json` shows every non-manifest ZIP payload unchanged, including all DEX, resources and nine native libraries. App/test share the same original signing certificate; signatures and the unchanged trusted-runtime ELF/hash verifier pass. Only manifest bytes and unavoidable ZIP compression/alignment/signing metadata change. Baseline test APK is reused byte-for-byte. No Gradle, Java/Kotlin/C++, model compilation or native preparation was needed. The source worktree and normal Gradle outputs were not replaced.

Three focused manifest tests passed before packaging. Their exact baseline8112-byte manifest fixture is committed with the tool source. `retained-manifest.json` binds17 original proof/log files (179,028 bytes); APKs and intermediate packages remain outside Git.

See [`../../docs/duration-native-library-candidate.md`](../../docs/duration-native-library-candidate.md) for source/build method, installation semantics and claim limits. Any future separately authorized diagnostic remains one constructor, zero Run/Gemma/other-context/TTS/capacity/retries with unchanged contract/options/context/payload. A load success would not prove neural execution.

# One-declaration duration-load candidate

**Source/build-only scope. No new phone attempt is authorized here.** Baseline physical evidence is committed in `8c08c9f`; its verbose loader error precedes the original INVALID_CONFIG and downstream disabled-fallback rejection.

## Sole semantic change

Apply `config/diagnostics/duration-fastrpc-native-library.xml` to the **frozen3fd75c0 diagnostic**, not the current polished app:

```xml
<uses-native-library android:name="libcdsprpc.so" android:required="false" />
```

The saved S23 vendor public-library list advertises `libcdsprpc.so`. Android's [platform documentation](https://developer.android.com/guide/topics/manifest/uses-native-library-element) states that apps targeting API31+ must explicitly request non-NDK vendor libraries through this declaration. It asks Android to expose an advertised public library, not to bypass namespace policy.

`required=false` permits installation when the library is absent, matching the baseline's optional OpenCL/vndksupport declaration style. The diagnostic already handles failed loads by producing an explicit terminal failure. This does **not** permit a CPU fallback or pretend QNN is available: session creation still must fail if its dependency is unavailable. Choosing optional installation does not change the mandatory runtime route.

## Controlled build and verification

`tools/prepare_duration_native_library.py`:

1. Pins the baseline candidate/APK/test hashes and the committed overlay/tool inputs.
2. Constructs the effective source from3fd75c0 plus exactly one declaration in the main manifest using an isolated Git index; no app worktree replacement.
3. Reuses the exact frozen app APK. `duration_manifest_overlay.py` inserts a declaration cloned from the existing optional OpenCL entry in binary XML and appends one UTF-16 string. It fails on unexpected formats and proves that removing the added node yields the complete original manifest semantic tree.
4. Preserves every ZIP entry payload except `AndroidManifest.xml`; zipaligns and re-signs with the same debug certificate. The exact frozen instrumentation APK is reused.
5. Checks the final manifest with Android's aapt2, verifies app/test signatures, compares every DEX/resource/native/other ZIP payload against baseline, and runs the unchanged trusted-runtime ELF/hash verifier. All nine native payloads, including the bridge, must remain exact.

ZIP compression/alignment metadata, binary-manifest offsets and APK signing blocks necessarily change. These are disclosed rather than claiming byte-identical APK packaging. No Java/Kotlin/C++/model compilation, runtime preparation, service/contract/options change, ADSP/LD adjustment, or ADB is part of this procedure. No system `libcdsprpc.so` is copied into the APK.

Focused tests use the exact8112-byte baseline binary-manifest fixture, hash `293221fb7189018607b2424216d84c811c0c00d4f935c3d05d876ada31b5efd8`; they check the sole optional declaration, duplicate rejection and fail-closed handling of unsupported/truncated input.

A new source/manifest/app/test/candidate identity is required, while the approved host guard remains `3ad4c644a7733d1f1feeb7bbbe83532cc0be0f727f32f59dda00c951dd6e202d`. Nik must review exact outputs and Pi must grant a new phone slot before the same bounded **one-constructor, zero-Run/Gemma/other-context/TTS/capacity/retry** diagnostic may execute. A successful future load would still not prove neural execution or whole-chapter feasibility.

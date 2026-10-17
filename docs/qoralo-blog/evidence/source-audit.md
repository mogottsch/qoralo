# Pocket input-lifetime source audit

This is a later source audit, not a new model result or a replay of the historical recording. Original experiment results and rejected/accepted WAVs are unchanged.

## Definite source defect

Retained file: `experiments/0014-pocket-fp-onnx-qnn-htp/tools/pocket_alba_cpu_runner.cc`.

SHA-256: `a2c833b2ac8fc85f676b1aff8203cc1ada452be87699a65543033136897c45cd`.

Its `TV()` helper calls the user-buffer overload:

```cpp
Ort::Value::CreateTensor<T>(mi, v.data(), v.size(), s.data(), s.size());
```

That creates an OrtValue wrapping the caller's storage, not an owning copy. In the first autoregressive step, the runner creates `bos` inside an if-block, wraps it, leaves the block, then calls `Run(main, inputs)` outside the block. The vector has already been destroyed. The tensor's backing pointer dangles before inference consumes it.

The pinned ORT C API header explicitly says: “p_data is owned by caller. ReleaseValue won't release p_data.” See `onnxruntime_c_api.h`, `CreateTensorWithDataAsOrtValue`; the C++ `MemoryInfo` overload forwards directly to it. The allocator-taking overload is a separate API that owns its allocated storage.

This is not the local shape vector `s`: ORT copies shape metadata. The defect is the lifetime of `bos.data()`.

I also read every other `TV()` call in the runner (token ids, empty sequence, text embedding, `current`, `step_noise`, `s0`/`t1`, decoder `chunk`). Each backing vector is declared in a scope that is still alive when the `Run()` that consumes it executes. `bos` is the only one that is not.

## Bounded host verification

`bos-lifetime-repro.cc` uses actual ORT tensor creation and mirrors the relevant helper/block scope. It creates **no Ort::Session, loads no model, runs no inference and accesses no phone**. It consumes the tensor's pointer directly under AddressSanitizer.

- Original block-scoped storage: AddressSanitizer reports **heap-use-after-free** at the read, with allocation/deallocation in the same source scope.
- Control retaining the vector outside the block: exits 0; all 32 NaN start markers remain valid through consumption.
- Host runtime: existing ORT 1.22.1, explicitly initialized with API22. The pinned 1.27.1 C++ headers are used only for compatible ownership methods. `GetTensorMutableData()` is used because the newer const-data API is not part of API22.

Reproduce from the repository root with the retained local dependencies:

```sh
ROOT="$PWD"
INC="$ROOT/experiments/0010-supertonic-qnn-htp-feasibility/.local/onnxruntime-v1.27.1-source/include/onnxruntime/core/session"
LIB="$ROOT/experiments/0024-pocket-tts-qnn-precompiled-context-startup/.local/export-venv/lib/python3.11/site-packages/onnxruntime/capi"
WORK=$(mktemp -d)
ln -s "$LIB/libonnxruntime.so.1.22.1" "$WORK/libonnxruntime.so.1"
g++ -std=c++17 -O1 -g -fsanitize=address -fno-omit-frame-pointer \
  -I"$INC" docs/qoralo-blog/evidence/bos-lifetime-repro.cc \
  -L"$LIB" -Wl,-rpath,"$LIB" -l:libonnxruntime.so.1.22.1 \
  -o "$WORK/repro"
LD_LIBRARY_PATH="$WORK" ASAN_OPTIONS=detect_leaks=0 "$WORK/repro"
# Expected nonzero exit with heap-use-after-free.
LD_LIBRARY_PATH="$WORK" ASAN_OPTIONS=detect_leaks=0 "$WORK/repro" keep-alive
# Expected exit 0 and PASS. Remove your temporary directory when done.
```

No downloads are part of the command. These local header/runtime caches must exist. Raw local diagnostic logs: `/tmp/qoralo-story-v3/{broken.asan.txt,kept.stdout,kept.stderr}`. Initial environment/API compatibility errors were resolved before the valid sanitizer comparison; those failed launches were not evidence of the source defect.

## What this changes, and what remains unproved

The old article presented the first EOS-logit difference as a meaningful device/runtime localization despite identical input conditions. The source defect means that inference input validity is not established by having matching token/cache/noise files. A tensor that points at freed storage is not a guaranteed identical input. **Runtime-only blame is not established.**

The historical JSON records the phone executable SHA-256 as `a11685f5635efdca81c07a12794a9e4d103e86f82b631e3b45dc893b17f57257`. That is a binary hash, not the source hash above. This audit has not verified a source-to-binary binding for that old executable and has not replayed the old model after changing only buffer lifetime. It therefore does not prove that this defect caused the exact old recording, its first logit difference, or every later error.

The fixed-cache runner uses a dedicated BOS graph and avoids this particular borrowed BOS-buffer path, but also changes the graph/state layout. Its accepted recording is not a controlled lifetime-only intervention. The separate zero-voice-encoder/invalid-Bria root cause belongs to different failed samples.

The source-level conclusion is concrete: this runner has undefined input-memory behavior; retain backing storage through consumption or use an owning tensor/copy. Exact audio causality remains untested. The blog now explains this actual ownership mechanism instead of decorating the logit symptom as a cause.

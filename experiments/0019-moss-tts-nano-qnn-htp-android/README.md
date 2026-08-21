# Experiment 0019 — MOSS-TTS-Nano QNN/HTP feasibility

## Final result

**Blocked before physical inference.** The complete fixed-capacity pipeline clears CPU equivalence and host QNN gates, and four host-generated context binaries reload as fail-closed one-partition QNN models. On the authorized Galaxy S23 Ultra, however, this exact carrier/app-UID direct-QNN path fails while creating the HTP device:

```text
QNN SetupBackend failed Failed to create device.
Error: QNN_DEVICE_ERROR_INVALID_CONFIG: Invalid config values
```

The failure occurs before the first neural session is created or assigned. Therefore experiment 0019 has **no phone inference, HTP WAV, RTF, memory benchmark, provider-event proof, RPC/accelerator/cycle/HVX execution proof, or listening verdict**. It must not appear as a completed full-HTP route.

This conclusion is intentionally narrow. It applies to the recorded carrier, app UID, Android build, ORT/QNN versions, and authorized phone. It does not establish that all Android apps, host contexts, or QNN deployments are incompatible.

[`results/fixed-capacity-phone-blocker.json`](results/fixed-capacity-phone-blocker.json) is the canonical final checkpoint. For clean-machine reproduction and continuation on another explicitly authorized device, start with [`HANDOFF.md`](HANDOFF.md) and [`results/continuation-manifest.json`](results/continuation-manifest.json).

## Canonical-v2 benchmark input

Final work uses repository protocol commit `2de8b80`:

- `protocols/android-tts-benchmark/transcript.txt`
- 226 bytes, no trailing newline
- SHA-256 `424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67`
- official SentencePiece model SHA-256 `c353ee1479b536bf414c1b247f5542b6607fb8ae91320e5af1781fee200fddff`
- 51 exact IDs in [`protocol/canonical-v2-tokenization.json`](protocol/canonical-v2-tokenization.json)

Canonical v2 changes exactly token positions 5 and 40 from legacy-v1 ID `1583` to comma ID `10364`. Token count and the `[1,226,17]` prefill shape do not change. [`results/canonical-v2-tokenization-impact.json`](results/canonical-v2-tokenization-impact.json) preserves the comparison.

The original 230-byte `350c8d3d…` transcript and tokenization files remain as immutable legacy-v1 evidence for the earlier host phase. They are not labeled canonical v2.

## Fixed-capacity decode ABI

The official loop starts with 226 prefill positions and permits 375 generated frames:

- decode input view: positions `0..599`, capacity 600;
- decode output/logical retained state: positions `0..600`, capacity 601;
- step 0 reads valid length 226 and writes state slot 226;
- step 373 reads 599 and writes 599;
- final step 374 reads 600 and writes retained slot 600;
- final slot 600 is not consumed by another decode call.

A first zero-padded design failed immediately. The original graph concatenates the new K/V at physical position 600, while its valid-length attention mask admits positions `0..valid_length`. At step 0 that masked out the actual current K/V and admitted zero padding at logical position 226. This was a step-0 topology error, not cumulative drift. The failed metrics and diagnosis remain in:

- [`results/fixed-capacity-padding-invalid.json`](results/fixed-capacity-padding-invalid.json)
- [`results/fixed-capacity-padding-diagnosis.json`](results/fixed-capacity-padding-diagnosis.json)

The accepted derivative preserves the physical `[past600,new@600]` graph outputs for the state ABI. For attention only, it constructs `[past600,zero]` and inserts new K/V at `past_valid_lengths`. It changes 24 K/V concat boundaries and redirects 36 attention/shape consumers. Original graph outputs remain unchanged, so application CPU orchestration still copies physical output index 600 to logical state slot `valid_length`.

## Canonical-v2 CPU equivalence

The replacement passed the frozen ORT 1.20 CPU policy:

| Boundary | Result |
|---|---:|
| Dynamic canonical-v2 stop | 161 frames |
| Fixed-route calls exercised | 375 |
| Hidden aggregate max / RMSE / cosine | `5.662e-6` / `8.321e-7` / `0.999999999999657` |
| New-K/V aggregate max / RMSE / cosine | `1.0967e-5` / `6.611e-7` / `0.999999999999763` |
| Final 601-state max / RMSE / cosine | `1.0967e-5` / `5.222e-7` / `0.999999999999861` |
| Observed codec length | exact 618,240 samples |
| Observed codec max / cosine | `5.543e-6` / `0.999999999998969` |
| Full-375 codec length | exact 1,440,000 samples |
| Full-375 codec max / cosine | `6.258e-6` / `0.999999999998332` |

Steps `0`, `104`, `208`, `209`, `373`, and `374` all pass. Final slot 600 is written and retained. The run used up to `22,739,692` KiB RSS; this is host validation resource evidence, not an Android memory result.

See [`results/fixed-capacity-cpu-equivalence.json`](results/fixed-capacity-cpu-equivalence.json), [`protocol/fixed-capacity-equivalence-policy.json`](protocol/fixed-capacity-equivalence-policy.json), and [`results/fixed-capacity-derivative-provenance.json`](results/fixed-capacity-derivative-provenance.json).

## Host QNN eligibility and contexts

The static derivatives all cleared fail-closed host QNN HTP gates:

- prefill: one complete partition;
- reusable fixed-capacity decode: one complete partition;
- local fixed-frame decoder: one complete partition;
- fixed-capacity full codec: one complete partition.

Four external QNN contexts were generated with QNN `2.49.0.260730134355`. Their binaries total 704,607,776 bytes. Minimum host `MemAvailable` during serialized generation was 9,546,780 KiB; swap remained effectively unused. Each context then reloaded fail-closed as exactly one QNN partition containing its single EPContext node.

Exact sources, context hashes/sizes, I/O shapes, SDK attributes, generation logs, reload gates, and resource minima are in [`results/fixed-capacity-context-provenance.json`](results/fixed-capacity-context-provenance.json). Host eligibility is not physical HTP execution.

## Android boundary

Nine isolated attempts progressively established the transport/backend boundary:

1. driver-shell initialization error before runner invocation;
2. SELinux denied executing a tmp-staged app-UID runner;
3. Samsung native-library-directory discovery mismatch;
4. first fail-closed EPContext session rejection;
5. INFO diagnostic of the same pre-inference rejection;
6. source-ONNX mode reached the same QNN backend device-creation failure;
7. required public `libcdsprpc.so` manifest exposure and exact app-native hashes passed;
8. a unique world-readable, hash-verified V73 DSP skel plus standard RFSA paths passed;
9. minimal runtime auto-detect removed `soc_model`, burst, and all optional device configs, but `CreateDevice` still returned `QNN_DEVICE_ERROR_INVALID_CONFIG`.

The final carrier used:

- Package-Manager-labeled native runner and exact ORT/QNN/V73 libraries;
- required public `libcdsprpc.so` declaration, confirmed present in `/vendor/lib64` and Samsung's `public.libraries.txt`;
- unique app-internal model/context staging with local/upload/internal SHA checks;
- unique tmp DSP-skel staging only, mode 0644 under a 0755 directory;
- CPU fallback disabled and graph-I/O quantization off;
- runtime SoC auto-detection and no performance-mode option.

The QNN backend interface loads, but `CreateDevice` fails before graph assignment. All attempts cleaned their unique stages and uninstalled the carrier. A final independent locked check confirmed the authorized identity, all `moss-0019-*` tmp paths absent, package absent, and the phone lock reclaimable.

## Claim boundaries

- CPU tokenization, prompt/state orchestration, fixed KV copies, stereo-to-mono conversion, and WAV encoding were designed as disclosed application work—not neural fallback.
- No mixed fallback phone route was run.
- No quantization or calibration was performed.
- No numerical result is treated as a listening verdict.
- Listening status is `not_reviewed` because no phone WAV exists.
- Phone benchmark fields are null with explicit reasons in the final checkpoint.

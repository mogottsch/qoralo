# Paired K-cache consumer — first bounded host result

**Complete: one weight-free paired graph, one high-level compile, one load-factory call and one forward. No retry.** The strict fullchain scalar reference does not reproduce the selected public output. This is a host functional observation, not physical Android HTP execution or a full-model cause/fix.

## Exact host identity

- ExecuTorch installed source declares **1.2.0+cpu**, revision `0b0e2c5cdd67c8b4396a46ea1d1aa72ffb0128d7`. Exact loaded-route file bindings, rather than an inferred native build provenance, are retained in `request.json` and `host-backend-identity.json`.
- Python3.11.13/Linux x86_64; Torch2.11.0+cpu; NumPy2.4.6.
- QAIRT**2.49.0.260730**, selected x86 library `libQnnHtp.so` SHA `e557ca522713ea7ee7efd252083b927009cd54c158899c086b23d92b63bf1f33`. Portable runtime `_portable_lib` SHA `dbcde02f5dd27d642baa2e496a3eac3146c7158677f3b16b48b3f78dff4c0b05`; native binding SHA `5a6c2eefd72a97d28869b4f219ee93d623c126fecf47214ffbad005083f8562f`.
- Retained runtime log explicitly identifies **kHtpBackend/HtpProvider, RouterX86/Router.X86**. The requested target is SoC43/SM8550/V73, but line366 says **“Setting libnative architecture to v79 (requested arch is v73)”**. Classify this as **x86-host HTP-provider/libnative simulation**, not actual v73 hardware execution. Pinning the available `libQnnHtpQemu.so` does not prove it was used; a loaded-library map was not captured.
- Logged QNN API2.38.0 versus wrapper tested-against2.27.0 warning is retained. Initial default SoC/architecture and the target overwrite messages are not physical device detection. Host HVX/VTCM/PD estimates and internal “fallback to hex-nn” messages are not Android hardware telemetry or ET CPU-tensor fallback.

One `QnnBackend` delegate and zero emitted ET KernelCalls establish the executable delegation path, **not Android HTP execution**. No device/RPC/cycle/performance claim is made.

## Fixture and actual result

Source/design predecessor: `176d250`. The exact request SHA is `1507d2acddc2f98c2ccdde0e5305af7a126af508aa43b39d05257af0536b29b8`.

State3/K3 uses its incoming narrow input domain and wider returned-key/Cat domain. State15/K15 is a **same-layout, unequal-domain control**, not an aligned-domain control. Each branch applies input QDQ and current-key QDQ, concatenates4095+1 positions and applies Cat QDQ. No Conv, slicing, attention, learned weights, original model archive or input sweep is involved.

Four FLOAT32 inputs total16MiB. They are positive zero except the saved K3 anchor10.028990745544434 and two declared synthetic1.0 values. Each output has2,097,152 elements. The fixture is overwhelmingly zero; high overall byte agreement is not broad numerical coverage.

| Public output site | Host actual | Fullchain scalar/CPU reference | Cat-only hypothesis |
|---|---:|---:|---:|
|K3 `[0,1,24,0]`|10.028992652893066|6.853916168212891|10.028990745544434|
|K3 in-range `[0,0,0,0]`|0.9999257326126099|0.9999256134033203|0.9999256134033203|
|K15 control `[0,1,24,0]`|1.0001479387283325|0.9998471736907959|1.000147819519043|

All4,194,304 outputs are finite and input bytes are unchanged. There are three bitwise mismatches versus fullchain, exactly the three nonzero sites; all other outputs are zero. The K3 anchor differs from fullchain by3.175076484680176; K15 differs by0.0003007650375366211. Complete outputs are within2ULP/1ULP of the Cat-only hypothesis for K3/K15 respectively, **not byte-identical** to it. The in-range K3 point does not distinguish fullchain from Cat-only; its mismatch is a small rounding difference.

This rules out the strict fullchain result at the affected public-output anchor in this synthetic consumer. It does not prove that the SDK deleted a particular Quantize node, reveal actual consumed integer codes, establish universal Cat-only behavior, or attribute full-model drift. The earlier Conv sweep remains a separate non-universal result.

## Frontend declarations versus internal execution

The actual pre-Compile wrapper tap contains **four Quantize, two Concat and two Dequantize operators**, including both cache-input Quantize nodes with their expected UFIXED_POINT_16 scales/offsets. The ET-level delegation summary counts the two Cat computations after QDQ folding. These are different representation layers, not contradictory operator counts.

Declared cache input scale/offset pairs are0.00029122494743205607/−42000 and0.00027434100047685206/−32369; their wider Cat pairs are0.00034575574682094157/−35376 and0.0003006155020557344/−35268. Float public input/output wrappers are present. Complete encoding-kind/bitwidth tags are not exposed by the getter; that limitation remains null, not invented. No extra context load or tensor-dump rebuild was used to obtain missing internal metadata.

## Execution, validation and retention

- Five scalar/array tests passed without Torch/SDK calls. One CPU reference forward matched both entire independent NumPy/scalar-reference outputs byte-for-byte before compilation.
- One compiler manager construction and one native Compile callback were observed. One QNN delegate covers both Cat computations, with zero tensor-compute fallback and zero final ET KernelCalls.
- PTE:97,904bytes, SHA `d88182196544514ee3dc888b05a68a3eab11d7be90f4f5befd4a8580a01faf0d`. Context:96,112bytes; the context/PTE remain LOCAL-ONLY and migration-required, listed in `local-native-artifacts.json`.
- Compile guard28.228503s, runtime guard7.007353s; peak process RSS734,600/692,640KiB.4GiB address-space cap, CPUs0–3, low priority, disk scratch,120s compile/60s runtime budgets and240s active cap. These are host process observations, not DSP memory/timing.
- **Timing limitation:** raw `load_seconds` is only the41.4µs factory API call. It excludes `method_meta` and may exclude lazy backend initialization. Backend-ready setup and its exact split were not captured. The first forward API interval1.465852s includes any remaining lazy work. Neither is a canonical setup/prefill/TTFT/decode metric; no timing-only rerun was made.
- Source/input/reference/runtime postpins passed. All four supervised workers were reaped and their groups absent. Initial compile/runtime cleanup correctly recorded nonempty scratch because of empty `torchinductor_moritz` directories. Their before-inventory and later removal are retained separately; no scratch files existed or were deleted, and every phase scratch is now empty. The original false cleanup observations were not overwritten.
- **12 full raw arrays (80MiB) are preserved losslessly as2,977bytes of zstd**, each fully decompressed and hash-verified. All originals remain local. Raw outputs were written before comparison. Logs, ABI, all metadata taps, sources, request and cleanup are retained. No learned model/PTE/library bytes are copied into Git.

## Next discriminating step, not an approval loop

Do not repeat this host fixture merely to improve agreement. The next useful contrast is the **same immutable tiny PTE and same input bytes on the actual SM8550/v73 device**, using a separate fixture-capable command-line runner (four inputs/two outputs), not the49-output full-model runner or podcast app. It requires no model recalibration or graph recompile and separates this host libnative-v79 observation from target behavior. Offline runner compatibility/preparation can proceed within Qwen ownership; device execution must be scheduled through Pi/full phone.lock behind Janek's app repair. This is a scheduling dependency, not another user permission gate.

Even a target match would remain a synthetic-consumer result, not full-model fidelity or logit causality. A mismatch would localize a host/target distinction before altering model quantization. Preserve both outcomes, actual backend identity and public-vs-internal limits. No new phone/model run is included in this package. Push/history-rewrite hold remains; no agents or Nik review.

# Physical-device control

[`run_tiny_htp_smoke.sh`](run_tiny_htp_smoke.sh) is the sanitized reproduction of the accepted experiment-0010 phone control. It stages only a tiny QDQ graph and the local Android ORT/QAIRT runtime into a scoped `/data/local/tmp` directory, acquires the repository phone lock, requires the exact `SM-S918B`/`SM8550`, disables ORT CPU fallback, captures detailed QNN profiling, checks for RPC/accelerator/HVX evidence, and removes its device staging directory on exit.

It intentionally cannot run the Supertonic vocoder. The current Android runtime predates the tracked ORT crash backport, and the patched host gate still rejects eight decomposed-GELU `Erf` nodes. See [`../HANDOFF.md`](../HANDOFF.md) before adding any larger device action.

Before every invocation:

1. confirm that no other experiment owns the phone;
2. notify Moritz and obtain fresh immediate approval;
3. set `PHONE_USE_CONFIRMED=yes` only for that confirmed invocation;
4. pass an output directory below ignored `../work/`.

QAIRT `2.49.0.260730` requires `libQnnHtpPrepare.so` in addition to the backend, system, V73 stub, and V73 skel files. The library is dynamically loaded and must not be omitted merely because it is absent from `readelf -d libQnnHtp.so`.

No Qualcomm runtime, model, profile, tensor, device serial, or generated output is stored in this directory or committed by the script.

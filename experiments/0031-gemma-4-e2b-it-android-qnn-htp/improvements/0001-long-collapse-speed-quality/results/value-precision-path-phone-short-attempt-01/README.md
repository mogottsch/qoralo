# True precision-path candidate: physical short compatibility passes

Run `value-short-20260911T124722Z-01`, one-use slot
`pi-gemma-value-short-20260911-a`. Pi granted this slot after Ben's first full-HTP
TTS attempt released the phone. This Gemma run made no app/data changes and did
not execute an exact-long request.

## Result

The new context `27e19e32ef479dfb39b53e6530cd25105c3c8e9ccf9fa4b9e9af4b5d770fabdd`
completed one fresh-dialog short/max16 query on the physical SM8550. Runtime
stdout contains the exact frozen prompt; profile count is170 input/16 generated,
with the expected single-BOS prefix. The provider log records SMART_MASK and
2AR128+15AR1=17 status0 completions, one query entry/return and one context/dialog.
No CPU-backend, runtime-fallback, nonzero-execute or cache-quantization marker was
found. All raw markers are preserved, including18 execute-start text matches and
the known usesCrossAttention warning. Start-marker counts are not a separate
request-count invariant.

The89-byte output is coherent as a deliberately capped short prefix:

> The choice between the Cedar, Juniper, and Rowan inference engines hinges entirely on the

Output SHA-256:
`70711436da1fba6f0b7d869c319f8d97c0819d36affbd369e119c1c3f04d6357`.
It is identical to the previous FP16-interface candidate's short output. This
establishes compatibility for this request, not long-output improvement or hidden
numerical equality. Output sanity was explicitly reviewed against this hash.

Raw Genie query duration is1,356,705us, TTFT455,407us, reported prefill373.413tok/s
and generation18.7115tok/s; init-time1,846,375us. These are one max16 engineering
observation with runtime-defined timing boundaries, not a canonical distribution
or a speed comparison. Normalized decode remains null because first-token rate
semantics are not established. The query returned and the ceiling was reached;
an independent EOS-versus-limit enum remains unexposed.

## Retention and release

All53 ADB calls were under the noninherited full phone.lock lease. A live native
PID was observed with its exact identity. The raw pull completed before remote
root deletion. Model/wrapper/watchdog PIDs and the remote root were verified
absent, no signals were issued, and the lock was released. Pi received the
outcome/release before any next device slot. The launcher saved actual exit0;
this is not inferred from post-GC systemd defaults.

Battery core fields were80→80%,28.0→28.0°C, USB powered. Thermal status remained0;
AP33.9→39.6°C and skin30.2→30.8°C. No process PSS/VmHWM or HTP-private memory was
measured. Full original Samsung battery dumps stay private and hash-bound;
public evidence contains explicitly labeled core-field extracts only. The
714,303-byte provider log and all other retained public raw bytes are unchanged.
The original private controller checksum manifest was verified in full.

The canonical campaign, previous exact-long negative and all previous stages
remain unchanged. Full-DLC floating-path gates and compiled-context metadata are
separate evidence; this short run does not prove every finalized kernel's
arithmetic, universal CPU-free placement, fidelity, root cause, quality or speed.

Next: freeze the separate exact-long/max2048 stage and run it in a subsequent
Pi-coordinated slot. No automatic overlapping request or baseline replay.

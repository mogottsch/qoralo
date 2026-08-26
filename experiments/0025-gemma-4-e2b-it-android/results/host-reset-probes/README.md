# LiteRT-LM reset probes

These host-only diagnostics compare two bounded two-request strategies on one loaded Engine:

- `rewind/`: reuse one Session and call `RewindToStep(0)` before request two. Request two reused prefix/KV state and therefore failed the full-reset requirement.
- `fresh_session/`: destroy and recreate the Session before request two while retaining the Engine. Both requests performed genuine full prefill; Session recreation took about 41 microseconds in this observation.

These are compatibility diagnostics, not Android performance evidence. They support the proposed one-Engine/fresh-Session adaptation, which still requires explicit approval because the canonical contract says the warm campaign reuses one session.

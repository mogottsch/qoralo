# Canonical Android CPU campaign

This directory contains the complete protocol-v2 Gemma 4 E2B IT Android CPU campaign: one first short request followed by five loaded-Engine requests for each of short, medium, and long. The Engine/model route remained loaded while a fresh Session isolated every logical request after the first. Session recreation is measured separately and excluded from request timing.

The runner completed all 16 requests with exit code zero. Raw output, logs, manifests, operating conditions, lock lifecycle, and verified scoped cleanup are retained. `SHA256SUMS` binds every other file in this directory.

The phone began warm and ended at Android thermal status 3. Treat the resulting performance as the observed sustained campaign under those documented conditions; do not hide or normalize away likely thermal throttling.

This is execution/performance evidence. The exact-hash output sanity check establishes only that the outputs look like sensible natural-language text, not that they are correct or useful.

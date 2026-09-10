# First attempt — transport preflight failure

The first explicitly authorized attempt stopped at its first command:

```text
adb -s R5CW81PR8SY shell getprop ro.product.model
adb: device 'R5CW81PR8SY' not found
```

The command exited 1. No install, model staging, settings change, instrumentation, inference, phone scratch root, or phone process was reached. Controller/ADB children exited and `phone.lock` was released. `launched=false` and raw command/output/cleanup bytes are retained. Package-retention flags in generic cleanup metadata do not imply a package was installed during this attempt.

This is transport-only evidence, not model/runtime evidence. No automatic retry occurred; the later run had a new explicit authorization and distinct directory.

# Historical unapproved diagnostic draft — superseded by v2

This initial source/mock candidate was not executed. Its request digest is `15807e707d74472a1a97faefc430d326ed8f749aa1d140ab4f5814dc9f49c02c`; the source snapshot and44-test receipt are retained unchanged.

Nik's source review found that optional cgroup capture/write failures could mask the original constructor exception, and that relative/parent-traversal scope paths needed rejection. Both were corrected and tested in `../vocoder-diagnostic-readiness-20260910-rev02/`. Only the v2 request is a current candidate; no diagnostic constructor has been released or executed.

`logging-source.json` identifies the exact read-only ORT QNN logging-bridge source used for this design. Runtime/model/shape/RAM changes were not made.

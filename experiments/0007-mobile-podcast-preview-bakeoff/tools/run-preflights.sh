#!/usr/bin/env bash
# Measure sequentially under the conservative/exclusive grant, then atomically install.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/.." && pwd)"
ARTIFACTS="$ROOT/artifacts/task-5"
POLICY="$ROOT/protocol/model-resource-policy-v1.json"

"$HERE/with-resources.sh" --policy "$POLICY" --task task-5 --kind preflight -- \
  env PREVIEW_RESOURCE_GRANT_KIND=preflight python3 "$HERE/run_preflights.py"
# install-policy holds the final administrative grant, requires zero active grants,
# fsyncs the complete candidate, and exposes it to readers with one rename.
python3 "$HERE/resource_lock.py" install-policy --lock-root "${PREVIEW_LOCK_ROOT:-/tmp/mobile-podcast-preview-gate}" \
  "$ARTIFACTS/measured-policy.json" "$POLICY"
echo "Installed measured generation policy: $POLICY"

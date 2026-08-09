#!/usr/bin/env bash
# Python owns one atomic interlocking grant and releases it in a finally block
# on normal exit, command failure, SIGINT, SIGTERM, and SIGHUP.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/resource_lock.py" run "$@"

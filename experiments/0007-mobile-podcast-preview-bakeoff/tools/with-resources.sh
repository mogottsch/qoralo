#!/usr/bin/env bash
# Python owns the atomic lock directories and releases them in finally blocks on
# normal exit, command failure, SIGINT, SIGTERM, and SIGHUP.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/resource_lock.py" "$@"

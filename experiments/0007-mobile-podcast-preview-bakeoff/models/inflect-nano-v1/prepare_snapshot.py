#!/usr/bin/env python3
"""Download only the immutable, hash-pinned Inflect-Nano-v1 inference snapshot."""
from __future__ import annotations

import json
from pathlib import Path

from track import PINS, SNAPSHOT, verify_snapshot


def main() -> None:
    from huggingface_hub import snapshot_download

    identity = PINS["identity"]
    downloaded = Path(snapshot_download(
        repo_id=identity["repository"],
        revision=identity["revision"],
        allow_patterns=list(PINS["artifacts"]["files"]),
        local_dir=SNAPSHOT,
    ))
    verified = verify_snapshot(downloaded)
    print(json.dumps({"status": "passed", "snapshot": str(downloaded), "verified_files": len(verified)}, sort_keys=True))


if __name__ == "__main__":
    main()

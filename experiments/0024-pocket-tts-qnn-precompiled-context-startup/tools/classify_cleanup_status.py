#!/usr/bin/env python3
"""Classify remote cleanup verification without conflating ADB failure and absence."""
from __future__ import annotations

import argparse


def classify(transport_rc: int, exists_rc: int | None) -> tuple[str, int]:
    if transport_rc != 0:
        return "pending_device_reconnect", 2
    if exists_rc == 1:
        return "verified_absent", 0
    if exists_rc == 0:
        return "remote_present", 1
    return "cleanup_verification_error", 3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("transport_rc", type=int)
    parser.add_argument("exists_rc", type=int, nargs="?")
    args = parser.parse_args()
    status, exit_code = classify(args.transport_rc, args.exists_rc)
    print(status)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()

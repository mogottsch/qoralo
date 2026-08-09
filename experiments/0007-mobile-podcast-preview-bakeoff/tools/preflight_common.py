#!/usr/bin/env python3
"""Low-overhead process-tree RSS sampling for ignored model preflights."""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path


def _rss_bytes(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def _children(pid: int) -> list[int]:
    found: list[int] = []
    pending = [pid]
    while pending:
        parent = pending.pop()
        try:
            direct = [int(value) for value in Path(f"/proc/{parent}/task/{parent}/children").read_text().split()]
        except (OSError, ValueError):
            direct = []
        found.extend(direct)
        pending.extend(direct)
    return found


class RssSampler:
    """Sample this process and descendants, retaining peaks by named phase."""

    def __init__(self, interval_seconds: float = 0.02):
        self.interval_seconds = interval_seconds
        self.phase = "baseline"
        self.peaks: dict[str, int] = {}
        self.samples = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="rss-sampler", daemon=True)

    def start(self) -> "RssSampler":
        self._thread.start()
        return self

    def mark(self, phase: str) -> None:
        self.phase = phase
        self.sample_now()

    def sample_now(self) -> int:
        total = sum(_rss_bytes(pid) for pid in [os.getpid(), *_children(os.getpid())])
        self.peaks[self.phase] = max(total, self.peaks.get(self.phase, 0))
        self.samples += 1
        return total

    def stop(self) -> dict[str, object]:
        self.sample_now()
        self._stop.set()
        self._thread.join(timeout=2)
        return {
            "sampling_interval_seconds": self.interval_seconds,
            "sample_count": self.samples,
            "phase_peak_process_tree_rss_bytes": self.peaks,
            "peak_process_tree_rss_bytes": max(self.peaks.values(), default=0),
        }

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self.sample_now()

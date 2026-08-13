#!/usr/bin/env python3
"""Shared, dependency-free measurements for protocol-v2 generation jobs.

All elapsed values use ``time.monotonic``. RSS is sampled every 20 ms from the
root process and all recursively discovered descendants. ``baseline`` is a
synchronous sample taken before model loading; ``peak`` is the largest complete
process-tree sample, including that baseline. A process disappearing while
``/proc`` is read is counted as a race rather than failing the generation.

RTF always divides generation wall time by accepted *raw native* duration, not
the normalized 15-second duration. First audible output is the first 10 ms,
non-overlapping frame whose RMS is at least -50 dBFS. An unavailable first API
or audible output is represented by a null value and a non-empty reason.
"""
from __future__ import annotations

import math
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

RSS_SAMPLE_INTERVAL_SECONDS = 0.020
AUDIBLE_FRAME_SECONDS = 0.010
AUDIBLE_THRESHOLD_DBFS = -50.0
AUDIBLE_THRESHOLD_RMS = 10.0 ** (AUDIBLE_THRESHOLD_DBFS / 20.0)
RSS_SAMPLE_INTERVAL_MS = round(RSS_SAMPLE_INTERVAL_SECONDS * 1000)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def process_tree_rss_bytes(root_pid: int | None = None, proc_root: str | Path = "/proc") -> tuple[int, int]:
    """Return ``(aggregate_rss_bytes, process_races)`` for a recursive tree.

    Children are discovered before the parent's RSS is read. Missing/exited
    processes and malformed transient proc entries contribute zero and increment
    the race count. PIDs are de-duplicated to tolerate unusual proc snapshots.
    """
    proc_root = Path(proc_root)
    pending = [os.getpid() if root_pid is None else root_pid]
    seen: set[int] = set()
    total = races = 0
    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        try:
            children = _read_text(proc_root / str(pid) / "task" / str(pid) / "children")
            pending.extend(int(value) for value in children.split())
        except (OSError, ValueError):
            races += 1
        try:
            status = _read_text(proc_root / str(pid) / "status")
            rss_line = next(line for line in status.splitlines() if line.startswith("VmRSS:"))
            total += int(rss_line.split()[1]) * 1024
        except (OSError, ValueError, IndexError, StopIteration):
            races += 1
    return total, races


class ProcessTreeRssSampler:
    """Fixed-interval recursive RSS sampler with explicit baseline semantics."""

    def __init__(
        self,
        root_pid: int | None = None,
        interval_seconds: float = RSS_SAMPLE_INTERVAL_SECONDS,
        sample: Callable[[int | None], tuple[int, int]] | None = None,
        *,
        rss_reader: Callable[[int], int] | None = None,
        children_reader: Callable[[int], Iterable[int]] | None = None,
    ):
        if interval_seconds != RSS_SAMPLE_INTERVAL_SECONDS:
            raise ValueError(f"RSS sampling uses the fixed {RSS_SAMPLE_INTERVAL_MS} ms interval")
        if sample is not None and (rss_reader is not None or children_reader is not None):
            raise ValueError("provide either a tree sample or per-process readers")
        self.root_pid = root_pid
        self.interval_seconds = interval_seconds
        if rss_reader is not None or children_reader is not None:
            if rss_reader is None or children_reader is None:
                raise ValueError("both per-process RSS and children readers are required")
            self._sample = lambda pid: self._sample_from_readers(pid, rss_reader, children_reader)
        else:
            self._sample = sample or process_tree_rss_bytes
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="generation-rss-sampler", daemon=True)
        self._started = False
        self._lock = threading.Lock()
        self.baseline_rss_bytes: int | None = None
        self.peak_process_tree_rss_bytes = 0
        self.sample_count = 0
        self.process_race_count = 0

    @staticmethod
    def _sample_from_readers(
        root_pid: int | None,
        rss_reader: Callable[[int], int],
        children_reader: Callable[[int], Iterable[int]],
    ) -> tuple[int, int]:
        pending = [os.getpid() if root_pid is None else root_pid]
        seen: set[int] = set()
        total = races = 0
        while pending:
            pid = pending.pop()
            if pid in seen:
                continue
            seen.add(pid)
            try:
                pending.extend(children_reader(pid))
            except (OSError, ProcessLookupError, KeyError, ValueError):
                races += 1
            try:
                total += rss_reader(pid)
            except (OSError, ProcessLookupError, KeyError, ValueError):
                races += 1
        return total, races

    def sample_now(self) -> int:
        rss, races = self._sample(self.root_pid)
        if rss < 0 or races < 0:
            raise ValueError("RSS samples and race counts must be non-negative")
        with self._lock:
            self.sample_count += 1
            self.process_race_count += races
            self.peak_process_tree_rss_bytes = max(self.peak_process_tree_rss_bytes, rss)
        return rss

    def start_before_model_load(self) -> "ProcessTreeRssSampler":
        """Capture the pre-load baseline synchronously, then begin sampling."""
        if self._started:
            raise RuntimeError("RSS sampler was already started")
        self.baseline_rss_bytes = self.sample_now()
        self._started = True
        self._thread.start()
        return self

    def stop(self) -> dict[str, object]:
        if not self._started or self.baseline_rss_bytes is None:
            raise RuntimeError("RSS sampler was not started before model load")
        self.sample_now()
        self._stop.set()
        self._thread.join(timeout=max(2.0, self.interval_seconds * 4))
        if hasattr(self._thread, "is_alive") and self._thread.is_alive():
            raise RuntimeError("RSS sampler did not stop")
        limitations = []
        if self.process_race_count:
            limitations.append(
                f"{self.process_race_count} process-tree /proc reads raced with child creation or exit; those processes contributed zero to affected samples"
            )
        return {
            "baseline_rss_bytes": self.baseline_rss_bytes,
            "peak_process_tree_rss_bytes": self.peak_process_tree_rss_bytes,
            "sample_interval_ms": round(self.interval_seconds * 1000),
            "sample_count": self.sample_count,
            "process_race_count": self.process_race_count,
            "sampling_limitations": limitations,
        }

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self.sample_now()


def raw_duration_rtf(generation_wall_seconds: float, raw_duration_seconds: float) -> float:
    """Compute RTF using the accepted raw native duration as denominator."""
    if generation_wall_seconds < 0:
        raise ValueError("generation wall time cannot be negative")
    if raw_duration_seconds <= 0:
        raise ValueError("raw duration must be positive")
    return generation_wall_seconds / raw_duration_seconds


def first_audible_offset_seconds(
    samples: Iterable[float],
    sample_rate_hz: int,
    *,
    threshold_dbfs: float = AUDIBLE_THRESHOLD_DBFS,
    frame_seconds: float = AUDIBLE_FRAME_SECONDS,
) -> float | None:
    """Find the first qualifying non-overlapping RMS frame in native audio."""
    if sample_rate_hz <= 0:
        raise ValueError("sample rate must be positive")
    frame_samples = round(sample_rate_hz * frame_seconds)
    if frame_samples <= 0:
        raise ValueError("audible analysis frame must contain samples")
    threshold = 10.0 ** (threshold_dbfs / 20.0)
    frame: list[float] = []
    frame_start = 0
    for value in samples:
        sample = float(value)
        if not math.isfinite(sample):
            raise ValueError("audible timing input contains a non-finite sample")
        frame.append(sample)
        if len(frame) == frame_samples:
            rms = math.sqrt(sum(item * item for item in frame) / frame_samples)
            if rms >= threshold:
                return frame_start / sample_rate_hz
            frame_start += frame_samples
            frame.clear()
    return None


def first_audible_sample(samples: Iterable[float], sample_rate_hz: int) -> int | None:
    """Return the first audible frame's sample index, or null for no full frame."""
    offset = first_audible_offset_seconds(samples, sample_rate_hz)
    return None if offset is None else round(offset * sample_rate_hz)


def nullable_timing(value: float | None, unavailable_reason: str | None = None) -> dict[str, float | str | None]:
    """Enforce the evidence contract: null requires a reason; a value forbids one."""
    if value is None:
        if not unavailable_reason or not unavailable_reason.strip():
            raise ValueError("timing requires a non-empty reason when unavailable")
        return {"seconds": None, "unavailable_reason": unavailable_reason.strip()}
    if value < 0 or not math.isfinite(value):
        raise ValueError("timing must be finite and non-negative")
    if unavailable_reason is not None:
        raise ValueError("available timing cannot have an unavailable reason")
    return {"seconds": value, "unavailable_reason": None}


@dataclass
class GenerationTimer:
    """Monotonic API timer supporting streaming and completion-only APIs."""

    clock: Callable[[], float] = time.monotonic
    started_at: float | None = None
    ended_at: float | None = None
    api_first_output_seconds: float | None = None
    first_audible_output_seconds: float | None = None

    def start(self) -> "GenerationTimer":
        if self.started_at is not None:
            raise RuntimeError("generation timer was already started")
        self.started_at = self.clock()
        return self

    def mark_api_output(self, samples: Sequence[float] | None = None, sample_rate_hz: int | None = None) -> float:
        elapsed = self._elapsed()
        if self.api_first_output_seconds is None:
            self.api_first_output_seconds = elapsed
        if samples is not None:
            if sample_rate_hz is None:
                raise ValueError("sample rate is required with an audio payload")
            offset = first_audible_offset_seconds(samples, sample_rate_hz)
            if offset is not None and self.first_audible_output_seconds is None:
                self.first_audible_output_seconds = elapsed + offset
        return elapsed

    def observe_audio(self, samples: Sequence[float], sample_rate_hz: int, *, arrival_seconds: float | None = None) -> float | None:
        """Record payload arrival and first audible time within that payload."""
        arrival = self.mark_api_output() if arrival_seconds is None else arrival_seconds
        if arrival < 0:
            raise ValueError("payload arrival cannot be negative")
        if self.api_first_output_seconds is None:
            self.api_first_output_seconds = arrival
        offset = first_audible_offset_seconds(samples, sample_rate_hz)
        if offset is not None and self.first_audible_output_seconds is None:
            self.first_audible_output_seconds = arrival + offset
        return self.first_audible_output_seconds

    def stop(self) -> float:
        if self.started_at is None:
            raise RuntimeError("generation timer was not started")
        if self.ended_at is None:
            self.ended_at = self.clock()
        wall = self.ended_at - self.started_at
        if wall < 0:
            raise RuntimeError("monotonic clock moved backwards")
        return wall

    def result(self, raw_duration_seconds: float, *, api_reason: str | None = None, audible_reason: str | None = None) -> dict[str, float | str | None]:
        wall = self.stop()
        api = nullable_timing(self.api_first_output_seconds, api_reason)
        audible = nullable_timing(self.first_audible_output_seconds, audible_reason)
        result: dict[str, float | str | None] = {
            "clock": "CLOCK_MONOTONIC",
            "generation_wall_seconds": wall,
            "api_first_output_seconds": api["seconds"],
            "first_audible_output_seconds": audible["seconds"],
            "rtf": raw_duration_rtf(wall, raw_duration_seconds),
            "rtf_denominator": "raw_native_audio_duration_seconds",
        }
        if api["unavailable_reason"] is not None:
            result["api_first_output_unavailable_reason"] = api["unavailable_reason"]
        if audible["unavailable_reason"] is not None:
            result["first_audible_output_unavailable_reason"] = audible["unavailable_reason"]
        return result

    def finish(
        self,
        raw_duration_seconds: float,
        *,
        api_first_output_unavailable_reason: str | None = None,
        first_audible_output_unavailable_reason: str | None = None,
    ) -> dict[str, float | str | None]:
        return self.result(
            raw_duration_seconds,
            api_reason=api_first_output_unavailable_reason,
            audible_reason=first_audible_output_unavailable_reason,
        )

    def _elapsed(self) -> float:
        if self.started_at is None:
            raise RuntimeError("generation timer was not started")
        elapsed = self.clock() - self.started_at
        if elapsed < 0:
            raise RuntimeError("monotonic clock moved backwards")
        return elapsed


def result_is_publishable(result: dict[str, object]) -> bool:
    """Fail closed: blockers, short raw audio, and incomplete output never unlock publication."""
    raw = result.get("raw")
    normalized = result.get("normalized")
    return (
        result.get("status") == "accepted"
        and result.get("blocker") is None
        and isinstance(raw, dict)
        and raw.get("preserved_unchanged") is True
        and isinstance(raw.get("duration_seconds"), (int, float))
        and raw["duration_seconds"] >= 15.0
        and isinstance(normalized, dict)
        and normalized.get("sample_count") == 360000
        and result.get("forbidden_transformations_used", []) == []
        and result.get("publication_eligible", True) is True
    )


accepted_for_publication = result_is_publishable

"""Independent strict host PCM WAV validation (does not use Android writer/reader code)."""
from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class WavError(ValueError):
    pass


@dataclass(frozen=True)
class WavReport:
    sha256: str
    sample_rate_hz: int
    frames: int
    duration_seconds: float
    peak: float
    rms: float


def encode_pcm16(samples: Iterable[float], sample_rate: int) -> bytes:
    if sample_rate <= 0:
        raise WavError("invalid sample rate")
    values = list(samples)
    if not values:
        raise WavError("empty source samples")
    encoded = bytearray()
    for value in values:
        if not math.isfinite(value):
            raise WavError("non-finite source sample")
        encoded += struct.pack("<h", max(-32768, min(32767, round(value * 32767))))
    data_size = len(encoded)
    return (b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVEfmt " +
            struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16) +
            b"data" + struct.pack("<I", data_size) + bytes(encoded))


def validate_bytes(payload: bytes, expected_sha256: str | None = None) -> WavReport:
    observed = hashlib.sha256(payload).hexdigest()
    if expected_sha256 is not None and observed != expected_sha256:
        raise WavError("WAV hash drift")
    if len(payload) < 44 or payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
        raise WavError("malformed WAV header")
    riff_size = struct.unpack_from("<I", payload, 4)[0]
    if riff_size + 8 != len(payload):
        raise WavError("RIFF size/trailing-byte mismatch")
    offset = 12
    fmt = None
    data = None
    while offset + 8 <= len(payload):
        chunk_id = payload[offset:offset + 4]
        size = struct.unpack_from("<I", payload, offset + 4)[0]
        start, end = offset + 8, offset + 8 + size
        if end > len(payload):
            raise WavError("truncated WAV chunk")
        if chunk_id == b"fmt ":
            if fmt is not None or size != 16:
                raise WavError("duplicate or unsupported fmt chunk")
            fmt = struct.unpack_from("<HHIIHH", payload, start)
        elif chunk_id == b"data":
            if data is not None:
                raise WavError("duplicate data chunk")
            data = payload[start:end]
        offset = end + (size & 1)
    if offset != len(payload) or fmt is None or data is None:
        raise WavError("incomplete WAV chunk structure")
    audio_format, channels, rate, byte_rate, block_align, bits = fmt
    if (audio_format, channels, bits) != (1, 1, 16) or rate <= 0 or byte_rate != rate * 2 or block_align != 2:
        raise WavError("WAV must be canonical mono PCM16")
    if not data or len(data) % block_align:
        raise WavError("empty or partial PCM frame")
    samples = [item[0] for item in struct.iter_unpack("<h", data)]
    frames = len(data) // block_align
    if frames != len(samples):
        raise WavError("sample/frame disagreement")
    peak_i = max(abs(value) for value in samples)
    rms = math.sqrt(sum((value / 32768.0) ** 2 for value in samples) / frames)
    if rms < 1e-5:
        raise WavError("silent audio")
    if peak_i >= 32767:
        raise WavError("clipped audio")
    duration = frames / rate
    if not math.isfinite(duration) or duration <= 0 or abs(duration * rate - frames) > 1e-9:
        raise WavError("duration/frame disagreement")
    return WavReport(observed, rate, frames, duration, peak_i / 32768.0, rms)


def validate_file(path: Path, expected_sha256: str | None = None) -> WavReport:
    return validate_bytes(path.read_bytes(), expected_sha256)

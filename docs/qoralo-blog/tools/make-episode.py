#!/usr/bin/env python3
"""Make the web copy of a full episode WAV exported from the app.

  python3 make-episode.py EPISODE.wav [--out ../media/episode.m4a]

The page plays a compressed copy because a 3-minute WAV is 16 MB. The audio itself is the app's output; only two things change:
a measured gain (raise to -16 LUFS, but never let the peak pass -1.5 dBFS, the same policy as the demo video) and AAC encoding at
128 kbit/s (mono, 44.1 kHz). The original WAV is never modified and is not stored in the repository.
"""
import argparse, hashlib, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

def measure(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    return float(re.findall(r"^\s+I:\s+(-?[\d.]+) LUFS", r.stderr, re.M)[-1]), float(re.findall(r"^\s+Peak:\s+(-?[\d.]+) dBFS", r.stderr, re.M)[-1])

def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wav", type=Path)
    ap.add_argument("--out", type=Path, default=HERE.parent / "media" / "episode.m4a")
    ap.add_argument("--target-lufs", type=float, default=-16)
    ap.add_argument("--peak-ceiling", type=float, default=-1.5)
    a = ap.parse_args()
    lufs, peak = measure(a.wav)
    gain = min(a.target_lufs - lufs, a.peak_ceiling - peak)
    print(f"source: {a.wav.name}  {duration(a.wav):.1f}s  sha256 {hashlib.sha256(a.wav.read_bytes()).hexdigest()}")
    print(f"level: {lufs:.1f} LUFS, peak {peak:.1f} dBFS -> gain {gain:+.1f} dB (target {a.target_lufs} LUFS, peak ceiling {a.peak_ceiling} dBFS)")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    limit = 10 ** (a.peak_ceiling / 20)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(a.wav), "-vn",
                    "-af", f"volume={gain:.2f}dB,alimiter=limit={limit:.3f}:level=disabled",
                    "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "1", "-movflags", "+faststart", str(a.out)], check=True)
    l2, p2 = measure(a.out)
    print(f"wrote {a.out} ({a.out.stat().st_size/1e6:.1f} MB, {duration(a.out):.1f}s): {l2:.1f} LUFS, peak {p2:.1f} dBFS")

if __name__ == "__main__":
    sys.exit(main())

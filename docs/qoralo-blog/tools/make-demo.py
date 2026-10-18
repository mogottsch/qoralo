#!/usr/bin/env python3
"""Cut the raw scrcpy recording into the article's demo video.

  python3 make-demo.py RAW.mkv [--cuts demo-cuts.json] [--out ../media/demo.mp4] [--include-drafts] [--dry-run]

Crops the status and navigation bars, drops the listed gaps, speeds up the listed waits (muted, with a visible
"Nx speed, N s real time" badge so the speed-up is honest), adds timed on-screen notes, lifts the very quiet audio
with a measured gain and encodes H.264 + AAC with fast start. The raw file is never modified.

Notes live in demo-cuts.json under "notes". A note is only rendered when "approved" is true, unless --include-drafts is
given (use that together with --out to make a preview file for reviewing wording and placement).
"""
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HIGHLIGHT = "0xff5a1f"   # vivid orange: visible on the app's near-white screens (the article's mint is not)

def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())

def measure_audio(path):
    """Integrated loudness (LUFS) and peak (dBFS) of the raw audio. Silence is gated out of the loudness."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    i = re.findall(r"^\s+I:\s+(-?[\d.]+) LUFS", r.stderr, re.M)[-1]
    pk = re.findall(r"^\s+Peak:\s+(-?[\d.]+) dBFS", r.stderr, re.M)[-1]
    return float(i), float(pk)

def font(bold):
    r = subprocess.run(["fc-match", "-f", "%{file}", "sans:bold" if bold else "sans"], capture_output=True, text=True)
    return r.stdout.strip() or ("/usr/share/fonts/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/noto/NotoSans-Regular.ttf")

def timeline(cfg, duration):
    """[(raw_start, raw_end, speed, final_start)] for every kept segment, in order."""
    out, t = [], 0.0
    for s in cfg["segments"]:
        st, en, sp = float(s["start"]), float(s["end"] if s.get("end") is not None else duration), float(s.get("speed", 1))
        out.append((st, en, sp, t))
        t += (en - st) / sp
    return out, t

def to_final(tl, raw, end=False):
    """Map a raw timestamp to the final timeline. A moment inside a cut gap snaps to the nearest kept moment
    (a note's start snaps forward, its end snaps back)."""
    for st, en, sp, f0 in tl:
        if st <= raw <= en:
            return f0 + (raw - st) / sp
    if end:
        prev = [x for x in tl if x[1] <= raw]
        return prev[-1][3] + (prev[-1][1] - prev[-1][0]) / prev[-1][2] if prev else 0.0
    nxt = [x for x in tl if x[0] >= raw]
    return nxt[0][3] if nxt else tl[-1][3] + (tl[-1][1] - tl[-1][0]) / tl[-1][2]

def note_filters(cfg, tl, tmp, out_w, crop_w, include_drafts):
    """drawbox + drawtext filters for the notes, on the final (already scaled) video."""
    f, k = [], out_w / crop_w
    reg = font(False)
    for n in cfg.get("notes", []):
        if not (n.get("approved") or include_drafts):
            continue
        a, b = to_final(tl, float(n["raw_start"])), to_final(tl, float(n["raw_end"]), end=True)
        en = f"enable='between(t,{a:.3f},{b:.3f})'"
        if "highlight" in n:
            h = n["highlight"]
            f.append(f"drawbox=x={h['x']*k:.0f}:y={h['y']*k:.0f}:w={h['w']*k:.0f}:h={h['h']*k:.0f}:color={HIGHLIGHT}@0.95:t=5:{en}")
        tf = tmp / f"note_{n['id']}.txt"
        tf.write_text(n["text"])
        fs = n.get("fontsize", 27)
        widest = max(len(l) for l in n["text"].split("\n")) * fs * 0.56 + 44   # rough width of the widest line plus padding
        if widest > out_w - 20:
            print(f"WARNING note {n['id']}: widest line is about {widest:.0f}px, wider than the {out_w}px frame; shorten it", file=sys.stderr)
        if not n.get("approved"):   # a small marker in the corner, so the layout of the note itself is not distorted
            f.append(f"drawtext=fontfile={reg}:text='DRAFT NOTE':fontsize=22:fontcolor=white:box=1:boxcolor=0xc62828@0.95:boxborderw=8:x=14:y=h-52:{en}")
        f.append(f"drawtext=fontfile={reg}:textfile='{tf}':expansion=none:fontsize={fs}:fontcolor=white:line_spacing=8"
                 f":box=1:boxcolor=0x0b1017@0.92:boxborderw=22:x=(w-text_w)/2:y=h*{n.get('y', 0.06)}:{en}")
    return f

def build(cfg, duration, gain_db, include_drafts, tmp):
    c, o = cfg["crop"], cfg["output"]
    fps, width = o.get("fps", 30), o.get("width", 720)
    tl, total = timeline(cfg, duration)
    ff = font(True)
    parts, concat_in = [], ""
    for i, ((st, en, sp, _), s) in enumerate(zip(tl, cfg["segments"])):
        shown = (en - st) / sp
        v = f"[0:v]trim=start={st}:end={en},setpts=PTS-STARTPTS,crop={c['w']}:{c['h']}:{c['x']}:{c['y']}"
        if sp != 1:
            # t is the real (un-sped) time since the segment started, because drawtext runs before the speed-up.
            clock = r"%{eif\:floor(t)\:d}"  # whole seconds of real time; no raw colon or comma, which break the filter graph
            v += (f",drawtext=fontfile={ff}:text='{sp:g}\u00d7 speed  \u00b7  {clock} s real time':fontsize=58:fontcolor=white"
                  f":box=1:boxcolor=black@0.7:boxborderw=26:x=(w-text_w)/2:y=h*{s.get('badge_y', 0.82)}")
            v += f",setpts=PTS/{sp}"
        v += f",fps={fps},scale={width}:-2,format=yuv420p[v{i}]"
        parts.append(v)
        if sp == 1:
            parts.append(f"[0:a]atrim=start={st}:end={en},asetpts=PTS-STARTPTS[a{i}]")
        else:  # sped-up waits are silent, so they stay silent; keep the audio length equal to the video length
            parts.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{shown:.3f},asetpts=PTS-STARTPTS[a{i}]")
        concat_in += f"[v{i}][a{i}]"
    parts.append(f"{concat_in}concat=n={len(tl)}:v=1:a=1[v][a]")
    nf = note_filters(cfg, tl, tmp, width, c["w"], include_drafts)
    parts.append(f"[v]{','.join(nf) if nf else 'null'}[vout]")
    # Plain gain, not loudnorm: the recording is very quiet and clean TTS needs no compression. A safety limiter and 48 kHz output.
    fade = float(o.get("audio_fade_out_s", 0))   # a short fade so a cut in the middle of speech does not click
    fade_f = f",afade=t=out:st={max(total - fade, 0):.3f}:d={fade}" if fade else ""
    parts.append(f"[a]volume={gain_db:.2f}dB,alimiter=limit=0.89:level=disabled,aresample=48000{fade_f}[aout]")
    return ";".join(parts), total, tl

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw", type=Path)
    ap.add_argument("--cuts", type=Path, default=HERE / "demo-cuts.json")
    ap.add_argument("--out", type=Path, default=HERE.parent / "media" / "demo.mp4")
    ap.add_argument("--include-drafts", action="store_true", help="also render notes that are not approved yet (marked [DRAFT]); use with --out for a preview")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and expected length, do not encode")
    a = ap.parse_args()
    cfg = json.loads(a.cuts.read_text())
    dur = probe_duration(a.raw)
    o = cfg["output"]
    lufs, peak = measure_audio(a.raw)
    target, ceiling = o.get("loudness_lufs", -16), o.get("peak_ceiling_dbfs", -1.5)
    gain = min(target - lufs, ceiling - peak)
    with tempfile.TemporaryDirectory() as td:
        graph, total, tl = build(cfg, dur, gain, a.include_drafts, Path(td))
        print(f"raw {dur:.1f}s -> expected {total:.1f}s ({int(total//60)}:{int(total%60):02d})")
        print(f"audio: raw {lufs:.1f} LUFS, peak {peak:.1f} dBFS -> gain {gain:+.1f} dB (target {target} LUFS, peak ceiling {ceiling} dBFS)")
        for (st, en, sp, f0), s in zip(tl, cfg["segments"]):
            print(f"  raw {st:7.2f} - {en:7.2f}  x{sp:g}  -> final {f0:6.2f} - {f0 + (en - st) / sp:6.2f}  {s.get('note','')}")
        for n in cfg.get("notes", []):
            on = n.get("approved") or a.include_drafts
            print(f"  note {n['id']:<10} final {to_final(tl, n['raw_start']):6.2f} - {to_final(tl, n['raw_end'], end=True):6.2f}  {'RENDERED' if on else 'skipped (draft)'}")
        if a.dry_run:
            return
        a.out.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-stats", "-y", "-i", str(a.raw), "-filter_complex", graph,
               "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "slow", "-crf", str(o.get("crf", 24)),
               "-c:a", "aac", "-b:a", f"{o.get('audio_kbps', 128)}k", "-movflags", "+faststart", str(a.out)]
        subprocess.run(cmd, check=True)
    print(f"wrote {a.out} ({a.out.stat().st_size/1e6:.1f} MB, {probe_duration(a.out):.1f}s)")

if __name__ == "__main__":
    sys.exit(main())

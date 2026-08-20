#!/usr/bin/env python3
"""Generate host listening oracles with the frozen official Pocket source/runtime.

This intentionally imports the repository-pinned source checkout and local config
prepared by experiment 0012, but writes only under experiment 0014.  It uses the
same first 10 seconds of the pinned Bria reference that sherpa used on Android.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np

TEXT = "Pocket TTS runs entirely on this Android phone using the original floating point model."
CODE_REVISION = "d108410d23eef7e01db282f9442891162dbc3db6"
WEIGHTS_REVISION = "d29db7978e464fb90cb3359ee0c69a273b9142cc"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_pcm16(path: Path, audio: np.ndarray, sample_rate: int) -> dict:
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    assert audio.size and np.isfinite(audio).all()
    pcm = np.clip(np.rint(audio * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(pcm.tobytes())
    return {
        "path": str(path),
        "sha256": sha256(path),
        "samples": int(audio.size),
        "seconds": audio.size / sample_rate,
        "sample_rate_hz": sample_rate,
        "channels": 1,
        "encoding": "PCM16",
        "finite": True,
        "peak_float": float(np.max(np.abs(audio))),
        "rms_float": float(np.sqrt(np.mean(audio * audio))),
        "clipped_sample_count_before_pcm_conversion": int(np.count_nonzero(np.abs(audio) > 1.0)),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--temperatures", type=float, nargs="+", default=[0.3, 0.7])
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--voice-mode", choices=("bria10s", "alba-state"), default="bria10s")
    p.add_argument("--out-dir", type=Path)
    args = p.parse_args()

    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    exp12 = root / "experiments/0012-pocket-onnx-vs-executorch-android"
    exp14 = root / "experiments/0014-pocket-fp-onnx-qnn-htp"
    source = exp12 / ".local/source"
    config = exp12 / ".local/english-local.yaml"
    weights = exp12 / ".local/source-assets/languages/english/model.safetensors"
    tokenizer = exp12 / ".local/source-assets/languages/english/tokenizer.model"
    bria_full = exp12 / ".local/sherpa-assets/test_wavs/bria.wav"
    bria_10s = exp14 / "work/bria-10s.wav"
    alba_state = exp12 / ".local/source-assets/languages/english/embeddings/alba.safetensors"
    out_dir = args.out_dir or exp14 / "work/quality-recovery/source-oracle"
    out_dir.mkdir(parents=True, exist_ok=True)

    assert subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip() == CODE_REVISION
    assert not subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True).strip()
    assert sha256(weights) == "be9c6b4876d3f30740a8225dfcaa2e43dc4aeb753c15272735bee16bbb4abb0a"
    assert sha256(tokenizer) == "d461765ae179566678c93091c5fa6f2984c31bbe990bf1aa62d92c64d91bc3f6"
    assert sha256(bria_full) == "85f46d6f0642f657a6bd689ddaa52d5a5f53e4314715e1032704c80917392181"
    assert sha256(bria_10s) == "5edb7efde83cf88aab25a35a88e5c48c0f01d5118ad8009b5793a30921a4bb6d"
    assert sha256(alba_state) == "e4a323e8e771f14fd669428d83e7af6d83b4d6d0f0e282c30122f04824f17b1c"

    sys.path.insert(0, str(source))
    import torch
    from pocket_tts import TTSModel

    torch.set_num_threads(1)
    t0 = time.perf_counter()
    model = TTSModel.load_model(
        config=config,
        temp=args.temperatures[0],
        lsd_decode_steps=1,
        noise_clamp=None,
        eos_threshold=-4.0,
    )
    model.eval()
    model_load_s = time.perf_counter() - t0
    v0 = time.perf_counter()
    voice_input = bria_10s if args.voice_mode == "bria10s" else alba_state
    voice_state = model.get_state_for_audio_prompt(voice_input)
    voice_conditioning_s = time.perf_counter() - v0

    outputs = []
    for temperature in args.temperatures:
        model.temp = float(temperature)
        torch.manual_seed(args.seed)
        g0 = time.perf_counter()
        audio = model.generate_audio(voice_state, TEXT, frames_after_eos=None, copy_state=True)
        generation_s = time.perf_counter() - g0
        audio_np = audio.detach().cpu().numpy().astype(np.float32, copy=False)
        temp_tag = str(temperature).replace(".", "p")
        stem = "official-source" if args.voice_mode == "bria10s" else "official-source-alba-control"
        wav_path = out_dir / f"{stem}-temp{temp_tag}-seed{args.seed}.wav"
        item = write_pcm16(wav_path, audio_np, model.sample_rate)
        item.update({"temperature": temperature, "seed": args.seed, "generation_seconds": generation_s})
        outputs.append(item)

    report = {
        "schema_version": 1,
        "status": "awaiting_human_listening_verdict",
        "route": "exact official Pocket PyTorch source/runtime on host CPU",
        "source": {
            "repository": "https://github.com/kyutai-labs/pocket-tts.git",
            "revision": CODE_REVISION,
            "checkout_clean": True,
            "config_path": str(config),
            "config_sha256": sha256(config),
            "weights_repository": "kyutai/pocket-tts-without-voice-cloning",
            "weights_revision": WEIGHTS_REVISION,
            "weights_sha256": sha256(weights),
            "tokenizer_sha256": sha256(tokenizer),
            "torch_version": torch.__version__,
            "numpy_version": np.__version__,
        },
        "contract": {
            "text": TEXT,
            "text_sha256": hashlib.sha256(TEXT.encode()).hexdigest(),
            "voice_mode": args.voice_mode,
            "voice_input_sha256": sha256(voice_input),
            "voice_reference_full_sha256": sha256(bria_full) if args.voice_mode == "bria10s" else None,
            "voice_reference_policy": "same first 10.0 seconds used by the physical sherpa route" if args.voice_mode == "bria10s" else "official pinned precomputed Alba state; voice-conditioning control",
            "voice_reference_10s_sha256": sha256(bria_10s) if args.voice_mode == "bria10s" else None,
            "alba_state_sha256": sha256(alba_state) if args.voice_mode == "alba-state" else None,
            "seed": args.seed,
            "temperatures": args.temperatures,
            "lsd_decode_steps": 1,
            "noise_clamp": None,
            "eos_threshold": -4.0,
            "frames_after_eos": "official model-derived behavior",
        },
        "timing": {"model_load_seconds": model_load_s, "voice_conditioning_seconds": voice_conditioning_s},
        "outputs": outputs,
        "claim_boundary": "These are source-runtime candidates, not quality-valid oracles until Moritz listens and accepts one.",
    }
    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

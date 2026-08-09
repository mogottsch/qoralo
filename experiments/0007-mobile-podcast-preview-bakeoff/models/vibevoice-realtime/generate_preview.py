#!/usr/bin/env python3
"""Capture the locked Realtime preview. Invoke only through generate-preview.sh."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import sys
import threading
import time
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
from preflight_common import RssSampler

RATE = 24_000
SEED = 0
AUDIBLE_RMS = 10 ** (-50 / 20)
FRAME_SAMPLES = RATE // 100


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def first_audible_frame(samples: np.ndarray) -> int | None:
    for offset in range(0, max(0, samples.size - FRAME_SAMPLES + 1), FRAME_SAMPLES):
        frame = samples[offset:offset + FRAME_SAMPLES].astype(np.float64)
        if float(np.sqrt(np.mean(frame * frame))) >= AUDIBLE_RMS:
            return offset
    return None


def exclusive_npy(path: Path, samples: np.ndarray) -> None:
    with path.open("xb") as stream:
        np.save(stream, np.asarray(samples, dtype=np.float32), allow_pickle=False)


def wav_bytes(samples: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    # This matches soundfile's default WAV subtype used by the official file demo.
    sf.write(buffer, samples, RATE, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def main() -> None:
    if os.environ.get("VIBEVOICE_PREVIEW_GATE") != "task-6:generation-realtime":
        raise SystemExit("refusing ungated generation; use generate-preview.sh")

    artifacts = Path(os.environ.get("VIBEVOICE_REALTIME_ARTIFACTS", HERE / "artifacts"))
    source = artifacts / "source/microsoft-vibevoice"
    model_path = artifacts / "model/microsoft-VibeVoice-Realtime-0.5B"
    tokenizer_path = artifacts / "model/Qwen2.5-0.5B-tokenizer"
    voice_path = source / "demo/voices/streaming_model/en-Grace_woman.pt"
    transcript_path = ROOT / "protocol/transcript.txt"
    capture_path = ROOT / "artifacts/raw/realtime/v2/capture.json"
    raw_dir = capture_path.parent
    raw_dir.mkdir(parents=True, exist_ok=True)
    if any(raw_dir.iterdir()):
        raise SystemExit(f"raw capture directory must be empty (never overwrite raw files): {raw_dir}")

    expected_transcript_hash = "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"
    transcript_bytes = transcript_path.read_bytes()
    if hashlib.sha256(transcript_bytes).hexdigest() != expected_transcript_hash:
        raise RuntimeError("locked transcript hash mismatch")
    transcript = transcript_bytes.decode("utf-8")

    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    sys.path.insert(0, str(source))
    import torch
    from transformers.cache_utils import DynamicCache
    from transformers.modeling_outputs import BaseModelOutputWithPast
    from vibevoice.modular.modeling_vibevoice_streaming_inference import VibeVoiceStreamingForConditionalGenerationInference
    from vibevoice.modular.modular_vibevoice_text_tokenizer import VibeVoiceTextTokenizerFast
    from vibevoice.modular.streamer import AudioStreamer
    from vibevoice.processor.vibevoice_streaming_processor import VibeVoiceStreamingProcessor
    from vibevoice.processor.vibevoice_tokenizer_processor import VibeVoiceTokenizerProcessor

    if not torch.cuda.is_available():
        raise RuntimeError("the pinned Realtime preview requires CUDA")
    sampler = RssSampler(interval_seconds=0.02).start()
    baseline_rss = sampler.sample_now()
    sampler.mark("model_load")
    tokenizer = VibeVoiceTextTokenizerFast.from_pretrained(tokenizer_path, local_files_only=True)
    processor = VibeVoiceStreamingProcessor(
        tokenizer=tokenizer,
        audio_processor=VibeVoiceTokenizerProcessor(sampling_rate=RATE, normalize_audio=True, target_dB_FS=-25, eps=1e-6),
        speech_tok_compress_ratio=3200,
        db_normalize=True,
    )
    model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
        model_path, local_files_only=True, torch_dtype=torch.bfloat16, device_map="cuda", attn_implementation="sdpa"
    ).eval()
    model.set_ddpm_inference_steps(num_steps=5)
    with torch.serialization.safe_globals([BaseModelOutputWithPast, DynamicCache]):
        prompt = torch.load(voice_path, map_location="cuda", weights_only=True)
    sampler.mark("loaded")

    inputs = processor.process_input_with_cached_prompt(
        text=transcript, cached_prompt=prompt, padding=True, return_tensors="pt", return_attention_mask=True
    )
    inputs = {key: value.to("cuda") if torch.is_tensor(value) else value for key, value in inputs.items()}

    def generate_once(preserve: bool) -> dict[str, object]:
        torch.manual_seed(SEED)
        torch.cuda.manual_seed_all(SEED)
        streamer = AudioStreamer(batch_size=1, stop_signal=None, timeout=None)
        errors: list[BaseException] = []

        def run() -> None:
            try:
                with torch.inference_mode():
                    model.generate(
                        **inputs, max_new_tokens=None, cfg_scale=1.5, tokenizer=processor.tokenizer,
                        generation_config={"do_sample": False}, audio_streamer=streamer, verbose=False,
                        all_prefilled_outputs=copy.deepcopy(prompt),
                    )
            except BaseException as exc:
                errors.append(exc)
                streamer.end()

        torch.cuda.synchronize()
        started = time.monotonic()
        thread = threading.Thread(target=run, name="vibevoice-generation")
        thread.start()
        chunks: list[np.ndarray] = []
        chunk_records: list[dict[str, object]] = []
        first_output = None
        first_audible = None
        generated_samples = 0
        sampler.mark("primary_generation" if preserve else "determinism_repeat")
        for index, tensor in enumerate(streamer.get_stream(0)):
            arrived = time.monotonic() - started
            chunk = tensor.detach().cpu().to(torch.float32).numpy().reshape(-1)
            if first_output is None:
                first_output = arrived
            audible_offset = first_audible_frame(chunk)
            if first_audible is None and audible_offset is not None:
                first_audible = arrived
            record = {
                "index": index, "sample_count": int(chunk.size), "arrival_seconds": arrived,
                "audio_start_seconds": generated_samples / RATE,
                "first_audible_sample_in_chunk": audible_offset,
                "pcm_f32le_sha256": hashlib.sha256(chunk.astype("<f4", copy=False).tobytes()).hexdigest(),
            }
            if preserve:
                chunk_path = raw_dir / f"chunk-{index:04d}.npy"
                exclusive_npy(chunk_path, chunk)
                record.update(path=str(chunk_path.relative_to(ROOT)), bytes=chunk_path.stat().st_size, sha256=sha256_file(chunk_path))
            chunk_records.append(record)
            chunks.append(chunk)
            generated_samples += int(chunk.size)
        thread.join()
        torch.cuda.synchronize()
        wall = time.monotonic() - started
        if errors:
            raise errors[0]
        if not chunks:
            raise RuntimeError("model returned no streaming audio")
        waveform = np.concatenate(chunks).astype(np.float32, copy=False)
        return {
            "wall_seconds": wall, "api_first_output_seconds": first_output,
            "first_audible_output_seconds": first_audible, "sample_count": int(waveform.size),
            "pcm_f32le_sha256": hashlib.sha256(waveform.astype("<f4", copy=False).tobytes()).hexdigest(),
            "wav_sha256": hashlib.sha256(wav_bytes(waveform)).hexdigest(), "chunks": chunk_records,
            "waveform": waveform,
        }

    primary = generate_once(preserve=True)
    raw_wav = raw_dir / "assembled-native.wav"
    with raw_wav.open("xb") as stream:
        stream.write(wav_bytes(primary.pop("waveform")))
    primary["assembled_wav"] = {
        "path": str(raw_wav.relative_to(ROOT)), "bytes": raw_wav.stat().st_size, "sha256": sha256_file(raw_wav),
        "sample_rate_hz": RATE, "channels": 1, "sample_format": "PCM_S16LE",
    }
    repeat = generate_once(preserve=False)
    repeat.pop("waveform")
    rss = sampler.stop()
    capture = {
        "schema_version": 1, "status": "captured", "seed": SEED,
        "seed_support": "The official demo has no seed option; task 6 explicitly seeds torch CPU and all CUDA generators. Token sampling is disabled; diffusion uses torch.randn.",
        "determinism": {
            "repeat_pcm_match": primary["pcm_f32le_sha256"] == repeat["pcm_f32le_sha256"],
            "repeat_wav_match": primary["wav_sha256"] == repeat["wav_sha256"],
            "primary_pcm_f32le_sha256": primary["pcm_f32le_sha256"],
            "repeat_pcm_f32le_sha256": repeat["pcm_f32le_sha256"],
            "repeat_wall_seconds": repeat["wall_seconds"],
        },
        "baseline_rss_bytes": baseline_rss, "rss": rss, "primary": primary,
        "transcript_sha256": expected_transcript_hash, "voice_sha256": sha256_file(voice_path),
        "device": torch.cuda.get_device_name(),
    }
    capture_path.write_text(json.dumps(capture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"capture": str(capture_path), "raw_wav": str(raw_wav), "samples": primary["sample_count"]}, sort_keys=True))


if __name__ == "__main__":
    main()

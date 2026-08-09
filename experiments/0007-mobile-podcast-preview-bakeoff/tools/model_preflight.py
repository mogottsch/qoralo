#!/usr/bin/env python3
"""Bounded, non-preview inference worker. Invoke only through run-preflights.sh."""
from __future__ import annotations

import argparse
import copy
import ctypes.util
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from preflight_common import RssSampler

PROBE_TEXT = "Memory preflight."


def realtime(sampler: RssSampler) -> dict[str, object]:
    artifacts = ROOT / "models/vibevoice-realtime/artifacts"
    source = artifacts / "source/microsoft-vibevoice"
    sys.path.insert(0, str(source))
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    import torch
    from transformers.cache_utils import DynamicCache
    from transformers.modeling_outputs import BaseModelOutputWithPast
    from vibevoice.modular.modeling_vibevoice_streaming_inference import VibeVoiceStreamingForConditionalGenerationInference
    from vibevoice.modular.modular_vibevoice_text_tokenizer import VibeVoiceTextTokenizerFast
    from vibevoice.processor.vibevoice_streaming_processor import VibeVoiceStreamingProcessor
    from vibevoice.processor.vibevoice_tokenizer_processor import VibeVoiceTokenizerProcessor

    if not torch.cuda.is_available():
        raise RuntimeError("Realtime preflight requires CUDA on the pinned host")
    tokenizer = VibeVoiceTextTokenizerFast.from_pretrained(artifacts / "model/Qwen2.5-0.5B-tokenizer", local_files_only=True)
    processor = VibeVoiceStreamingProcessor(tokenizer=tokenizer, audio_processor=VibeVoiceTokenizerProcessor(
        sampling_rate=24000, normalize_audio=True, target_dB_FS=-25, eps=1e-6), speech_tok_compress_ratio=3200,
        db_normalize=True)
    model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
        artifacts / "model/microsoft-VibeVoice-Realtime-0.5B", local_files_only=True,
        torch_dtype=torch.bfloat16, device_map="cuda", attn_implementation="sdpa").eval()
    model.set_ddpm_inference_steps(num_steps=5)
    with torch.serialization.safe_globals([BaseModelOutputWithPast, DynamicCache]):
        prompt = torch.load(source / "demo/voices/streaming_model/en-Grace_woman.pt", map_location="cuda", weights_only=True)
    sampler.mark("loaded")
    durations = []
    samples = []
    for index, phase in enumerate(("cold_short_inference", "warm_short_inference")):
        inputs = processor.process_input_with_cached_prompt(text=PROBE_TEXT, cached_prompt=prompt, padding=True,
            return_tensors="pt", return_attention_mask=True)
        inputs = {key: value.to("cuda") if torch.is_tensor(value) else value for key, value in inputs.items()}
        sampler.mark(phase)
        started = time.monotonic()
        with torch.inference_mode():
            output = model.generate(**inputs, max_new_tokens=20, cfg_scale=1.5, tokenizer=processor.tokenizer,
                generation_config={"do_sample": False}, verbose=False, all_prefilled_outputs=copy.deepcopy(prompt))
        torch.cuda.synchronize()
        durations.append(time.monotonic() - started)
        speech = output.speech_outputs[0] if output.speech_outputs else None
        samples.append(int(speech.numel()) if speech is not None else 0)
        sampler.sample_now()
        del output, inputs
    return {"inference_wall_seconds": durations, "discarded_audio_samples": samples,
            "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated(), "device": torch.cuda.get_device_name()}


def pocket(sampler: RssSampler) -> dict[str, object]:
    source = ROOT / "artifacts/setup/pocket-tts/source"
    sys.path.insert(0, str(source))
    import torch
    from pocket_tts import TTSModel
    model = TTSModel.load_model(language="english", temp=0.3)
    state = model.get_state_for_audio_prompt("alba")
    sampler.mark("loaded")
    durations, samples = [], []
    for phase in ("cold_short_inference", "warm_short_inference"):
        torch.manual_seed(0)
        sampler.mark(phase)
        started = time.monotonic()
        chunks = list(model.generate_audio_stream(state, PROBE_TEXT, frames_after_eos=1, copy_state=True))
        durations.append(time.monotonic() - started)
        samples.append(sum(int(chunk.numel()) for chunk in chunks))
        sampler.sample_now()
        del chunks
    return {"inference_wall_seconds": durations, "discarded_audio_samples": samples,
            "device": "cpu", "sample_rate_hz": model.sample_rate}


def kokoro(sampler: RssSampler) -> dict[str, object]:
    artifacts = ROOT / "artifacts/kokoro"
    snapshot = artifacts / "snapshot"
    espeak_library = os.environ.get("KOKORO_ESPEAK_LIBRARY") or ctypes.util.find_library("espeak-ng")
    espeak_data = os.environ.get("KOKORO_ESPEAK_DATA", "/usr/share/espeak-ng-data")
    if not espeak_library or not Path(espeak_data).is_dir():
        raise RuntimeError("Kokoro preflight requires eSpeak library and data")
    import espeakng_loader
    espeakng_loader.get_library_path = lambda: espeak_library
    espeakng_loader.get_data_path = lambda: espeak_data
    import torch
    from kokoro import KModel, KPipeline
    torch.use_deterministic_algorithms(True)
    model = KModel(repo_id="hexgrad/Kokoro-82M", config=str(snapshot / "config.json"),
        model=str(snapshot / "kokoro-v1_0.pth")).cpu().eval()
    pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M", model=model, device="cpu")
    sampler.mark("loaded")
    durations, samples = [], []
    for phase in ("cold_short_inference", "warm_short_inference"):
        torch.manual_seed(0)
        sampler.mark(phase)
        started = time.monotonic()
        chunks = list(pipeline(PROBE_TEXT, voice=str(snapshot / "voices/af_heart.pt"), speed=1.0))
        durations.append(time.monotonic() - started)
        samples.append(sum(int(result.audio.numel()) for result in chunks if result.audio is not None))
        sampler.sample_now()
        del chunks
    return {"inference_wall_seconds": durations, "discarded_audio_samples": samples,
            "device": "cpu", "sample_rate_hz": 24000}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", choices=("realtime", "pocket", "kokoro"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if os.environ.get("PREVIEW_RESOURCE_GRANT_KIND") != "preflight":
        raise SystemExit("refusing ungated preflight; use run-preflights.sh")
    sampler = RssSampler().start()
    sampler.sample_now()
    sampler.mark("cold_load")
    started = time.monotonic()
    result = globals()[args.model](sampler)
    result.update(sampler.stop())
    result.update({"model": args.model, "probe_text": PROBE_TEXT, "total_wall_seconds": time.monotonic() - started,
        "audio_disposition": "discarded_in_memory_not_written_not_a_preview", "status": "passed"})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

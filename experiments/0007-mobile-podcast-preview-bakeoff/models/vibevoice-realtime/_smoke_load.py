#!/usr/bin/env python3
"""Internal load probe. Invoke only through smoke-load.sh (the resource gate)."""
from __future__ import annotations
import hashlib, json, os, sys, time
from pathlib import Path
if os.environ.get("VIBEVOICE_SMOKE_GATE") != "task-2":
    raise SystemExit("refusing ungated model load; use smoke-load.sh")
HERE = Path(__file__).resolve().parent
ARTIFACTS = Path(os.environ.get("VIBEVOICE_REALTIME_ARTIFACTS", HERE / "artifacts"))
MODEL = ARTIFACTS / "model/microsoft-VibeVoice-Realtime-0.5B"
TOKENIZER = ARTIFACTS / "model/Qwen2.5-0.5B-tokenizer"
SOURCE = ARTIFACTS / "source/microsoft-vibevoice"
sys.path.insert(0, str(SOURCE))
os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
import torch
from transformers.cache_utils import DynamicCache
from transformers.modeling_outputs import BaseModelOutputWithPast
from vibevoice.modular.modeling_vibevoice_streaming_inference import VibeVoiceStreamingForConditionalGenerationInference
from vibevoice.modular.modular_vibevoice_text_tokenizer import VibeVoiceTextTokenizerFast
from vibevoice.processor.vibevoice_streaming_processor import VibeVoiceStreamingProcessor
from vibevoice.processor.vibevoice_tokenizer_processor import VibeVoiceTokenizerProcessor

def main() -> None:
    if not torch.cuda.is_available(): raise SystemExit("CUDA smoke load required on this pinned host")
    start = time.monotonic()
    # The official preprocessor points at a floating Qwen repo. Assemble the same
    # processor from our independently pinned local tokenizer to forbid that download.
    tokenizer = VibeVoiceTextTokenizerFast.from_pretrained(TOKENIZER, local_files_only=True)
    processor = VibeVoiceStreamingProcessor(
        tokenizer=tokenizer,
        audio_processor=VibeVoiceTokenizerProcessor(sampling_rate=24000, normalize_audio=True, target_dB_FS=-25, eps=1e-6),
        speech_tok_compress_ratio=3200, db_normalize=True,
    )
    model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
        MODEL, local_files_only=True, torch_dtype=torch.bfloat16, device_map="cuda", attn_implementation="sdpa"
    )
    model.eval(); model.set_ddpm_inference_steps(num_steps=5)
    voice = SOURCE / "demo/voices/streaming_model/en-Grace_woman.pt"
    with torch.serialization.safe_globals([BaseModelOutputWithPast, DynamicCache]):
        prompt = torch.load(voice, map_location="cuda", weights_only=True)
    result = {
        "status": "passed", "scope": "load_only_no_generation", "gate": "smoke-load",
        "model_revision": (MODEL / ".model-revision").read_text().strip(),
        "tokenizer_revision": (TOKENIZER / ".model-revision").read_text().strip(),
        "source_revision": os.popen(f"git -C '{SOURCE}' rev-parse HEAD").read().strip(),
        "voice": "en-Grace_woman.pt", "voice_sha256": hashlib.sha256(voice.read_bytes()).hexdigest(),
        "device": torch.cuda.get_device_name(), "dtype": str(next(model.parameters()).dtype),
        "attention": "sdpa", "offline_local_only": True,
        "processor_sample_rate_hz": processor.audio_processor.sampling_rate,
        "prompt_sections": sorted(prompt), "load_wall_seconds": time.monotonic() - start,
        "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
    }
    out = ARTIFACTS / "smoke-load.json"; out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
if __name__ == "__main__": main()

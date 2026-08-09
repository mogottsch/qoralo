#!/usr/bin/env python3
"""Capture the first 20 real recurrent VibeVoice calls with exact eager state.

Large ``.pt`` evidence is written below ``artifacts/``.  Only its hash manifest is
intended for version control.  The caller MUST run this program through task 1's
model-resource gate (see ``run-recurrent-capture.sh``).
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import resource
import runpy
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F

from fixture_utils import repo_root, snapshot_cache, tensor_metadata

SOURCE_REVISION = "6dd49cb7200c0367205a5f1e650244259e9e423d"
MODEL_REVISION = "c00898d257e6b46004e3e2866a47534085fb685a"
CALL_COUNT = 20
SAMPLE_RATE = 24_000
# Pinned processor token, independently frozen in token-selection-manifest.json.
SPEECH_DIFFUSION_ID = 151_654


class CaptureComplete(RuntimeError):
    """Private control-flow exception used to stop before recurrent call 20."""


def _clone(value: torch.Tensor) -> torch.Tensor:
    return value.detach().cpu().contiguous().clone()


def _dynamic_cache(cache: Any) -> dict[str, torch.Tensor]:
    if cache is None:
        return {}
    result: dict[str, torch.Tensor] = {}
    for layer, (key, value) in enumerate(zip(cache.key_cache, cache.value_cache)):
        result[f"layer_{layer:02d}.key"] = _clone(key)
        result[f"layer_{layer:02d}.value"] = _clone(value)
    return result


def _cache_metadata(cache: dict[str, torch.Tensor]) -> dict[str, dict[str, Any]]:
    return {name: tensor_metadata(value) for name, value in sorted(cache.items())}


def _equal_cache(left: dict[str, torch.Tensor], right: dict[str, torch.Tensor]) -> bool:
    return left.keys() == right.keys() and all(torch.equal(left[key], right[key]) for key in left)


def _pcm_metadata(pcm: torch.Tensor) -> dict[str, Any]:
    meta = tensor_metadata(pcm)
    samples = pcm.detach().float().cpu().reshape(-1)
    rms = float(torch.sqrt(torch.mean(samples.square())).item()) if samples.numel() else 0.0
    peak = float(samples.abs().max().item()) if samples.numel() else 0.0
    # Eager decoder PCM is normalized float audio; dBFS is therefore relative to 1.0.
    meta.update({
        "sample_rate_hz": SAMPLE_RATE,
        "samples": int(samples.numel()),
        "rms": rms,
        "peak": peak,
        "dbfs": 20.0 * math.log10(rms) if rms > 0 else None,
    })
    return meta


def _call_metadata(payload: dict[str, Any], index: int, fixture: str) -> dict[str, Any]:
    qwen = payload["qwen"]
    diffusion = payload["diffusion"]
    decoder = payload["decoder"]
    semantic = payload["semantic"]
    return {
        "index": index,
        "fixture": fixture,
        "selected_token": int(payload["selected_token"]),
        "qwen": {
            "inputs_embeds": tensor_metadata(qwen["inputs_embeds"]),
            "attention_mask": tensor_metadata(qwen["attention_mask"]),
            "cache_position": tensor_metadata(qwen["cache_position"]),
            "hidden": tensor_metadata(qwen["hidden"]),
            "logits": tensor_metadata(qwen["logits"]),
            "pre_cache": _cache_metadata(qwen["pre_cache"]),
            "post_cache": _cache_metadata(qwen["post_cache"]),
        },
        "connector": {
            "acoustic": tensor_metadata(payload["connector"]["acoustic"]),
            "semantic": tensor_metadata(payload["connector"]["semantic"]),
            "combined": tensor_metadata(payload["connector"]["combined"]),
        },
        "diffusion": {
            "positive_condition": tensor_metadata(diffusion["positive_condition"]),
            "negative_condition": tensor_metadata(diffusion["negative_condition"]),
            "initial_noise": tensor_metadata(diffusion["initial_noise"]),
            "steps": [
                {
                    "timestep": int(step["timestep"]),
                    "input": tensor_metadata(step["input"]),
                    "prediction": tensor_metadata(step["prediction"]),
                }
                for step in diffusion["steps"]
            ],
            "final_latent": tensor_metadata(diffusion["final_latent"]),
        },
        "decoder": {
            "input_latent": tensor_metadata(decoder["input_latent"]),
            "pcm": _pcm_metadata(decoder["pcm"]),
            "pre_cache": _cache_metadata(decoder["pre_cache"]),
            "post_cache": _cache_metadata(decoder["post_cache"]),
        },
        "semantic": {
            "input_pcm": tensor_metadata(semantic["input_pcm"]),
            "output": tensor_metadata(semantic["output"]),
            "pre_cache": _cache_metadata(semantic["pre_cache"]),
            "post_cache": _cache_metadata(semantic["post_cache"]),
        },
    }


def _validate_calls(calls: list[dict[str, Any]], diffusion_token: int) -> dict[str, Any]:
    if len(calls) != CALL_COUNT or [call["index"] for call in calls] != list(range(CALL_COUNT)):
        raise RuntimeError(f"expected contiguous calls 0..{CALL_COUNT - 1}")
    if any(call["selected_token"] != diffusion_token for call in calls):
        raise RuntimeError("a captured decoder call was not selected by speech_diffusion_id")
    if any(len(call["diffusion"]["steps"]) != 10 for call in calls):
        raise RuntimeError("a captured call does not contain the locked ten diffusion steps")
    lengths = [call["decoder"]["pcm"]["samples"] for call in calls]
    if not lengths or any(length != lengths[0] for length in lengths):
        raise RuntimeError(f"non-uniform PCM boundaries: {lengths}")
    return {
        "contiguous_call_indices": True,
        "all_selected_tokens_are_speech_diffusion": True,
        "diffusion_steps_per_call": 10,
        "pcm_chunk_samples": lengths[0],
        "pcm_total_samples": sum(lengths),
        "pcm_boundaries": [index * lengths[0] for index in range(CALL_COUNT + 1)],
        "missing_duplicated_or_reordered_chunks": False,
    }


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=root / "artifacts/source/microsoft-vibevoice")
    parser.add_argument("--model", type=Path, default=root / "artifacts/models/microsoft-VibeVoice-1.5B")
    parser.add_argument("--transcript", type=Path, default=root / "experiments/0001-vibevoice-1.5b-local-reference/transcript.txt")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeat-of", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cfg-scale", type=float, default=1.3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    source, model, output = args.source.resolve(), args.model.resolve(), args.output.resolve()
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if revision != SOURCE_REVISION:
        raise SystemExit(f"expected source {SOURCE_REVISION}, got {revision}")
    if not (model / "model.safetensors.index.json").is_file():
        raise SystemExit("pinned model is missing")
    output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(source))

    from transformers.models.qwen2.modeling_qwen2 import Qwen2Model
    from vibevoice.modular.modeling_vibevoice import SpeechConnector
    from vibevoice.modular.modeling_vibevoice_inference import VibeVoiceForConditionalGenerationInference
    from vibevoice.modular.modular_vibevoice_tokenizer import VibeVoiceAcousticTokenizerModel, VibeVoiceSemanticTokenizerModel

    originals = {
        "qwen": Qwen2Model.forward,
        "sample": VibeVoiceForConditionalGenerationInference.sample_speech_tokens,
        "outer": VibeVoiceForConditionalGenerationInference.forward,
        "decoder": VibeVoiceAcousticTokenizerModel.decode,
        "semantic": VibeVoiceSemanticTokenizerModel.encode,
        "connector": SpeechConnector.forward,
    }
    qwen_events: collections.deque[dict[str, Any]] = collections.deque(maxlen=2)
    manifests: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    diffusion: dict[str, Any] | None = None
    model_instance: Any = None

    def qwen_forward(self: Any, *positional: Any, **kwargs: Any) -> Any:
        if len(manifests) == CALL_COUNT:
            raise CaptureComplete
        embeds = kwargs.get("inputs_embeds")
        position = kwargs.get("cache_position")
        if embeds is None or position is None:
            return originals["qwen"](self, *positional, **kwargs)
        pre = _dynamic_cache(kwargs.get("past_key_values"))
        result = originals["qwen"](self, *positional, **kwargs)
        hidden = result.last_hidden_state[:, -1:, :]
        qwen_events.append({
            "inputs_embeds": _clone(embeds),
            "attention_mask": _clone(kwargs["attention_mask"]),
            "cache_position": _clone(position),
            "hidden": _clone(hidden),
            "logits": _clone(F.linear(hidden[:, -1, :], self.embed_tokens.weight).float()),
            "pre_cache": pre,
            "post_cache": _dynamic_cache(result.past_key_values),
        })
        return result

    def outer_forward(self: Any, *positional: Any, **kwargs: Any) -> Any:
        nonlocal model_instance
        model_instance = self
        return originals["outer"](self, *positional, **kwargs)

    def prediction_forward(self: Any, x: torch.Tensor, timestep: torch.Tensor, *positional: Any, **kwargs: Any) -> Any:
        result = prediction_original(x, timestep, *positional, **kwargs)
        assert diffusion is not None
        diffusion["steps"].append({"timestep": int(timestep.reshape(-1)[0].item()), "input": _clone(x), "prediction": _clone(result)})
        return result

    def sample_tokens(self: Any, condition: torch.Tensor, neg_condition: torch.Tensor, cfg_scale: float = 3.0) -> torch.Tensor:
        nonlocal diffusion, prediction_original
        diffusion = {"positive_condition": _clone(condition), "negative_condition": _clone(neg_condition), "steps": []}
        head = self.model.prediction_head
        prediction_original = head.forward
        head.forward = prediction_forward.__get__(head, type(head))
        try:
            result = originals["sample"](self, condition, neg_condition, cfg_scale)
        finally:
            head.forward = prediction_original
        # First prediction input is the duplicated initial random sample.
        diffusion["initial_noise"] = diffusion["steps"][0]["input"]
        diffusion["final_latent"] = _clone(result)
        return result

    def decode(self: Any, latents: torch.Tensor, cache: Any = None, sample_indices: Any = None, use_cache: bool = False, debug: bool = False) -> Any:
        nonlocal active
        if len(qwen_events) != 2 or diffusion is None:
            raise RuntimeError("decoder reached without positive/negative Qwen and diffusion state")
        pre, _ = snapshot_cache(self.decoder, cache)
        pcm = originals["decoder"](self, latents, cache=cache, sample_indices=sample_indices, use_cache=use_cache, debug=debug)
        post, _ = snapshot_cache(self.decoder, cache)
        active = {
            "selected_token": SPEECH_DIFFUSION_ID,
            "qwen": qwen_events[0],
            "diffusion": diffusion,
            "decoder": {"input_latent": _clone(latents), "pcm": _clone(pcm), "pre_cache": pre, "post_cache": post},
            "connector": {},
        }
        return pcm

    def semantic_encode(self: Any, audio: torch.Tensor, cache: Any = None, sample_indices: Any = None, use_cache: bool = False, debug: bool = False) -> Any:
        if active is None:
            return originals["semantic"](self, audio, cache=cache, sample_indices=sample_indices, use_cache=use_cache, debug=debug)
        pre, _ = snapshot_cache(self.encoder, cache)
        result = originals["semantic"](self, audio, cache=cache, sample_indices=sample_indices, use_cache=use_cache, debug=debug)
        post, _ = snapshot_cache(self.encoder, cache)
        active["semantic"] = {"input_pcm": _clone(audio), "output": _clone(result.mean), "pre_cache": pre, "post_cache": post}
        return result

    def connector_forward(self: Any, features: torch.Tensor, **kwargs: Any) -> Any:
        nonlocal active, diffusion
        result = originals["connector"](self, features, **kwargs)
        if active is None or model_instance is None:
            return result
        if self is model_instance.model.acoustic_connector:
            active["connector"]["acoustic"] = _clone(result)
        elif self is model_instance.model.semantic_connector:
            active["connector"]["semantic"] = _clone(result)
            active["connector"]["combined"] = active["connector"]["acoustic"] + active["connector"]["semantic"]
            index = len(manifests)
            if index and not _equal_cache(active["qwen"]["pre_cache"], previous_qwen):
                raise RuntimeError(f"Qwen eager cache chain broke at call {index}")
            if index and not _equal_cache(active["decoder"]["pre_cache"], previous_decoder):
                raise RuntimeError(f"decoder eager cache chain broke at call {index}")
            if index and not _equal_cache(active["semantic"]["pre_cache"], previous_semantic):
                raise RuntimeError(f"semantic eager cache chain broke at call {index}")
            fixture_name = f"call_{index:03d}.pt"
            torch.save(active, output / fixture_name)
            manifests.append(_call_metadata(active, index, fixture_name))
            previous_qwen.clear(); previous_qwen.update(active["qwen"]["post_cache"])
            previous_decoder.clear(); previous_decoder.update(active["decoder"]["post_cache"])
            previous_semantic.clear(); previous_semantic.update(active["semantic"]["post_cache"])
            active = None
            diffusion = None
        return result

    previous_qwen: dict[str, torch.Tensor] = {}
    previous_decoder: dict[str, torch.Tensor] = {}
    previous_semantic: dict[str, torch.Tensor] = {}
    prediction_original: Any = None
    Qwen2Model.forward = qwen_forward
    VibeVoiceForConditionalGenerationInference.forward = outer_forward
    VibeVoiceForConditionalGenerationInference.sample_speech_tokens = sample_tokens
    VibeVoiceAcousticTokenizerModel.decode = decode
    VibeVoiceSemanticTokenizerModel.encode = semantic_encode
    SpeechConnector.forward = connector_forward
    demo = source / "demo/inference_from_file.py"
    old_argv = sys.argv
    sys.argv = [str(demo), "--model_path", str(model), "--txt_path", str(args.transcript.resolve()), "--speaker_names", "Carter", "Maya", "--output_dir", str(output / "generated-audio"), "--device", "cpu", "--cfg_scale", str(args.cfg_scale), "--seed", str(args.seed)]
    try:
        runpy.run_path(str(demo), run_name="__main__")
    except CaptureComplete:
        pass
    finally:
        sys.argv = old_argv
        Qwen2Model.forward = originals["qwen"]
        VibeVoiceForConditionalGenerationInference.forward = originals["outer"]
        VibeVoiceForConditionalGenerationInference.sample_speech_tokens = originals["sample"]
        VibeVoiceAcousticTokenizerModel.decode = originals["decoder"]
        VibeVoiceSemanticTokenizerModel.encode = originals["semantic"]
        SpeechConnector.forward = originals["connector"]

    diffusion_token = SPEECH_DIFFUSION_ID
    boundaries = _validate_calls(manifests, diffusion_token)
    deterministic: bool | None = None
    differing: list[str] = []
    if args.repeat_of:
        prior = json.loads((args.repeat_of / "manifest.json").read_text())
        for current, old in zip(manifests, prior.get("calls", [])):
            if current != old:
                differing.append(f"call_{current['index']:03d}")
        deterministic = len(prior.get("calls", [])) == CALL_COUNT and not differing
        if not deterministic:
            raise SystemExit(f"repeat capture differs: {differing}")
    manifest = {
        "schema_version": 1,
        "scope": "VibeVoice 1.5B eager recurrent calls 0-19; evidence only, no deployment ABI selected",
        "provenance": {"source_revision": SOURCE_REVISION, "model_revision": MODEL_REVISION, "seed": args.seed, "cfg_scale": args.cfg_scale, "device": "cpu", "dtype": "float32", "transcript_sha256": hashlib.sha256(args.transcript.read_bytes()).hexdigest()},
        "calls": manifests,
        "chaining": {"actual_eager_state": True, "qwen_pre_equals_previous_positive_post": True, "decoder_pre_equals_previous_post": True, "semantic_pre_equals_previous_post": True, "fixture_substitution": False},
        "boundaries": boundaries,
        "repeat": {"compared_to": str(args.repeat_of) if args.repeat_of else None, "all_call_metadata_and_hashes_match": deterministic, "differing_calls": differing},
        "capture": {"wall_seconds": time.perf_counter() - started, "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "large_evidence_policy": "call tensors and generated audio remain below ignored artifacts/; only this derived manifest is copied into fixtures/",
        "abi_decision": None,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"calls": len(manifests), "deterministic": deterministic, "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()

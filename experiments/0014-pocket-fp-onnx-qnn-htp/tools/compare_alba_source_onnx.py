#!/usr/bin/env python3
"""Compare the valid pinned-Alba fixed-voice route from official source to 0012 ONNX.

Positive-temperature RNG implementations differ, so recurrent operator comparison
uses shared explicit noise fixtures.  A temperature-zero full synthesis isolates
all deterministic downstream boundaries through Mimi decode.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

TEXT = "Pocket TTS runs entirely on this Android phone using the original floating point model."


def metrics(a, b) -> dict:
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    assert a.shape == b.shape
    d = np.abs(a - b)
    return {
        "shape": list(a.shape),
        "max_abs": float(d.max(initial=0.0)),
        "mean_abs": float(d.mean()) if d.size else 0.0,
        "rmse": float(np.sqrt(np.mean(d * d))) if d.size else 0.0,
        "source_finite": bool(np.isfinite(a).all()),
        "onnx_finite": bool(np.isfinite(b).all()),
    }


def update_onnx_state(state, result, manifest, offset=2):
    for entry in manifest:
        state[entry["input_name"]] = result[offset + entry["index"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=70)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    e12 = root / "experiments/0012-pocket-onnx-vs-executorch-android"
    e14 = root / "experiments/0014-pocket-fp-onnx-qnn-htp"
    source = e12 / ".local/source"
    bundle = e12 / ".local/onnx-controlled"
    config = e12 / ".local/english-local.yaml"
    alba = e12 / ".local/source-assets/languages/english/embeddings/alba.safetensors"
    runtime = e12 / ".local/pocket_tts_onnx.py"
    output = args.output or e14 / "work/quality-recovery/alba-source-vs-onnx.json"
    output.parent.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(source))
    import torch
    from pocket_tts import TTSModel
    from pocket_tts.conditioners.base import TokenizedText
    from pocket_tts.modules.stateful_module import increment_steps

    # Import the controlled 0012 runtime without changing 0012.
    sys.path.insert(0, str(runtime.parent))
    from pocket_tts_onnx import PocketTTSOnnx

    torch.set_num_threads(1)
    model = TTSModel.load_model(config=config, temp=0.3, lsd_decode_steps=1, noise_clamp=None, eos_threshold=-4.0)
    model.eval()
    ort_model = PocketTTSOnnx(models_dir=str(bundle), language="x", precision="fp32", device="cpu", temperature=0.3, lsd_steps=1)
    manifest = ort_model.flow_state_manifest

    prepared = model.flow_lm.conditioner.prepare(TEXT)
    source_ids = prepared.tokens.detach().cpu().numpy().astype(np.int64)
    onnx_ids = ort_model._tokenize(TEXT)
    assert np.array_equal(source_ids, onnx_ids)
    with torch.no_grad():
        source_text = model.flow_lm.conditioner(TokenizedText(torch.from_numpy(source_ids))).numpy()
    onnx_text = ort_model.text_conditioner.run(None, {"token_ids": onnx_ids})[0]

    source_state = model.get_state_for_audio_prompt(alba)
    model._expand_kv_cache(source_state, sequence_length=1000)
    onnx_state = ort_model.prepare_voice_state(alba)

    def compare_cache(valid: int) -> dict:
        rows = []
        for layer in range(6):
            module = f"transformer.layers.{layer}.self_attn"
            a = source_state[module]["cache"].detach().cpu().numpy()[:, :, :valid]
            b = onnx_state[f"state_{layer * 3}"][:, :, :valid]
            rows.append(metrics(a, b))
            assert int(source_state[module]["offset"].item()) == int(onnx_state[f"state_{layer * 3 + 2}"][0]) == valid
        return {
            "valid_positions": valid,
            "layer_max_abs": [x["max_abs"] for x in rows],
            "max_abs": max(x["max_abs"] for x in rows),
            "all_offsets_equal": True,
        }

    initial_cache = compare_cache(126)
    # Exact official text-prefill call. Its sampled return is ignored; only the
    # cache/state mutation is part of prompt conditioning.
    torch.manual_seed(1234)
    with torch.no_grad():
        model._run_flow_lm_and_increment_step(model_state=source_state, text_tokens=torch.from_numpy(source_ids))
    empty_seq = np.zeros((1, 0, 32), dtype=np.float32)
    onnx_result = ort_model.flow_lm_main.run(None, {"sequence": empty_seq, "text_embeddings": onnx_text, **onnx_state})
    update_onnx_state(onnx_state, onnx_result, manifest)
    post_text_cache = compare_cache(152)

    empty_text_np = np.zeros((1, 0, 1024), dtype=np.float32)
    empty_text_t = torch.zeros((1, 0, 1024), dtype=torch.float32)
    source_cur = np.full((1, 1, 32), np.nan, dtype=np.float32)
    onnx_cur = source_cur.copy()
    noise_rng = np.random.RandomState(0)
    step_rows = []
    source_eos = None
    onnx_eos = None
    for step in range(args.steps):
        # Official source backbone and raw EOS logit, with its own recurrent trajectory.
        seq_t = torch.from_numpy(source_cur)
        with torch.no_grad():
            sequence = torch.where(torch.isnan(seq_t), model.flow_lm.bos_emb, seq_t)
            source_c = model.flow_lm.backbone(
                model.flow_lm.input_linear(sequence), empty_text_t, seq_t, model_state=source_state
            )[:, -1].to(torch.float32)
            source_logit = model.flow_lm.out_eos(source_c)
            increment_steps(model.flow_lm, source_state, increment=1)
        source_c_np = source_c.numpy()
        source_logit_np = source_logit.numpy()

        ort_result = ort_model.flow_lm_main.run(
            None, {"sequence": onnx_cur, "text_embeddings": empty_text_np, **onnx_state}
        )
        update_onnx_state(onnx_state, ort_result, manifest)
        onnx_c, onnx_logit = ort_result[:2]

        noise = noise_rng.normal(0.0, np.sqrt(0.3), (1, 32)).astype(np.float32)
        s0 = np.array([[0.0]], dtype=np.float32)
        t1 = np.array([[1.0]], dtype=np.float32)
        with torch.no_grad():
            source_flow = model.flow_lm.flow_net(
                source_c, torch.from_numpy(s0), torch.from_numpy(t1), torch.from_numpy(noise)
            ).numpy()
        onnx_flow = ort_model.flow_lm_flow.run(None, {"c": onnx_c, "s": s0, "t": t1, "x": noise})[0]
        source_cur = (noise + source_flow).reshape(1, 1, 32)
        onnx_cur = (noise + onnx_flow).reshape(1, 1, 32)
        c_metric = metrics(source_c_np, onnx_c)
        flow_metric = metrics(source_flow, onnx_flow)
        latent_metric = metrics(source_cur, onnx_cur)
        source_value = float(source_logit_np[0, 0])
        onnx_value = float(onnx_logit[0, 0])
        if source_eos is None and source_value > -4.0:
            source_eos = step
        if onnx_eos is None and onnx_value > -4.0:
            onnx_eos = step
        step_rows.append({
            "step": step,
            "conditioning_max_abs": c_metric["max_abs"],
            "flow_direction_max_abs": flow_metric["max_abs"],
            "latent_max_abs": latent_metric["max_abs"],
            "source_eos_logit": source_value,
            "onnx_eos_logit": onnx_value,
            "eos_logit_abs": abs(source_value - onnx_value),
        })

    post_ar_cache = compare_cache(152 + args.steps)

    # Deterministic full synthesis isolates every downstream boundary through
    # flow and Mimi decode without positive-temperature RNG mismatch.
    model.temp = 0.0
    torch.manual_seed(0)
    source_audio = model.generate_audio(model.get_state_for_audio_prompt(alba), TEXT).detach().cpu().numpy().astype(np.float32)
    ort_model.temperature = 0.0
    np.random.seed(0)
    onnx_audio = np.asarray(ort_model.generate(TEXT, alba), dtype=np.float32)
    equal_length = source_audio.size == onnx_audio.size
    if equal_length:
        audio_metrics = metrics(source_audio, onnx_audio)
        correlation = float(np.corrcoef(source_audio, onnx_audio)[0, 1])
        error = source_audio.astype(np.float64) - onnx_audio.astype(np.float64)
        snr_db = float(10 * np.log10(np.mean(source_audio.astype(np.float64) ** 2) / np.mean(error ** 2)))
    else:
        audio_metrics, correlation, snr_db = None, None, None

    report = {
        "schema_version": 1,
        "status": "valid_fixed_voice_downstream_equivalence_characterized",
        "contract": {
            "voice": "official pinned precomputed Alba state",
            "voice_state_sha256": hashlib.sha256(alba.read_bytes()).hexdigest(),
            "text": TEXT,
            "seed": 0,
            "positive_temperature_for_shared_noise_steps": 0.3,
            "step_count": args.steps,
            "temperature_zero_full_synthesis": True,
        },
        "tokenizer": {
            "source_ids": source_ids.reshape(-1).tolist(),
            "onnx_ids": onnx_ids.reshape(-1).tolist(),
            "exact": True,
        },
        "text_conditioner": metrics(source_text, onnx_text),
        "initial_alba_state": initial_cache,
        "after_text_prefill": post_text_cache,
        "recurrent_shared_noise": {
            "source_eos_step_within_window": source_eos,
            "onnx_eos_step_within_window": onnx_eos,
            "conditioning_max_abs": max(x["conditioning_max_abs"] for x in step_rows),
            "flow_direction_max_abs": max(x["flow_direction_max_abs"] for x in step_rows),
            "latent_max_abs": max(x["latent_max_abs"] for x in step_rows),
            "eos_logit_max_abs": max(x["eos_logit_abs"] for x in step_rows),
            "first_latent_step_over_1e_3": next((x["step"] for x in step_rows if x["latent_max_abs"] > 1e-3), None),
            "records": step_rows,
        },
        "after_recurrent_window": post_ar_cache,
        "temperature_zero_end_to_end": {
            "source_samples": int(source_audio.size),
            "onnx_samples": int(onnx_audio.size),
            "equal_length": equal_length,
            "metrics": audio_metrics,
            "correlation": correlation,
            "snr_db": snr_db,
        },
        "claim_boundary": "Numerical equivalence establishes implementation fidelity for the valid fixed-Alba contract; only Moritz's listening verdict establishes speech quality.",
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "output": str(output),
        "token_ids_exact": True,
        "text_max_abs": report["text_conditioner"]["max_abs"],
        "recurrent_latent_max_abs": report["recurrent_shared_noise"]["latent_max_abs"],
        "temp0_audio": report["temperature_zero_end_to_end"],
    }, indent=2))


if __name__ == "__main__":
    main()

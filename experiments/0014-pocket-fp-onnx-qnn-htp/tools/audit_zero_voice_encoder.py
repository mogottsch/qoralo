#!/usr/bin/env python3
"""Fail-closed audit of the invalid 0012 Bria voice-cloning contract."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

EXPECTED = {
    "weights": "be9c6b4876d3f30740a8225dfcaa2e43dc4aeb753c15272735bee16bbb4abb0a",
    "encoder_onnx": "a01b6a65c24fe407e8900841446de914b6208482615aff0f23c2e434e9fa3284",
    "source": "d108410d23eef7e01db282f9442891162dbc3db6",
    "source_tts_model": "f0bc252b3ce1c23a5cdbcbb8653b998d8f49744a6b0956b1b1c7eee2390b54f2",
    "local_config": "f851a07982deab073b0e2e5d36a86f38a96069d760146befc26867728eba244b",
    "official_config": "463605b15840d1c62666d1669b0fc70495c45ef4e8fc8ebda422f7e0fbc0f546",
    "bria_10s": "5edb7efde83cf88aab25a35a88e5c48c0f01d5118ad8009b5793a30921a4bb6d",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def main() -> None:
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    e12 = root / "experiments/0012-pocket-onnx-vs-executorch-android"
    e14 = root / "experiments/0014-pocket-fp-onnx-qnn-htp"
    source = e12 / ".local/source"
    weights = e12 / ".local/source-assets/languages/english/model.safetensors"
    encoder_onnx = e12 / ".local/onnx-controlled/mimi_encoder.onnx"
    local_config = e12 / ".local/english-local.yaml"
    official_config = source / "pocket_tts/config/english.yaml"
    tts_model_source = source / "pocket_tts/models/tts_model.py"
    bria = e14 / "work/bria-10s.wav"
    output = e14 / "work/quality-recovery/zero-voice-encoder-audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)

    paths = {
        "weights": weights,
        "encoder_onnx": encoder_onnx,
        "source_tts_model": tts_model_source,
        "local_config": local_config,
        "official_config": official_config,
        "bria_10s": bria,
    }
    for key, path in paths.items():
        actual = sha256_file(path)
        assert actual == EXPECTED[key], (key, actual)
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    assert revision == EXPECTED["source"]
    assert not subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True).strip()

    import onnxruntime as ort
    import torch
    from safetensors.torch import load_file

    state = load_file(str(weights))
    encoder_names = sorted(k for k in state if k.startswith(("mimi.encoder.", "mimi.encoder_transformer.")))
    assert len(encoder_names) == 42
    tensors = []
    for name in encoder_names:
        tensor = state[name].detach().cpu().contiguous()
        raw = tensor.view(torch.uint8).numpy().tobytes()
        tensors.append({
            "name": name,
            "shape": list(tensor.shape),
            "dtype": str(tensor.dtype).removeprefix("torch."),
            "elements": tensor.numel(),
            "bytes": len(raw),
            "nonzero_elements": int(torch.count_nonzero(tensor).item()),
            "raw_tensor_sha256": sha256_bytes(raw),
        })
    assert all(x["nonzero_elements"] == 0 for x in tensors)

    sys.path.insert(0, str(source))
    from pocket_tts import TTSModel
    from pocket_tts.data.audio import audio_read
    from pocket_tts.data.audio_utils import convert_audio

    model = TTSModel.load_model(config=local_config, temp=0.3)
    model.eval()
    # This is the bypass: the local config's weights_path succeeds, so the
    # official fallback exception branch never sets has_voice_cloning=False.
    assert model.has_voice_cloning is True
    audio, rate = audio_read(bria)
    audio = convert_audio(audio, rate, model.sample_rate, 1).numpy().astype(np.float32)
    fixtures = {
        "bria_first_10s": audio.reshape(1, 1, -1),
        "zeros": np.zeros((1, 1, 240000), dtype=np.float32),
        "ones": np.ones((1, 1, 240000), dtype=np.float32),
        "random_seed0_standard_normal": np.random.RandomState(0).normal(size=(1, 1, 240000)).astype(np.float32),
    }
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(encoder_onnx), options, providers=["CPUExecutionProvider"])
    fixture_results = []
    with torch.no_grad():
        for name, value in fixtures.items():
            source_out = model._encode_audio(torch.from_numpy(value)).numpy()
            onnx_out = session.run(None, {"audio": value})[0]
            assert source_out.shape == onnx_out.shape == (1, 125, 1024)
            assert np.array_equal(source_out, onnx_out)
            assert np.count_nonzero(source_out) == 0
            raw = source_out.tobytes()
            fixture_results.append({
                "fixture": name,
                "input_shape": list(value.shape),
                "input_float32_sha256": sha256_bytes(value.tobytes()),
                "output_shape": list(source_out.shape),
                "source_nonzero_elements": int(np.count_nonzero(source_out)),
                "onnx_nonzero_elements": int(np.count_nonzero(onnx_out)),
                "source_vs_onnx_exact": True,
                "source_vs_onnx_max_abs": 0.0,
                "output_float32_sha256": sha256_bytes(raw),
            })

    report = {
        "schema_version": 1,
        "status": "root_cause_proven",
        "checkpoint": {
            "repository": "kyutai/pocket-tts-without-voice-cloning",
            "revision": "d29db7978e464fb90cb3359ee0c69a273b9142cc",
            "path": "languages/english/model.safetensors",
            "sha256": EXPECTED["weights"],
        },
        "source": {
            "repository": "https://github.com/kyutai-labs/pocket-tts.git",
            "revision": revision,
            "checkout_clean": True,
            "tts_model_py_sha256": EXPECTED["source_tts_model"],
        },
        "zero_encoder_tensors": {
            "count": len(tensors),
            "all_zero": True,
            "total_elements": sum(x["elements"] for x in tensors),
            "total_bytes": sum(x["bytes"] for x in tensors),
            "tensors": tensors,
        },
        "controlled_onnx_encoder": {
            "sha256": EXPECTED["encoder_onnx"],
            "fixture_results": fixture_results,
            "conclusion": "The graph is input-invariant and returns only zero voice embeddings; exact source-vs-ONNX agreement validates the broken no-voice-cloning contract.",
        },
        "guard_bypass": {
            "official_config": {
                "path": str(official_config),
                "sha256": EXPECTED["official_config"],
                "lines_3_4": "gated weights_path followed by ungated weights_path_without_voice_cloning",
            },
            "experiment_local_config": {
                "path": str(local_config),
                "sha256": EXPECTED["local_config"],
                "lines_3_4": "the same ungated no-voice-cloning checkpoint is assigned to both weights_path and weights_path_without_voice_cloning",
            },
            "source_logic": {
                "load_lines": "tts_model.py:200-209; has_voice_cloning is set false only when weights_path raises and fallback is selected",
                "guard_lines": "tts_model.py:874-875; audio-path cloning is rejected only when has_voice_cloning is false",
                "observed_has_voice_cloning_after_local_load": model.has_voice_cloning,
            },
        },
        "root_cause": "0012 accidentally exercised an invalid audio-cloning route with a no-voice-cloning checkpoint. Numerical equivalence validated that broken contract, not speech quality.",
        "history_policy": "Experiment 0012 remains unchanged; this correction is recorded in experiment 0014.",
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(output), "zero_tensors": len(tensors), "fixtures": len(fixture_results)}, indent=2))


if __name__ == "__main__":
    main()

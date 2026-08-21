#!/usr/bin/env python3
"""Recreate the exact experiment-0019 fixed-capacity ONNX derivatives.

The official source models and external-data files are intentionally ignored. This
script verifies them against results/source-lock.json, writes every fixed I/O shape,
runs the tracked graph rewrites, copies external data beside the derivatives, and
checks the final hashes against results/fixed-capacity-derivative-provenance.json.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]

p = argparse.ArgumentParser()
p.add_argument("--tts-root", type=Path, default=REPO / "experiments/0018-moss-tts-nano-onnx-android/.local/tts")
p.add_argument("--codec-root", type=Path, default=REPO / "experiments/0018-moss-tts-nano-onnx-android/.local/codec")
p.add_argument("--output-dir", type=Path, default=ROOT / ".local/specialized")
a = p.parse_args()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args: object) -> None:
    subprocess.run([sys.executable, *map(str, args)], check=True)


lock = json.load(open(ROOT / "results/source-lock.json"))
source_paths = {
    "moss_tts_prefill.onnx": a.tts_root / "moss_tts_prefill.onnx",
    "moss_tts_decode_step.onnx": a.tts_root / "moss_tts_decode_step.onnx",
    "moss_tts_local_fixed_sampled_frame.onnx": a.tts_root / "moss_tts_local_fixed_sampled_frame.onnx",
    "moss_tts_global_shared.data": a.tts_root / "moss_tts_global_shared.data",
    "moss_tts_local_shared.data": a.tts_root / "moss_tts_local_shared.data",
    "moss_audio_tokenizer_decode_full.onnx": a.codec_root / "moss_audio_tokenizer_decode_full.onnx",
    "moss_audio_tokenizer_decode_shared.data": a.codec_root / "moss_audio_tokenizer_decode_shared.data",
}
for name, path in source_paths.items():
    expected = lock["files"][name]
    assert path.is_file(), path
    assert path.stat().st_size == expected["bytes"], (name, path.stat().st_size, expected["bytes"])
    assert sha(path) == expected["sha256"], (name, sha(path), expected["sha256"])

a.output_dir.mkdir(parents=True, exist_ok=True)
for name in ("moss_tts_global_shared.data", "moss_tts_local_shared.data", "moss_audio_tokenizer_decode_shared.data"):
    shutil.copyfile(source_paths[name], a.output_dir / name)

prefill = {"input_ids": [1, 226, 17], "attention_mask": [1, 226], "global_hidden": [1, 226, 768]}
for i in range(12):
    prefill[f"present_key_{i}"] = [1, 226, 12, 64]
    prefill[f"present_value_{i}"] = [1, 226, 12, 64]

decode = {"input_ids": [1, 1, 17], "past_valid_lengths": [1], "global_hidden": [1, 1, 768]}
for i in range(12):
    decode[f"past_key_{i}"] = [1, 600, 12, 64]
    decode[f"past_value_{i}"] = [1, 600, 12, 64]
    decode[f"present_key_{i}"] = [1, 601, 12, 64]
    decode[f"present_value_{i}"] = [1, 601, 12, 64]

local = {
    "global_hidden": [1, 768],
    "repetition_seen_mask": [1, 16, 1024],
    "assistant_random_u": [1],
    "audio_random_u": [1, 16],
    "should_continue": [1, 1],
    "frame_token_ids": [1, 16],
}
codec = {
    "audio_codes": [1, 375, 16],
    "audio_code_lengths": [1],
    "audio": [1, 2, 1440000],
    "audio_lengths": [1],
}

specialize = ROOT / "tools/specialize_model_io.py"
rewrite = ROOT / "tools/rewrite_qnn_blockers.py"
attention = ROOT / "tools/rewrite_decode_fixed_attention.py"


def specialize_one(stem: str, source: Path, shapes: dict) -> Path:
    shape_path = a.output_dir / f"{stem}.shapes.json"
    model_path = a.output_dir / f"{stem}.onnx"
    report_path = a.output_dir / f"{stem}.provenance.json"
    shape_path.write_text(json.dumps(shapes, indent=2, sort_keys=True) + "\n")
    run(specialize, "--input", source, "--output", model_path, "--shapes", shape_path, "--report", report_path)
    return model_path


prefill_model = specialize_one("prefill-s226", source_paths["moss_tts_prefill.onnx"], prefill)
run(rewrite, "--kind", "prefill", "--input", prefill_model, "--output", a.output_dir / "prefill-s226-qnn.onnx", "--report", a.output_dir / "prefill-s226-qnn.rewrite.json")

decode_model = specialize_one("decode-fixed-cap600", source_paths["moss_tts_decode_step.onnx"], decode)
run(rewrite, "--kind", "decode", "--input", decode_model, "--output", a.output_dir / "decode-fixed-cap600-qnn.onnx", "--report", a.output_dir / "decode-fixed-cap600-qnn.rewrite.json")
run(attention, "--input", a.output_dir / "decode-fixed-cap600-qnn.onnx", "--output", a.output_dir / "decode-fixed-cap600-attention-qnn.onnx", "--report", a.output_dir / "decode-fixed-cap600-attention-qnn.rewrite.json")

specialize_one("local-fixed-b1", source_paths["moss_tts_local_fixed_sampled_frame.onnx"], local)
codec_model = specialize_one("codec-full-cap375", source_paths["moss_audio_tokenizer_decode_full.onnx"], codec)
run(rewrite, "--kind", "codec", "--input", codec_model, "--output", a.output_dir / "codec-full-cap375-qnn.onnx", "--report", a.output_dir / "codec-full-cap375-qnn.rewrite.json")

expected = {
    "prefill-s226.onnx": "9e66258130b509befe60e355facc00d757408d6c55de8fa66fda2934168930fd",
    "prefill-s226-qnn.onnx": "a974e163f7d17ab5b880992e4b1bbeb36e31d087110adfd24f660266b4597bbc",
    "decode-fixed-cap600.onnx": "02b8e47c074f0d17d85e0eab54c843324007df13ddf6533df5b48e8aa97b1da2",
    "decode-fixed-cap600-qnn.onnx": "15241baafb4f5798d0a0bfe64bc03eb0dc9b0b5ac951fe357cee57d77a80a2d4",
    "decode-fixed-cap600-attention-qnn.onnx": "e9f87f69d1ead5d32746872d7ae462a337ddbb5f6a80eedaa08f1c14789567b9",
    "local-fixed-b1.onnx": "f475a116f028f832606d4ca5f0bee5697bca2d0923a3a0a6cb28bd81585eaf02",
    "codec-full-cap375.onnx": "319e9d7db2fe6e2158b3d73cbed340b22b76137ba37c74468ffc7a41ceae3de4",
    "codec-full-cap375-qnn.onnx": "a7a5e97d5949bf6dff839745ba7a01c241b030c7b39d8987b5c9d529c467b7b9",
}
actual = {name: sha(a.output_dir / name) for name in expected}
assert actual == expected, (actual, expected)
manifest = {
    "schema_version": 1,
    "result": "passed_exact_derivative_reproduction",
    "source_revisions": lock["reused_revisions"],
    "source_files": lock["files"],
    "derivatives": {name: {"path": str(a.output_dir / name), "sha256": digest} for name, digest in actual.items()},
    "external_data": {name: {"path": str(a.output_dir / name), "sha256": sha(a.output_dir / name)} for name in ("moss_tts_global_shared.data", "moss_tts_local_shared.data", "moss_audio_tokenizer_decode_shared.data")},
}
(a.output_dir / "fixed-capacity-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
print(json.dumps({"result": manifest["result"], "output_dir": str(a.output_dir), "derivatives": actual}, indent=2))

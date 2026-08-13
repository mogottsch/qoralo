#!/usr/bin/env python3
"""Hash, inspect, and CPU-load exact Mini 0.8 assets under the global gate."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
PINS = json.loads((HERE / "pins.json").read_text(encoding="utf-8"))
ARTIFACT_ROOT = Path(os.environ.get("KITTEN_ARTIFACT_ROOT", EXPERIMENT / "artifacts/kitten-tts-mini-0.8"))


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"BLOCKED: {message}")


def main() -> None:
    if (
        os.environ.get("KITTEN_GATED_SMOKE") != "1"
        or os.environ.get("PREVIEW_RESOURCE_GRANT_KIND") != "model-load"
        or os.environ.get("PREVIEW_RESOURCE_GRANT_TASK") != "task-4"
    ):
        fail("direct model loading is forbidden; use smoke-load.sh to acquire the task-4 model-load gate")
    from huggingface_hub import snapshot_download
    import numpy as np
    import onnxruntime as ort
    # The locked espeakng-loader Linux wheel embeds a build-host data prefix.
    # Select an already-provided system/project-local eSpeak installation before
    # importing misaki through the official Kitten implementation.
    import espeakng_loader
    espeak_library = Path(os.environ.get("KITTEN_ESPEAK_LIBRARY", "/usr/lib/libespeak-ng.so"))
    espeak_data = Path(os.environ.get("KITTEN_ESPEAK_DATA", "/usr/share/espeak-ng-data"))
    if not espeak_library.is_file() or not espeak_data.is_dir():
        fail("permitted eSpeak library/data unavailable; set KITTEN_ESPEAK_LIBRARY and KITTEN_ESPEAK_DATA")
    espeakng_loader.get_library_path = lambda: str(espeak_library)
    espeakng_loader.get_data_path = lambda: str(espeak_data)
    from kittentts.onnx_model import KittenTTS_1_Onnx

    model = PINS["model"]
    snapshot = Path(snapshot_download(
        repo_id=model["repo_id"], revision=model["revision"], allow_patterns=list(model["files"]),
        local_dir=ARTIFACT_ROOT / "snapshot",
    ))
    verified = {}
    for relative, expected in model["files"].items():
        path = snapshot / relative
        actual = {"bytes": path.stat().st_size, "sha256": digest(path)}
        if actual != expected:
            fail(f"artifact mismatch for {relative}: {actual}")
        verified[relative] = actual
    config = json.loads((snapshot / "config.json").read_text(encoding="utf-8"))
    if (config.get("name"), config.get("version"), config.get("model")) != (
        "Kitten TTS Mini", "0.8", "kitten-tts-mini-0.8"
    ):
        fail(f"model config identity drift: {config}")
    if config.get("voice_aliases", {}).get("Jasper") != PINS["voice"]["asset_key"]:
        fail("Jasper stock alias drift")
    voices = np.load(snapshot / config["voices"], allow_pickle=False)
    voice = np.ascontiguousarray(voices[PINS["voice"]["asset_key"]])
    if voice.shape != tuple(PINS["voice"]["array_shape"]) or str(voice.dtype) != PINS["voice"]["array_dtype"]:
        fail("selected stock voice shape or dtype drift")
    if hashlib.sha256(voice.tobytes(order="C")).hexdigest() != PINS["voice"]["array_c_order_sha256"]:
        fail("selected stock voice digest drift")
    loaded = KittenTTS_1_Onnx(
        model_path=str(snapshot / config["model_file"]), voices_path=str(snapshot / config["voices"]),
        speed_priors=config.get("speed_priors", {}), voice_aliases=config.get("voice_aliases", {}),
    )
    providers = loaded.session.get_providers()
    if "CPUExecutionProvider" not in providers or {"CUDAExecutionProvider", "TensorrtExecutionProvider"} & set(providers):
        fail(f"CPU-only provider assertion failed: {providers}")
    report = {
        "schema_version": 1, "status": "passed", "created_at": datetime.now(timezone.utc).isoformat(),
        "resource_gate": {"kind": "model-load", "policy": "model-resource-policy-v1.json"},
        "model": {"repo_id": model["repo_id"], "revision": model["revision"], "verified_files": verified},
        "voice": PINS["voice"], "providers": providers, "native_output": PINS["native_output"],
        "phonemizer": {"library": str(espeak_library), "data": str(espeak_data)}, "generation_performed": False,
    }
    output = ARTIFACT_ROOT / "smoke-load.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "report": str(output), "providers": providers}, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fetch the exact public snapshot, verify it, and perform a CPU-only model load."""
from __future__ import annotations
import hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
PINS = json.loads((HERE / "pins.json").read_text(encoding="utf-8"))
ARTIFACT_ROOT = Path(os.environ.get("SUPERTONIC_ARTIFACT_ROOT", EXPERIMENT / "artifacts/supertonic-3"))
TRANSCRIPT = EXPERIMENT / "protocol/transcript.txt"
TRANSCRIPT_SHA256 = "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): value.update(block)
    return value.hexdigest()


def fail(message: str) -> "None": raise SystemExit(f"BLOCKED: {message}")


def verify_snapshot(snapshot: Path) -> dict[str, dict[str, object]]:
    verified = {}
    for relative, expected in PINS["model"]["files"].items():
        path = snapshot / relative
        if not path.is_file(): fail(f"pinned artifact absent: {relative}")
        actual = {"bytes": path.stat().st_size, "sha256": digest(path)}
        if actual != expected: fail(f"pinned artifact mismatch for {relative}: {actual}")
        verified[relative] = actual
    return verified


def main() -> None:
    if os.environ.get("SUPERTONIC_GATED_SMOKE") != "1" or os.environ.get("PREVIEW_RESOURCE_GRANT_KIND") != "smoke-load":
        fail("direct load forbidden; use smoke-load.sh to acquire the global gate")
    if os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        fail("credentials are forbidden; the official snapshot is public")
    if hashlib.sha256(TRANSCRIPT.read_bytes()).hexdigest() != TRANSCRIPT_SHA256: fail("frozen transcript changed")
    from huggingface_hub import snapshot_download
    model = PINS["model"]
    snapshot = Path(snapshot_download(repo_id=model["repo_id"], revision=model["revision"], allow_patterns=list(model["files"]), local_dir=ARTIFACT_ROOT / "snapshot", token=False))
    verified = verify_snapshot(snapshot)
    import onnxruntime as ort
    from supertonic import TTS, __version__
    if __version__ != PINS["implementation"]["version"]: fail("SDK version drift")
    if "CPUExecutionProvider" not in ort.get_available_providers(): fail(f"CPU ONNX provider absent: {ort.get_available_providers()}")
    tts = TTS(model="supertonic-3", model_dir=snapshot, auto_download=False)
    active_providers = {name: getattr(tts.model, name).get_providers() for name in ("dp_ort", "text_enc_ort", "vector_est_ort", "vocoder_ort")}
    if any(value != ["CPUExecutionProvider"] for value in active_providers.values()): fail(f"a model session is not CPU-only: {active_providers}")
    if tts.sample_rate != 44100 or tts.voice_style_names != ["M1"]: fail("native format or fixed stock voice mismatch")
    style = tts.get_voice_style("M1")
    report = {"schema_version": 1, "status": "passed", "created_at": datetime.now(timezone.utc).isoformat(), "resource_gate": {"task": "task-2", "kind": "smoke-load"}, "model": {"repo_id": model["repo_id"], "revision": model["revision"], "verified_files": verified}, "implementation": PINS["implementation"], "voice": PINS["voice"] | {"loaded": style is not None}, "runtime": PINS["runtime"] | {"onnxruntime": ort.__version__, "available_providers": ort.get_available_providers(), "active_session_providers": active_providers}, "native_output": PINS["native_output"], "transcript_sha256": TRANSCRIPT_SHA256, "inference_performed": False}
    output = ARTIFACT_ROOT / "smoke-load.json"; output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "report": str(output)}, sort_keys=True))

if __name__ == "__main__": main()

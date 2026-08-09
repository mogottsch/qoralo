from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]


def pins() -> dict:
    return json.loads((HERE / "pins.json").read_text(encoding="utf-8"))


def test_model_implementation_and_voice_are_immutable() -> None:
    data = pins()
    assert re.fullmatch(r"[0-9a-f]{40}", data["model"]["revision"])
    assert re.fullmatch(r"[0-9a-f]{40}", data["implementation"]["revision"])
    assert data["implementation"]["version"] == "0.9.4"
    assert re.fullmatch(r"[0-9a-f]{64}", data["implementation"]["wheel_sha256"])
    voice = data["voice"]
    voice_file = data["model"]["files"][f"voices/{voice['id']}.pt"]
    assert voice["kind"] == "repository stock voice"
    assert voice["personal_or_cloned_input_used"] is False
    assert re.fullmatch(r"[0-9a-f]{64}", voice_file["sha256"])


def test_native_output_and_frozen_transcript() -> None:
    data = pins()
    assert data["native_output"] == {
        "sample_rate_hz": 24000,
        "channels": 1,
        "library_tensor": "torch.float32 waveform",
        "official_cli_container": "WAV",
        "official_cli_encoding": "PCM signed 16-bit little-endian",
    }
    transcript = (EXPERIMENT / "protocol" / "transcript.txt").read_bytes()
    assert hashlib.sha256(transcript).hexdigest() == "424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67"
    smoke = (HERE / "smoke_load.py").read_text(encoding="utf-8")
    assert "protocol/transcript" not in smoke  # path is constructed from the experiment root
    assert "TRANSCRIPT = EXPERIMENT / \"protocol\" / \"transcript.txt\"" in smoke


def test_smoke_load_is_gated_and_local_only() -> None:
    wrapper = (HERE / "smoke-load.sh").read_text(encoding="utf-8")
    smoke = (HERE / "smoke_load.py").read_text(encoding="utf-8")
    assert "tools/with-resources.sh" in wrapper
    assert "--task task-4 --kind smoke-load" in wrapper
    assert "KOKORO_GATED_SMOKE=1" in wrapper
    assert 'os.environ.get("KOKORO_GATED_SMOKE") != "1"' in smoke
    assert "revision=model[\"revision\"]" in smoke
    assert 'config=str(snapshot / "config.json")' in smoke
    assert 'model=str(snapshot / "kokoro-v1_0.pth")' in smoke


def test_setup_never_requests_privilege_or_system_install() -> None:
    setup = (HERE / "setup.sh").read_text(encoding="utf-8")
    commands = [line.strip() for line in setup.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    assert not any(line.startswith(("sudo ", "apt ", "apt-get ", "pip ")) for line in commands)
    assert "uv pip install" not in setup
    assert "UV_PROJECT_ENVIRONMENT" in setup
    assert "--no-python-downloads" in setup
    assert "command -v espeak-ng" in setup

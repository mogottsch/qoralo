from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def data(filename: str) -> dict:
    return json.loads((HERE / filename).read_text(encoding="utf-8"))


def test_exact_mini_80m_v08_identity_and_official_release() -> None:
    pins = data("pins.json")
    assert pins["candidate"] == "F"
    assert pins["model"]["repo_id"] == "KittenML/kitten-tts-mini-0.8"
    assert pins["model"]["parameter_class"] == "80M"
    assert pins["model"]["revision"] == "c02725660cea441db4c383af69f1f26f5cd00947"
    release = pins["implementation"]
    assert release["release_tag"] == "0.8"
    assert release["declared_release_version"] == "0.8.0"
    assert release["release_asset"] == "kittentts-0.8.0-py3-none-any.whl"
    assert release["release_asset_url"].endswith("/0.8/kittentts-0.8.0-py3-none-any.whl")
    assert release["release_asset_sha256"] == "cba97464da2ec56384b9fc03004449dadbe6d9abd16aa89e98953027854fd7d9"
    assert release["embedded_distribution_version"] == "0.1.0"  # upstream packaging defect is explicit


@pytest.mark.parametrize("repo", [
    "KittenML/kitten-tts-nano-0.8", "KittenML/kitten-tts-micro-0.8",
    "KittenML/kitten-tts-mini-0.8.1", "KittenML/kitten-tts-mini", "kitten-tts-mini-0.8",
])
def test_verifier_rejects_substitutes(repo: str) -> None:
    verifier = load("kitten_verify", "verify_pins.py")
    pins, plan = data("pins.json"), data("attempt-plan.json")
    pins["model"]["repo_id"] = repo
    plan["model_repo_id"] = repo
    with pytest.raises(AssertionError):
        verifier.validate(pins, plan, check_lock=False)


@pytest.mark.parametrize("asset, tag, declared", [
    ("kittentts-0.8.1-py3-none-any.whl", "0.8.1", "0.8.1"),
    ("kittentts-py3-none-any.whl", "main", "unversioned"),
])
def test_verifier_rejects_later_or_unversioned_package(asset: str, tag: str, declared: str) -> None:
    verifier = load("kitten_verify_release", "verify_pins.py")
    pins, plan = data("pins.json"), data("attempt-plan.json")
    pins["implementation"].update(release_asset=asset, release_tag=tag, declared_release_version=declared)
    with pytest.raises(AssertionError):
        verifier.validate(pins, plan, check_lock=False)


def test_artifacts_voice_native_format_and_licenses_are_hashed() -> None:
    pins = data("pins.json")
    for artifact in pins["model"]["files"].values():
        assert artifact["bytes"] > 0
        assert len(artifact["sha256"]) == 64
    voice = pins["voice"]
    assert voice["display_id"] == "Jasper" and voice["asset_key"] == "expr-voice-2-m"
    assert voice["array_c_order_bytes"] == 409600
    assert voice["array_c_order_sha256"] == "4fc6fdcbaac820aad0d2f3040709bc0e23e3674d9c7f2eaa67ddc9573f128de4"
    assert voice["reference_audio_used"] is False and voice["cloning_performed"] is False
    assert pins["model"]["license"] == pins["implementation"]["license"] == "Apache-2.0"
    assert len(pins["implementation"]["license_sha256"]) == 64
    assert pins["native_output"]["sample_rate_hz"] == 24000
    assert pins["native_output"]["channels"] == 1


def test_dependency_graph_and_official_wheel_are_hash_locked() -> None:
    pins = data("pins.json")
    lock_path = HERE / "uv.lock"
    assert hashlib.sha256(lock_path.read_bytes()).hexdigest() == pins["implementation"]["dependency_lock_sha256"]
    lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    packages = {package["name"]: package for package in lock["package"]}
    kitten = packages["kittentts"]
    assert kitten["version"] == "0.1.0"  # exact official 0.8 asset's stale metadata
    assert kitten["source"]["url"].endswith("/0.8/kittentts-0.8.0-py3-none-any.whl")
    assert kitten["wheels"] == [{
        "url": pins["implementation"]["release_asset_url"],
        "hash": "sha256:" + pins["implementation"]["release_asset_sha256"],
    }]
    assert packages["torch"]["version"] == "2.6.0+cpu"
    assert "download.pytorch.org/whl/cpu" in packages["torch"]["source"]["registry"]
    assert not any(package["name"].startswith(("nvidia-", "cuda-")) for package in lock["package"])
    for package in lock["package"]:
        if "registry" in package.get("source", {}):
            artifacts = ([package["sdist"]] if "sdist" in package else []) + package.get("wheels", [])
            assert artifacts and all(item.get("hash", "").startswith("sha256:") for item in artifacts)


def test_plan_is_default_first_and_invents_no_undocumented_value() -> None:
    plan = data("attempt-plan.json")
    assert plan["committed_before_full_generation"] is True
    assert plan["attempts"] == [{"ordinal": 1, "id": "default", "speed": 1.0, "uses_documented_default": True}]
    assert plan["documentation"]["documented_numeric_bounds"] is None
    assert plan["documentation"]["documented_direction_for_longer_output"] is None
    assert plan["short_default_outcome"] == "terminal_protocol_blocker"
    assert "undocumented_speed_values" in plan["forbidden"]


def test_plan_mutation_and_cloning_flags_fail_closed() -> None:
    verifier = load("kitten_verify_plan", "verify_pins.py")
    pins, plan = data("pins.json"), data("attempt-plan.json")
    plan["attempts"].append({"ordinal": 2, "id": "slow", "speed": 0.9, "uses_documented_default": False})
    with pytest.raises(AssertionError):
        verifier.validate(pins, plan, check_lock=False)
    plan = data("attempt-plan.json")
    pins["voice"]["cloning_performed"] = True
    with pytest.raises(AssertionError):
        verifier.validate(pins, plan, check_lock=False)


def test_setup_and_smoke_are_isolated_cpu_only_and_gated() -> None:
    setup = (HERE / "setup.sh").read_text(encoding="utf-8")
    commands = [line.strip() for line in setup.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    assert not any(line.startswith(("sudo ", "apt ", "apt-get ", "pip ")) for line in commands)
    assert "uv sync" in setup and "--locked" in setup and "--no-python-downloads" in setup
    assert "UV_SKIP_WHEEL_FILENAME_CHECK=1" in setup
    assert "CUDAExecutionProvider" in setup and "CPUExecutionProvider" in setup
    assert "command -v espeak-ng" in setup and "KITTEN_ESPEAK_LIBRARY" in setup
    wrapper = (HERE / "smoke-load.sh").read_text(encoding="utf-8")
    smoke = (HERE / "smoke_load.py").read_text(encoding="utf-8")
    assert "tools/with-resources.sh" in wrapper and "--kind model-load" in wrapper
    assert "KITTEN_GATED_SMOKE=1" in wrapper
    assert 'PREVIEW_RESOURCE_GRANT_KIND") != "model-load"' in smoke
    assert "revision=model[\"revision\"]" in smoke
    assert "generation_performed\": False" in smoke


def test_generator_allows_no_reference_or_cloning_inputs_and_is_write_once() -> None:
    source = (HERE / "generate_preview.py").read_text(encoding="utf-8")
    wrapper = (HERE / "generate-preview.sh").read_text(encoding="utf-8")
    assert "--kind full-generation" in wrapper and "KITTEN_GATED_GENERATION=1" in wrapper
    assert 'open("xb")' in source
    assert "output.exists()" in source
    assert 'parser.add_argument("--attempt"' in source
    assert 'parser.add_argument("--output"' in source
    assert "reference_audio" not in source and "clone" not in source.lower()
    assert "TRANSCRIPT_SHA256" in source
    env = os.environ.copy()
    env.pop("KITTEN_GATED_GENERATION", None)
    result = subprocess.run(
        [sys.executable, str(HERE / "generate_preview.py"), "--attempt", "default", "--output", str(HERE / "should-not-exist.f32le")],
        text=True, capture_output=True, env=env,
    )
    assert result.returncode != 0 and "global full-generation gate" in (result.stdout + result.stderr)
    assert not (HERE / "should-not-exist.f32le").exists()


def test_frozen_transcript_unchanged() -> None:
    transcript = (EXPERIMENT / "protocol/transcript.txt").read_bytes()
    assert hashlib.sha256(transcript).hexdigest() == "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"

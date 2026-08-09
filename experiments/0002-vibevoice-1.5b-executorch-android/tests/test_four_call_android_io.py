import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ABI_PATH = ROOT / "fixtures/four-call-cache-abi.json"
MODULE_PATH = ROOT / "export/four_call_android_io.py"
SPEC = importlib.util.spec_from_file_location("four_call_android_io", MODULE_PATH)
io = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(io)


def write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_accepts_frozen_abi_and_all_four_transitions():
    abi = io.load_abi(ABI_PATH)
    assert list(abi["methods"]) == ["acoustic_decode", "semantic_encode"]
    assert [(x["required_phase"], x["next_phase"]) for x in abi["call_transitions"]] == [
        (0, 1), (1, 2), (2, 3), (3, 4)
    ]
    assert abi["call_transitions"][3]["decoder_post_valid_lengths"][28] == 4


@pytest.mark.parametrize("mutation,match", [
    (lambda abi: abi.update(schema_version=2), "schema_version"),
    (lambda abi: abi["methods"]["acoustic_decode"]["inputs"][3].update(shape=[1]), "shape mismatch"),
    (lambda abi: abi["methods"]["semantic_encode"]["outputs"][2].update(order=9), "order"),
    (lambda abi: abi["call_transitions"][2].update(required_phase=1), "phase"),
    (lambda abi: abi["call_transitions"][1]["decoder_pre_valid_lengths"].__setitem__(0, 5), "disconnected"),
])
def test_rejects_version_shape_order_and_transition_mismatches(tmp_path, mutation, match):
    abi = json.loads(ABI_PATH.read_text())
    mutation(abi)
    with pytest.raises(ValueError, match=match):
        io.load_abi(write_json(tmp_path / "abi.json", abi))


def test_prepare_packages_four_latents_and_hashed_metadata(tmp_path):
    latents = []
    for call in range(4):
        path = tmp_path / f"source-{call}.bin"
        path.write_bytes(bytes([call]) * 256)
        latents.append(path)
    output = tmp_path / "package"
    manifest = io.prepare(ABI_PATH, latents, output)
    assert [entry["call"] for entry in manifest["calls"]] == [0, 1, 2, 3]
    assert [entry["required_phase"] for entry in manifest["calls"]] == [0, 1, 2, 3]
    assert manifest["artifact"]["methods"] == ["acoustic_decode", "semantic_encode"]
    for call, entry in enumerate(manifest["calls"]):
        record = entry["decoder_latent"]
        packaged = output / record["file"]
        assert record["shape"] == [1, 1, 64]
        assert record["byte_count"] == 256
        assert record["sha256"] == hashlib.sha256(packaged.read_bytes()).hexdigest()


def _mock_device_result(package: Path) -> dict:
    abi = json.loads((package / "four-call-cache-abi.json").read_text())
    calls = []
    for call, transition in enumerate(abi["call_transitions"]):
        call_root = package / "device" / f"call-{call}"
        call_root.mkdir(parents=True)
        specs = [("pcm", [1, 1, 3200]), ("semantic_output", [1, 1, 128])]
        for domain, method in (("decoder", "acoustic_decode"), ("semantic", "semantic_encode")):
            specs += [(f"{domain}_cache_{index:02d}", cache["capacity_shape"])
                      for index, cache in enumerate(abi["methods"][method]["caches"])]
        outputs = []
        for order, (name, shape) in enumerate(specs):
            byte_count = 4
            for dimension in shape:
                byte_count *= dimension
            path = call_root / f"{name}.f32le"
            path.write_bytes(b"\0" * byte_count)
            outputs.append({"order": order, "name": name,
                            "file": path.relative_to(package / "device").as_posix(),
                            "shape": shape, "dtype": "float32", "byte_count": byte_count,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        calls.append({"call": call, "phase": call, "next_phase": call + 1,
                      "decoder_pre_valid_lengths": transition["decoder_pre_valid_lengths"],
                      "decoder_post_valid_lengths": transition["decoder_post_valid_lengths"],
                      "semantic_pre_valid_lengths": transition["semantic_pre_valid_lengths"],
                      "semantic_post_valid_lengths": transition["semantic_post_valid_lengths"],
                      "outputs": outputs})
    return {"schema_version": 1, "abi_id": io.ABI_ID, "status": "passed", "calls": calls}


def _package(tmp_path: Path) -> Path:
    sources = []
    for call in range(4):
        source = tmp_path / f"latent-{call}"
        source.write_bytes(b"\0" * 256)
        sources.append(source)
    package = tmp_path / "package"
    io.prepare(ABI_PATH, sources, package)
    return package


def test_parse_result_verifies_every_call_cache_and_payload(tmp_path):
    package = _package(tmp_path)
    result = _mock_device_result(package)
    result_path = write_json(package / "device-result.json", result)
    parsed = io.parse_result(package / "manifest.json", result_path, package / "device")
    assert parsed["status"] == "prepared"
    assert [call["output_count"] for call in parsed["calls"]] == [70] * 4
    assert all(call["outputs_verified"] for call in parsed["calls"])


@pytest.mark.parametrize("corrupt", ["call_order", "valid_lengths", "output_order", "hash"])
def test_parse_result_rejects_malformed_device_data(tmp_path, corrupt):
    package = _package(tmp_path)
    result = _mock_device_result(package)
    if corrupt == "call_order":
        result["calls"][2]["call"] = 1
    elif corrupt == "valid_lengths":
        result["calls"][1]["decoder_post_valid_lengths"][28] = 99
    elif corrupt == "output_order":
        result["calls"][0]["outputs"][3]["name"] = "wrong"
    else:
        result["calls"][3]["outputs"][-1]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        io.parse_result(package / "manifest.json", write_json(package / "result.json", result), package / "device")


def test_android_harness_uses_named_dispatch_and_atomic_transition_commit():
    source = (ROOT / "android/app/src/main/java/dev/moket/vibevoiceprobe/StreamingProbeActivity.java").read_text()
    assert "module.execute(method.name" in source
    assert 'Set.of(abi.decoder.name, abi.semantic.name)' in source
    assert "Commit is intentionally after both invocations" in source
    assert source.index("Invocation semantic = invoke") < source.index("decoderState = decoder.nextState")
    metadata = (ROOT / "android/app/src/main/java/dev/moket/vibevoiceprobe/FourCallMetadata.java").read_text()
    assert '"acoustic_decode"' in metadata and '"semantic_encode"' in metadata
    assert "tensor count mismatch" in metadata and "shape mismatch" in metadata

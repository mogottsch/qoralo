import copy
import json
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import protocol


def test_transcript_is_frozen_and_in_range():
    manifest = protocol.load_protocol()
    assert manifest["transcript_word_count"] == 36
    assert manifest["transcript_sha256"] == "424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67"


def test_manifest_and_result_schemas_are_valid():
    manifest = protocol.load_protocol()
    schema = json.loads((ROOT / "schemas" / "protocol.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(manifest, schema)
    for name in ("preview-result.schema.json", "generation-policy.schema.json"):
        jsonschema.Draft202012Validator.check_schema(json.loads((ROOT / "schemas" / name).read_text()))


def test_transcript_byte_drift_fails_closed(tmp_path):
    manifest = copy.deepcopy(protocol.load_protocol())
    (tmp_path / "transcript.txt").write_text((ROOT / "protocol" / "transcript.txt").read_text() + "!", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="drift"): protocol.load_protocol(tmp_path / "manifest.json")


def test_generated_artifacts_are_ignored():
    ignore = (ROOT.parents[1] / ".gitignore").read_text(encoding="utf-8")
    assert "artifacts/" in ignore and "*.wav" in ignore


def test_punctuation_change_requires_higher_version():
    previous = protocol.load_protocol()
    changed = copy.deepcopy(previous)
    changed["transcript_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="requires a higher protocol version"):
        protocol.validate_successor(previous, changed)
    changed["protocol_version"] += 1
    protocol.validate_successor(previous, changed)


def test_protocol_revision_invalidates_prior_preview(tmp_path):
    current = protocol.protocol_reference()
    protocol.validate_result_protocol({"protocol": current})
    changed = copy.deepcopy(protocol.load_protocol()); changed["protocol_version"] += 1
    path = tmp_path / "v2.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    (tmp_path / "transcript.txt").write_bytes((ROOT / "protocol" / "transcript.txt").read_bytes())
    with pytest.raises(ValueError, match="prior preview is invalid"):
        protocol.validate_result_protocol({"protocol": current}, path)

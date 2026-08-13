#!/usr/bin/env python3
"""Fail-closed validation of the Supertonic 3 deployment track."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCHIVE = "sherpa-onnx-supertonic-3-tts-int8-2026-05-11.tar.bz2"
ARCHIVE_SHA = "82fa96f91c4ef8abaae3a14a3f4153facf88bed821d1f7331cec2700f432c427"
MODEL_FILES = {"duration_predictor.int8.onnx", "text_encoder.int8.onnx", "vector_estimator.int8.onnx", "vocoder.int8.onnx"}
DATA_FILES = {"tts.json", "unicode_indexer.bin", "voice.bin"}
NOTICE_FILES = {"LICENSE", "README.md"}
DEPLOYED = {
 "LICENSE": (1070,"0dfe0d0ba84416fe3879d9a34f4909d8d0137c78d1e95834177b0414ac096fa2"), "README.md": (19518,"a96c347945f7c8bc1673bea3525b1ac8d36fdde556e1e0a6a186052429caf863"),
 "duration_predictor.int8.onnx": (3700147,"c3eb91414d5ff8a7a239b7fe9e34e7e2bf8a8140d8375ffb14718b1c639325db"), "text_encoder.int8.onnx": (36416150,"c7befd5ea8c3119769e8a6c1486c4edc6a3bc8365c67621c881bbb774b9902ff"),
 "tts.json": (8253,"42078d3aef1cd43ab43021f3c54f47d2d75ceb4e75f627f118890128b06a0d09"), "unicode_indexer.bin": (262144,"8402ca48e5189a8950138580b0fff64db6f072f24ac07cd54ba8b2fbb9883b30"),
 "vector_estimator.int8.onnx": (78400833,"20cd86fa5c6effedfda0e7cffe5b0569ca401c440a0c3a1d72bf39286c0db3fd"), "vocoder.int8.onnx": (25991073,"e923d60f53f95eb1ce235f1dc33ec56d9c057823c96fa6f8acf98f32b0da6152"), "voice.bin": (517168,"67d5209b0ee8ce6c74105ffbe12fe6a7628aea3b4ba2fcb308a4a67938a93ce8")}
VOICE_HASHES = {"F1.json":"bbdec6ee00231c2c742ad05483df5334cab3b52fda3ba38e6a07059c4563dbc2","F2.json":"7c722c6a72707b1a77f035d67f0d1351ba187738e06f7683e8c72b1df3477fc6","F3.json":"12f6ef2573baa2defa1128069cb59f203e3ab67c92af77b42df8a0e3a2f7c6ab","F4.json":"c2fa764c1225a76dfc3e2c73e8aa4f70d9ee48793860eb34c295fff01c2e032b","F5.json":"45966e73316415626cf41a7d1c6f3b4c70dbc1ba2bee5c1978ef0ce33244fc8d","M1.json":"e35604687f5d23694b8e91593a93eec0e4eca6c0b02bb8ed69139ab2ea6b0a5b","M2.json":"b76cbf62bac707c710cf0ae5aba5e31eea1a6339a9734bfae33ab98499534a50","M3.json":"ea1ac35ccb91b0d7ecad533a2fbd0eec10c91513d8951e3b25fbba99954e159b","M4.json":"ca8eefad4fcd989c9379032ff3e50738adc547eeb5e221b82593a6d7b3bac303","M5.json":"dd22b92740314321f8ae11c5e87f8dd60d060f15dd3a632b5adf77f471f77af2"}
SOURCE_HASHES={"onnx/duration_predictor.onnx":"c3eb91414d5ff8a7a239b7fe9e34e7e2bf8a8140d8375ffb14718b1c639325db","onnx/text_encoder.onnx":"c7befd5ea8c3119769e8a6c1486c4edc6a3bc8365c67621c881bbb774b9902ff","onnx/vector_estimator.onnx":"883ac868ea0275ef0e991524dc64f16b3c0376efd7c320af6b53f5b780d7c61c","onnx/vocoder.onnx":"085de76dd8e8d5836d6ca66826601f615939218f90e519f70ee8a36ed2a4c4ba","onnx/tts.json":"42078d3aef1cd43ab43021f3c54f47d2d75ceb4e75f627f118890128b06a0d09","onnx/unicode_indexer.json":"9bf7346e43883a81f8645c81224f786d43c5b57f3641f6e7671a7d6c493cb24f"}
TOOL_HASHES={"scripts/supertonic/README.md":"ba2cf4871eda3f3a89f217d29a290ce875ad198d60c6eb356913ff2de09f63ea","scripts/supertonic/convert.py":"b6ceffd711ceffe1b34ad80b0dc46c7a9789207ff30718a884804e1898f262b7","scripts/supertonic/generate_voices_bin.py":"9479238b1866d37288159efcc2f929f3c6bc09d87f511bbd70b474b5739e93df","scripts/supertonic/run.sh":"e18165884bca7c30ae63b07b2768f581960b80d7fb8c6b0ceb752a1326897748"}
HASH = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

class ValidationError(RuntimeError): pass

def load(name: str):
    try: return json.loads((HERE / name).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise ValidationError(f"invalid {name}: {exc}") from exc

def validate(base: Path = HERE) -> None:
    global HERE; old=HERE; HERE=base
    try:
        inv, proof, desc, cfg, licenses, provenance = (load(x) for x in ("inventory.json", "m1-proof.json", "android-descriptor.json", "sherpa-config.json", "licenses.json", "conversion-provenance.json"))
        if inv.get("archive_filename") != ARCHIVE or inv.get("archive_sha256") != ARCHIVE_SHA or inv.get("precision") != "int8": raise ValidationError("wrong archive date, identity, or precision")
        entries=inv.get("files"); paths={x.get("path") for x in entries} if isinstance(entries,list) else set()
        if paths != MODEL_FILES | DATA_FILES | NOTICE_FILES or len(entries) != 9: raise ValidationError("inventory must exactly cover four INT8 models, three data files, and two notices")
        if {x["path"]:(x.get("bytes"),x.get("sha256")) for x in entries} != DEPLOYED: raise ValidationError("deployed-file pins drifted")
        if inv.get("total_bytes") != sum(x["bytes"] for x in entries): raise ValidationError("inventory total drift")
        expected_order=sorted(x["path"].split("/")[-1] for x in proof.get("source",{}).get("inputs",[]))
        voice_inputs={x.get("path","").split("/")[-1]:x.get("sha256") for x in proof.get("source",{}).get("inputs",[])}
        if (proof.get("status") != "proven" or proof.get("requested_voice") != "M1" or proof.get("selected_sid") != 5 or voice_inputs != VOICE_HASHES
            or proof.get("deterministic_order") != expected_order or expected_order[5] != "M1.json"
            or proof.get("conversion",{}).get("revision") != "3dc7c569f31ca2cd4a20ed6f7db780327e6714c5"
            or proof.get("conversion",{}).get("sha256") != "9479238b1866d37288159efcc2f929f3c6bc09d87f511bbd70b474b5739e93df"
            or proof.get("conversion",{}).get("ordering_expression") != 'sorted(input_dir.glob("*.json"))'
            or len(expected_order) != 10): raise ValidationError("M1 SID is not proven by pinned deterministic ordering")
        voice_hash=next(x["sha256"] for x in entries if x["path"] == "voice.bin")
        reproduction=proof.get("reproduction",{})
        if reproduction.get("result") != "byte-identical" or reproduction.get("rebuilt_voice_bin_sha256") != voice_hash or reproduction.get("archive_voice_bin_sha256") != voice_hash: raise ValidationError("voice.bin reproduction does not prove the mapping")
        source=provenance.get("source_model",{}); tooling=provenance.get("conversion_tooling",{})
        source_hashes={x.get("path"):x.get("sha256") for x in source.get("inputs",[])}
        tool_hashes={x.get("path"):x.get("sha256") for x in tooling.get("files",[])}
        if (source.get("revision") != "724fb5abbf5502583fb520898d45929e62f02c0b" or source_hashes != SOURCE_HASHES
            or tooling.get("revision") != "3dc7c569f31ca2cd4a20ed6f7db780327e6714c5" or tool_hashes != TOOL_HASHES
            or any(not isinstance(x.get("bytes"),int) or x["bytes"] <= 0 or not isinstance(x.get("sha256"),str) or len(x["sha256"]) != 64 for x in source.get("inputs",[])+tooling.get("files",[]))): raise ValidationError("conversion inputs/tooling are incomplete or unpinned")
        required_cfg={"model_type":"supertonic","duration_predictor":"models/supertonic-3/duration_predictor.int8.onnx","text_encoder":"models/supertonic-3/text_encoder.int8.onnx","vector_estimator":"models/supertonic-3/vector_estimator.int8.onnx","vocoder":"models/supertonic-3/vocoder.int8.onnx","tts_json":"models/supertonic-3/tts.json","unicode_indexer":"models/supertonic-3/unicode_indexer.bin","voice_style":"models/supertonic-3/voice.bin","lang":"en"}
        if cfg != required_cfg: raise ValidationError("sherpa config is not exact English Supertonic INT8")
        if desc.get("deployment_variant") != ARCHIVE.removesuffix(".tar.bz2") or desc.get("archive_sha256") != ARCHIVE_SHA or desc.get("provider") != "cpu" or desc.get("num_threads") != 1 or desc.get("speaker_id") != 5 or desc.get("voice") != "M1" or desc.get("language") != "en" or desc.get("storage") != "app_specific_external_files": raise ValidationError("descriptor drift (CPU/one-thread/English/M1/external storage required)")
        filepins=desc.get("files",{}); expected_deployed={"models/supertonic-3/"+x["path"]:x["sha256"] for x in entries}
        if any(filepins.get(k) != v for k,v in expected_deployed.items()) or filepins.get("models/supertonic-3/sherpa-config.json") != HASH(base/"sherpa-config.json"): raise ValidationError("descriptor does not pin every deployed file")
        notices=licenses.get("notices",[])
        if {x.get("spdx") for x in notices if x.get("spdx")} != {"MIT","LicenseRef-OpenRAIL-M"} or {x.get("path_in_archive") for x in notices if x.get("path_in_archive")} != NOTICE_FILES: raise ValidationError("MIT/OpenRAIL model notices are not both preserved")
        upstream=base/"licenses/LICENSE.OpenRAIL-M"; pin=next((x for x in notices if x.get("committed_path")),None)
        if pin is None or not upstream.is_file() or upstream.stat().st_size != pin.get("bytes") or HASH(upstream) != pin.get("sha256"): raise ValidationError("committed OpenRAIL-M notice drift")
        smoke=load("host-smoke.json")
        if smoke.get("evidence_type") != "host_configuration_smoke_not_android_performance" or smoke.get("runtime",{}).get("sherpa_onnx") != "1.13.5" or smoke.get("result") != "passed" or smoke.get("audio",{}).get("non_silent") is not True or smoke.get("audio",{}).get("fully_decoded") is not True or any(k in smoke for k in ("rtf","elapsed_seconds","generation_seconds")): raise ValidationError("host smoke is absent, invalid, unpinned, or presented as performance evidence")
    finally: HERE=old

def main():
    try: validate(); print("Supertonic 3 track: valid")
    except ValidationError as exc: print(f"validation error: {exc}",file=sys.stderr); return 2
    return 0
if __name__ == "__main__": raise SystemExit(main())

#!/usr/bin/env python3
"""Freeze canonical-v2 Kokoro official-frontend tokens and style.

The historical 0013/0017 sherpa lexicon is tested first and must fail closed at
its real OOV boundary. The comparable route then uses the pinned Kokoro 0.9.4
American-English KPipeline (Misaki 0.9.4) without loading the neural model.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import inspect
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

CANONICAL = {
    "bytes": 226,
    "sha256": "424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67",
}
OFFICIAL_CONFIG = {
    "bytes": 2351,
    "sha256": "5abb01e2403b072bf03d04fde160443e209d7a0dad49a423be15196b9b43c17f",
}
VOICE_F32 = {
    "bytes": 522240,
    "sha256": "d583ccff3cdca2f7fae535cb998ac07e9fcb90f09737b9a41fa2734ec44a8f0b",
}
EXPECTED = {
    "phoneme_codepoints": 233,
    "phoneme_utf8_bytes": 323,
    "phoneme_utf8_sha256": "7c7299c2d19943162b5bc85cebe116d16e534f336ac5bcb4fce40fe126a8b3a0",
    "token_shape": [1, 235],
    "token_little_endian_int64_sha256": "9c565b2a6ee1a811f188f3e3425a3188af58866988ce5a2197eeaacc81dde280",
    "style_index": 232,
}
VERSIONS = {
    "kokoro": "0.9.4",
    "misaki": "0.9.4",
    "phonemizer-fork": "3.3.2",
    "espeakng-loader": "0.2.4",
    "spacy": "3.8.15",
    "num2words": "0.5.14",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path, pin: dict[str, object], label: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"{label} is not a regular file: {path}")
    if path.stat().st_size != pin["bytes"] or sha256(path) != pin["sha256"]:
        raise RuntimeError(f"{label} pin mismatch: {path}")


def tree_record(root: Path) -> dict[str, object]:
    files = sorted(path for path in root.rglob("*") if path.is_file())
    digest = hashlib.sha256()
    total = 0
    for path in files:
        relative = path.relative_to(root).as_posix().encode()
        payload_digest = bytes.fromhex(sha256(path))
        digest.update(len(relative).to_bytes(4, "little"))
        digest.update(relative)
        digest.update(path.stat().st_size.to_bytes(8, "little"))
        digest.update(payload_digest)
        total += path.stat().st_size
    return {
        "path": str(root),
        "files": len(files),
        "bytes": total,
        "manifest_sha256": digest.hexdigest(),
        "manifest_definition": "sha256 over sorted (relative-path length/path, byte count, content sha256)",
    }


def token_record(token: object) -> dict[str, object]:
    return {
        "text": token.text,
        "tag": token.tag,
        "whitespace": token.whitespace,
        "phonemes": token.phonemes,
        "rating": getattr(token, "rating", None),
        "metadata": getattr(token, "_", None),
    }


def run_official(text: str, config: dict[str, object]) -> dict[str, object]:
    from kokoro import KPipeline

    pipeline = KPipeline(
        lang_code="a",
        repo_id="hexgrad/Kokoro-82M",
        model=False,
        trf=False,
    )
    results = list(pipeline(text, voice=None))
    if len(results) != 1:
        raise RuntimeError(f"canonical text chunk count drift: {len(results)}")
    result = results[0]
    if result.graphemes != text or result.text_index != 0:
        raise RuntimeError("effective grapheme text drift")
    phonemes = result.phonemes
    token_ids = [0, *(config["vocab"].get(value) for value in phonemes), 0]
    if any(value is None for value in token_ids):
        raise RuntimeError("official model vocabulary does not cover official phonemes")
    tokens = np.asarray(token_ids, dtype="<i8").reshape(1, -1)
    trace = [token_record(token) for token in result.tokens]
    return {
        "graphemes": result.graphemes,
        "phonemes": phonemes,
        "tokens": tokens,
        "trace": trace,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-text", type=Path, required=True)
    parser.add_argument("--official-config", type=Path, required=True)
    parser.add_argument("--voice-f32", type=Path, required=True)
    parser.add_argument("--sherpa-contract-tool", type=Path, required=True)
    parser.add_argument("--sherpa-tokens", type=Path, required=True)
    parser.add_argument("--sherpa-lexicon", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()

    verify(args.canonical_text, CANONICAL, "canonical v2 transcript")
    verify(args.official_config, OFFICIAL_CONFIG, "official config")
    verify(args.voice_f32, VOICE_F32, "lossless official voice tensor")
    raw_text = args.canonical_text.read_bytes()
    if raw_text.endswith(b"\n"):
        raise RuntimeError("canonical transcript unexpectedly has a trailing newline")
    text = raw_text.decode("utf-8")

    # Preserve why the old experiment-0013 sherpa frontend cannot be reused.
    module_spec = importlib.util.spec_from_file_location(
        "experiment_0013_kokoro_contract", args.sherpa_contract_tool
    )
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError("cannot load historical sherpa frontend tool")
    sherpa_contract = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = sherpa_contract
    module_spec.loader.exec_module(sherpa_contract)

    sherpa_failure = None
    try:
        sherpa_contract.frontend(text, args.sherpa_tokens, args.sherpa_lexicon)
    except sherpa_contract.ContractError as error:
        sherpa_failure = str(error)
    if sherpa_failure != "selected text is not fully covered by lexicon: 'makes'":
        raise RuntimeError(f"unexpected sherpa frontend result: {sherpa_failure!r}")

    actual_versions = {
        name: importlib.metadata.version(name) for name in VERSIONS
    }
    if actual_versions != VERSIONS:
        raise RuntimeError(f"frontend package version drift: {actual_versions}")

    config = json.loads(args.official_config.read_text())
    first = run_official(text, config)
    second = run_official(text, config)
    if first["graphemes"] != second["graphemes"]:
        raise RuntimeError("official frontend grapheme nondeterminism")
    if first["phonemes"] != second["phonemes"]:
        raise RuntimeError("official frontend phoneme nondeterminism")
    if not np.array_equal(first["tokens"], second["tokens"]):
        raise RuntimeError("official frontend token nondeterminism")
    if first["trace"] != second["trace"]:
        raise RuntimeError("official frontend trace nondeterminism")

    phonemes = first["phonemes"]
    tokens = first["tokens"]
    phoneme_bytes = phonemes.encode("utf-8")
    token_sha = hashlib.sha256(tokens.tobytes()).hexdigest()
    observed = {
        "phoneme_codepoints": len(phonemes),
        "phoneme_utf8_bytes": len(phoneme_bytes),
        "phoneme_utf8_sha256": hashlib.sha256(phoneme_bytes).hexdigest(),
        "token_shape": list(tokens.shape),
        "token_little_endian_int64_sha256": token_sha,
        "style_index": len(phonemes) - 1,
    }
    if observed != EXPECTED:
        raise RuntimeError(f"canonical frontend contract drift: {observed}")

    voice = np.fromfile(args.voice_f32, dtype="<f4").reshape(510, 1, 256)
    style = np.ascontiguousarray(voice[EXPECTED["style_index"]], dtype="<f4")
    speed = np.asarray([1.0], dtype="<f4")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tensors = {"tokens": tokens, "style": style, "speed": speed}
    tensor_records = {}
    for name, value in tensors.items():
        path = args.output_dir / f"{name}.raw"
        path.write_bytes(value.tobytes())
        tensor_records[name] = {
            "ignored_path": str(path),
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }

    import espeakng_loader
    import kokoro.pipeline
    import misaki.en
    import misaki.espeak

    espeak_library = Path(espeakng_loader.get_library_path())
    espeak_data = Path(espeakng_loader.get_data_path())
    sources = {
        "kokoro_pipeline.py": Path(inspect.getsourcefile(kokoro.pipeline)),
        "misaki_en.py": Path(inspect.getsourcefile(misaki.en)),
        "misaki_espeak.py": Path(inspect.getsourcefile(misaki.espeak)),
        "misaki_us_gold.json": Path(inspect.getsourcefile(misaki.en)).parent / "data/us_gold.json",
        "misaki_us_silver.json": Path(inspect.getsourcefile(misaki.en)).parent / "data/us_silver.json",
        "espeak_library": espeak_library,
    }
    source_records = {
        name: {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for name, path in sources.items()
    }

    trace_payload = json.dumps(
        first["trace"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    full_record = {
        "schema_version": 1,
        "transcript": {
            "path": str(args.canonical_text),
            "bytes": len(raw_text),
            "sha256": hashlib.sha256(raw_text).hexdigest(),
            "trailing_newline": False,
            "effective_graphemes_utf8_sha256": hashlib.sha256(
                first["graphemes"].encode("utf-8")
            ).hexdigest(),
        },
        "historical_sherpa_frontend": {
            "status": "failed_closed",
            "tool": {
                "path": str(args.sherpa_contract_tool),
                "bytes": args.sherpa_contract_tool.stat().st_size,
                "sha256": sha256(args.sherpa_contract_tool),
            },
            "exact_error": sherpa_failure,
            "classification": "The old 0013/0017 sherpa lexicon route cannot be canonical v2 and is not silently extended or relabeled.",
        },
        "official_frontend": {
            "status": "passed",
            "repository": "hexgrad/Kokoro-82M",
            "revision": "f3ff3571791e39611d31c381e3a41a3af07b4987",
            "implementation": "Kokoro 0.9.4 KPipeline American-English path",
            "configuration": {
                "lang_code_requested": "a",
                "language": "American English",
                "repo_id": "hexgrad/Kokoro-82M",
                "model": False,
                "trf": False,
                "british": False,
                "fallback": "misaki.espeak.EspeakFallback(british=False, version=None)",
                "fallback_backend_language": "en-us",
                "fallback_preserve_punctuation": True,
                "fallback_with_stress": True,
                "fallback_tie": "^",
                "g2p_unk": "",
                "split_pattern": r"\n+",
            },
            "versions": actual_versions,
            "python": sys.version.split()[0],
            "chunks": 1,
            "phonemes": phonemes,
            **observed,
            "misaki_token_count": len(first["trace"]),
            "misaki_rating_counts": {
                str(key): value
                for key, value in sorted(
                    Counter(
                        "null" if item["rating"] is None else item["rating"]
                        for item in first["trace"]
                    ).items(),
                    key=lambda item: str(item[0]),
                )
            },
            "misaki_token_trace_sha256": hashlib.sha256(trace_payload).hexdigest(),
            "determinism_runs": 2,
            "source_files": source_records,
            "espeak_data_tree": tree_record(espeak_data),
            "official_config": {
                "path": str(args.official_config),
                "bytes": args.official_config.stat().st_size,
                "sha256": sha256(args.official_config),
            },
        },
        "fixed_inputs": {
            "voice_source": {
                "path": str(args.voice_f32),
                "bytes": args.voice_f32.stat().st_size,
                "sha256": sha256(args.voice_f32),
            },
            "tensors": tensor_records,
        },
        "pending_fixed_shape": {
            "duration_sum": None,
            "audio_samples": None,
            "reason": "Requires the separately scheduled official-model CPU oracle; no model was loaded by this frontend tool.",
        },
        "claim_boundary": "Canonical-v2 official frontend and fixed input proof only; not a model export, inference, QNN assignment, physical HTP result, benchmark, or listening verdict.",
    }
    full_path = args.output_dir / "frontend-full.json"
    full_path.write_text(
        json.dumps(
            {**full_record, "official_frontend": {**full_record["official_frontend"], "misaki_token_trace": first["trace"], "token_ids": tokens.reshape(-1).tolist()}},
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )
    full_record["ignored_full_record"] = {
        "path": str(full_path),
        "bytes": full_path.stat().st_size,
        "sha256": sha256(full_path),
    }
    args.provenance.parent.mkdir(parents=True, exist_ok=True)
    args.provenance.write_text(
        json.dumps(full_record, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )
    print(
        json.dumps(
            {
                "transcript": full_record["transcript"],
                "historical_sherpa_frontend": full_record["historical_sherpa_frontend"],
                "official_frontend": {
                    key: full_record["official_frontend"][key]
                    for key in (
                        "chunks",
                        "phoneme_codepoints",
                        "phoneme_utf8_sha256",
                        "token_shape",
                        "token_little_endian_int64_sha256",
                        "style_index",
                    )
                },
                "fixed_inputs": tensor_records,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

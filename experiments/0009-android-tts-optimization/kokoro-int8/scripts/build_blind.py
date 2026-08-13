#!/usr/bin/env python3
"""Build a deterministic blind A/B package, keeping the answer key outside it."""
from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import html
import io
import re
import secrets
import zipfile
from pathlib import Path
from typing import Any

from common import EXPERIMENT_ROOT, load_json, sha256_file, write_json

FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def write_zip_member(archive: zipfile.ZipFile, name: str, content: bytes) -> None:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    archive.writestr(info, content)


def load_or_create_seed(path: Path) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        text = path.read_text(encoding="ascii").strip()
        if not re.fullmatch(r"[0-9a-f]{64}", text):
            raise RuntimeError("blind seed must contain exactly 32 bytes as lowercase hex")
        return bytes.fromhex(text)
    seed = secrets.token_bytes(32)
    path.write_text(seed.hex() + "\n", encoding="ascii")
    return seed


def verify_audio(item: dict[str, Any]) -> tuple[Path, str]:
    wav = item["wav"]
    path = EXPERIMENT_ROOT / wav["path"]
    if not path.is_file() or path.stat().st_size != wav["bytes"] or sha256_file(path) != wav["sha256"]:
        raise RuntimeError(f"audio evidence drifted: {path}")
    return path, wav["sha256"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fp32-report", type=Path, default=EXPERIMENT_ROOT / "reports" / "synthesis-fp32.json")
    parser.add_argument("--int8-report", type=Path, default=EXPERIMENT_ROOT / "reports" / "synthesis-int8.json")
    parser.add_argument("--seed-file", type=Path, default=EXPERIMENT_ROOT / "generated" / "blind" / "seed.hex")
    parser.add_argument("--package", type=Path, default=EXPERIMENT_ROOT / "generated" / "blind" / "kokoro-int8-listening.zip")
    parser.add_argument("--answer-key", type=Path, default=EXPERIMENT_ROOT / "generated" / "blind" / "answer-key.json")
    parser.add_argument("--report", type=Path, default=EXPERIMENT_ROOT / "reports" / "blind-package.json")
    args = parser.parse_args()

    fp32 = load_json(args.fp32_report)
    int8 = load_json(args.int8_report)
    if fp32["exact_shared_inputs"] != int8["exact_shared_inputs"]:
        raise RuntimeError("cannot blind unmatched synthesis runs")
    fp32_by_id = {item["id"]: item for item in fp32["outputs"]}
    int8_by_id = {item["id"]: item for item in int8["outputs"]}
    order = fp32["exact_shared_inputs"]["corpus_order"]
    if list(fp32_by_id) != order or list(int8_by_id) != order:
        raise RuntimeError("blind package inputs are incomplete or reordered")

    seed = load_or_create_seed(args.seed_file)
    answer_pairs: list[dict[str, Any]] = []
    package_pairs: list[dict[str, Any]] = []
    members: list[tuple[str, bytes]] = []
    ballot_buffer = io.StringIO(newline="")
    ballot = csv.writer(ballot_buffer, lineterminator="\n")
    ballot.writerow(["pair", "preferred (A/B/tie)", "confidence (1-5)", "notes"])
    guide_rows: list[str] = []

    for index, utterance_id in enumerate(order, start=1):
        fp32_path, fp32_digest = verify_audio(fp32_by_id[utterance_id])
        int8_path, int8_digest = verify_audio(int8_by_id[utterance_id])
        fp32_is_a = (hmac.new(seed, utterance_id.encode("utf-8"), hashlib.sha256).digest()[0] & 1) == 0
        labels = {
            "A": ("fp32", fp32_path, fp32_digest) if fp32_is_a else ("int8", int8_path, int8_digest),
            "B": ("int8", int8_path, int8_digest) if fp32_is_a else ("fp32", fp32_path, fp32_digest),
        }
        pair_name = f"pair-{index:02d}"
        for label in ("A", "B"):
            _, path, _ = labels[label]
            members.append((f"{pair_name}/{label}.wav", path.read_bytes()))
        text = fp32_by_id[utterance_id]["text"]
        ballot.writerow([pair_name, "", "", ""])
        guide_rows.append(
            f"<tr><td>{pair_name}</td><td>{html.escape(text)}</td><td>A / B / tie</td><td></td></tr>"
        )
        answer_pairs.append(
            {
                "pair": pair_name,
                "utterance_id": utterance_id,
                "A": {"variant": labels["A"][0], "wav_sha256": labels["A"][2]},
                "B": {"variant": labels["B"][0], "wav_sha256": labels["B"][2]},
            }
        )
        package_pairs.append({"pair": pair_name, "utterance_id": utterance_id})

    guide = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Kokoro blind A/B listening</title>
<style>body{{font:16px system-ui;max-width:1000px;margin:2rem auto;padding:0 1rem}}table{{border-collapse:collapse}}td,th{{border:1px solid #bbb;padding:.55rem;vertical-align:top}}</style>
<h1>Kokoro blind A/B listening</h1>
<p>Use headphones in a quiet setting. For each pair, play A and B at the same volume, alternating order between pairs. Judge intelligibility, voice identity, artifacts, prosody, pacing, and overall preference. Do not inspect file hashes or the separate answer key before returning the ballot.</p>
<p>A tie is valid. This package does not identify either model. The automated report does not claim subjective equivalence.</p>
<table><thead><tr><th>Pair</th><th>Text</th><th>Preference</th><th>Notes</th></tr></thead><tbody>{''.join(guide_rows)}</tbody></table>
</html>
""".encode("utf-8")
    readme = (
        "Kokoro blind A/B listening package\n\n"
        "Open listening-guide.html, listen to every A.wav and B.wav pair at matched volume, "
        "and return ballot.csv. The answer key is intentionally excluded.\n"
    ).encode("utf-8")
    members.extend(
        [
            ("README.txt", readme),
            ("ballot.csv", ballot_buffer.getvalue().encode("utf-8")),
            ("listening-guide.html", guide),
        ]
    )
    args.package.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.package.with_suffix(args.package.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", allowZip64=True) as archive:
        for name, content in sorted(members):
            write_zip_member(archive, name, content)
    temporary.replace(args.package)

    answer = {
        "schema_version": 1,
        "warning": "Keep separate from the listener until the ballot is final.",
        "assignment": "HMAC-SHA256(seed, utterance_id) low bit; deterministic for retained seed",
        "seed_hex": seed.hex(),
        "seed_sha256": hashlib.sha256(seed).hexdigest(),
        "pairs": answer_pairs,
    }
    write_json(args.answer_key, answer)
    expected_names = sorted(name for name, _ in members)
    answer_by_pair = {item["pair"]: item for item in answer_pairs}
    with zipfile.ZipFile(args.package) as archive:
        names = archive.namelist()
        if names != expected_names or len(names) != len(set(names)):
            raise RuntimeError("blind package member set or deterministic ordering drifted")
        if archive.testzip() is not None:
            raise RuntimeError("blind package CRC validation failed")
        if any(
            forbidden in name.casefold()
            for name in names
            for forbidden in ("answer", "seed", "fp32", "int8")
        ):
            raise RuntimeError("blind package leaks model identity or blinding material in member names")
        wav_names = [name for name in names if name.endswith(".wav")]
        if len(wav_names) != len(order) * 2:
            raise RuntimeError("blind package does not contain exactly two WAVs per pair")
        for info in archive.infolist():
            if info.date_time != FIXED_ZIP_TIME or info.compress_type != zipfile.ZIP_STORED:
                raise RuntimeError(f"non-deterministic ZIP metadata: {info.filename}")
        for name in wav_names:
            pair_name, filename = name.split("/", 1)
            label = filename.removesuffix(".wav")
            expected_digest = answer_by_pair[pair_name][label]["wav_sha256"]
            if hashlib.sha256(archive.read(name)).hexdigest() != expected_digest:
                raise RuntimeError(f"blind WAV payload does not match retained assignment: {name}")

    a_variants = [pair["A"]["variant"] for pair in answer_pairs]
    if abs(a_variants.count("fp32") - a_variants.count("int8")) > 1:
        raise RuntimeError("retained seed produces an unnecessarily imbalanced A/B assignment")

    report = {
        "schema_version": 1,
        "status": "ready_awaiting_user_listening",
        "listener": "Moritz",
        "package": {
            "path": args.package.resolve().relative_to(EXPERIMENT_ROOT).as_posix(),
            "bytes": args.package.stat().st_size,
            "sha256": sha256_file(args.package),
            "pair_count": len(order),
            "wav_count": len(order) * 2,
            "answer_key_included": False,
            "member_count": len(expected_names),
            "crc_validation_passed": True,
            "fixed_zip_timestamp": "1980-01-01T00:00:00",
            "stored_without_lossy_or_audio_recompression": True,
        },
        "answer_key": {
            "path": args.answer_key.resolve().relative_to(EXPERIMENT_ROOT).as_posix(),
            "bytes": args.answer_key.stat().st_size,
            "sha256": sha256_file(args.answer_key),
            "retained_outside_package": True,
        },
        "seed": {
            "path": args.seed_file.resolve().relative_to(EXPERIMENT_ROOT).as_posix(),
            "sha256_of_seed_bytes": hashlib.sha256(seed).hexdigest(),
            "retained_outside_package": True,
        },
        "pairs": package_pairs,
        "blinding": {
            "assignment_balanced": abs(a_variants.count("fp32") - a_variants.count("int8")) <= 1,
            "deterministic_from_retained_seed": True,
            "model_identity_absent_from_member_names": True,
            "payloads_verified_against_answer_key": True,
        },
        "subjective_verdict": "awaiting_user_listening",
    }
    write_json(args.report, report)
    print(f"blind package ready: {args.package} ({report['package']['sha256']})")
    print(f"answer key retained separately: {args.answer_key} ({report['answer_key']['sha256']})")


if __name__ == "__main__":
    main()

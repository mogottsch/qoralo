#!/usr/bin/env python3
"""Inspect saved prompt-bench results offline; never builds, installs, or runs a model."""

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def verify_saved_files():
    for line in (ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"saved evidence changed: {relative}")


def opening_words(text):
    return re.findall(r"[\w']+", text.lower())


def measure(chapters):
    texts = [chapter["text"] for chapter in chapters]
    lengths = [len(text) for text in texts]
    first_words = [opening_words(text)[0] for text in texts]
    vocabulary = [set(re.findall(r"[a-z']{4,}", text.lower())) for text in texts]
    overlap = [len(a & b) / max(1, len(a | b))
               for i, a in enumerate(vocabulary) for b in vocabulary[i + 1:]]
    return {
        "chapters": len(texts),
        "chars": sum(lengths),
        "length_spread": max(lengths) / min(lengths),
        "literal_greeting_starts": sum(bool(re.match(r"\s*(welcome\b|hello\b|hi\b|greetings\b)", text, re.I))
                                      for text in texts),
        "duplicate_first_words": len(first_words) - len(set(first_words)),
        "mean_vocabulary_overlap": sum(overlap) / len(overlap) if overlap else None,
        "openings": [" ".join(opening_words(text)[:3]) for text in texts],
    }


def main():
    verify_saved_files()
    scenario = json.loads((ROOT / "scenarios/sandyford.json").read_text(encoding="utf-8"))
    source = scenario["sources"][0]["text"]
    print("Saved-file hashes verified. Descriptive writing diagnostics, not quality scores or timing benchmarks.")
    print("run             chapters chars spread greeting repeated-first-word overlap elapsed-s")
    for name in ("bench-round1c", "bench-round2", "bench-round3", "bench-round3b"):
        result = json.loads((ROOT / f"evidence/{name}.json").read_text(encoding="utf-8"))
        if not (result["runId"] == name and result["outcome"] == "complete" and
                result["jobStatus"] == "COMPLETE" and result["instructions"] == scenario["instructions"] and
                result["sourceChars"] == len(source)):
            raise ValueError(f"saved result identity/status does not match the scenario: {name}")
        chapters = result["chapters"]
        if not chapters or any(not c["text"].strip() for c in chapters):
            raise ValueError(f"empty transcript: {name}")
        if [c["position"] for c in chapters] != list(range(len(chapters))):
            raise ValueError(f"unexpected chapter order: {name}")
        m = measure(chapters)
        print(f"{name:15} {m['chapters']:8} {m['chars']:5} {m['length_spread']:6.2f} "
              f"{m['literal_greeting_starts']:8} {m['duplicate_first_words']:19} "
              f"{m['mean_vocabulary_overlap']:7.3f} {result['elapsedMs'] / 1000:9.1f}")
        print("  " + " | ".join(m["openings"]))


if __name__ == "__main__":
    main()

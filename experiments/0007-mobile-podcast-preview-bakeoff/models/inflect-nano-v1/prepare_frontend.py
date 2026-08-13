#!/usr/bin/env python3
"""Fetch immutable tokenizer and NLTK frontend assets, then verify every byte."""
from __future__ import annotations

import urllib.request
import zipfile
from pathlib import Path

from track import NLTK_DATA, PINS, TOKENIZER, verify_frontend_assets


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    temporary = destination.with_suffix(destination.suffix + ".partial")
    with urllib.request.urlopen(url, timeout=60) as response, temporary.open("xb") as stream:
        while chunk := response.read(1024 * 1024):
            stream.write(chunk)
    temporary.replace(destination)


def main() -> None:
    tokenizer = PINS["frontend_assets"]["bert_tokenizer"]
    for relative in tokenizer["files"]:
        download(
            f"https://huggingface.co/{tokenizer['repository']}/raw/{tokenizer['revision']}/{relative}",
            TOKENIZER / relative,
        )
    nltk = PINS["frontend_assets"]["nltk_data"]
    for relative, metadata in nltk["files"].items():
        download(
            f"https://raw.githubusercontent.com/{nltk['repository']}/{nltk['revision']}/{metadata['source']}",
            NLTK_DATA / relative,
        )
    verify_frontend_assets()
    # NLTK 3.10 loads the English tagger JSON from an extracted directory.
    tagger = NLTK_DATA / "taggers" / "averaged_perceptron_tagger_eng.zip"
    extracted = NLTK_DATA / "taggers" / "averaged_perceptron_tagger_eng"
    if not extracted.is_dir():
        with zipfile.ZipFile(tagger) as archive:
            archive.extractall(NLTK_DATA / "taggers")
    print("Pinned Inflect-Nano-v1 frontend assets verified")


if __name__ == "__main__":
    main()

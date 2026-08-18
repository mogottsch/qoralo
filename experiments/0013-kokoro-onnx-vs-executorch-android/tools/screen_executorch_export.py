#!/usr/bin/env python3
"""Reproduce the bounded Kokoro torch.export / ExecuTorch capability screen."""
from __future__ import annotations

import argparse
import json
import time
import traceback
from pathlib import Path
from typing import Callable

import torch
from kokoro import KModel
from kokoro.model import KModelForONNX

from executorch_wrapper import FixedContractKokoro
from kokoro_contract import frontend, sha256_file

MODEL_SHA = "496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4"
VOICE_SHA = "0ab5709b8ffab19bfd849cd11d98f75b60af7733253ad0d67b12382a102cb4ff"


def capture(label: str, module: torch.nn.Module, args: tuple[torch.Tensor, ...], strict: bool, log_dir: Path) -> dict[str, object]:
    started = time.perf_counter()
    try:
        program = torch.export.export(module, args, strict=strict)
        torch.export.save(program, log_dir / f"{label}-strict-{strict}.pt2")
        return {"label": label, "strict": strict, "status": "passed", "seconds": time.perf_counter() - started}
    except Exception as error:
        trace = traceback.format_exc()
        trace_path = log_dir / f"{label}-strict-{strict}.traceback.txt"
        trace_path.write_text(trace, encoding="utf-8")
        return {
            "label": label,
            "strict": strict,
            "status": "failed",
            "seconds": time.perf_counter() - started,
            "exception_type": f"{type(error).__module__}.{type(error).__name__}",
            "message": str(error),
            "traceback_path": trace_path.name,
            "traceback_sha256": sha256_file(trace_path),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--voice", type=Path, required=True)
    parser.add_argument("--tokens", type=Path, required=True)
    parser.add_argument("--lexicon", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--log-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sha256_file(args.model) != MODEL_SHA or sha256_file(args.voice) != VOICE_SHA:
        raise RuntimeError("official source pin mismatch")
    contract = frontend(args.transcript.read_text(encoding="utf-8"), args.tokens, args.lexicon)
    tokens = torch.tensor(contract.segments[0], dtype=torch.long).unsqueeze(0)
    voice = torch.load(args.voice, map_location="cpu", weights_only=True)[contract.style_indices[0]]
    speed = torch.tensor([1.0], dtype=torch.float32)
    inputs = (tokens, voice, speed)
    args.log_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)

    def model() -> KModel:
        return KModel(repo_id="not-used", model=str(args.model), config=str(args.config), disable_complex=False).cpu().eval()

    attempts = []
    exact = KModelForONNX(model()).eval()
    for strict in (True, False): attempts.append(capture("exact-source", exact, inputs, strict, args.log_dir))
    del exact
    eager_attention_model = model(); eager_attention_model.bert.config._attn_implementation = "eager"
    eager_attention = KModelForONNX(eager_attention_model).eval()
    for strict in (True, False): attempts.append(capture("eager-attention", eager_attention, inputs, strict, args.log_dir))
    del eager_attention, eager_attention_model
    fixed = FixedContractKokoro(model()).eval()
    for strict in (True, False): attempts.append(capture("fixed-no-padding", fixed, inputs, strict, args.log_dir))
    document = {
        "schema_version": 1,
        "source_model_sha256": MODEL_SHA,
        "source_voice_sha256": VOICE_SHA,
        "torch": torch.__version__,
        "attempts": attempts,
        "full_model_export_succeeded": any(x["status"] == "passed" for x in attempts),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["full_model_export_succeeded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

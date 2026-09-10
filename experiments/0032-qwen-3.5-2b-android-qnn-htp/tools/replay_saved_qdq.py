#!/usr/bin/env python3
"""Replay a hash-bound saved QDQ graph with durable per-position checkpoints.

Host only. This is teacher-forced replay of the 174 canonical short input tokens,
not autoregressive generation or a benchmark campaign. Fresh output, progress,
final-logit and per-position-logit paths are reserved before loading a graph.
The journal and raw per-position logits survive failure/interruption. Never resumes or
retries automatically. Requires a separately coordinated heavy-host release.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import signal
import struct
import tempfile
import time
import traceback

SHORT_TOKENS = 174
SHORT_IDS_SHA256 = "dcfd3c24cb3f8a370f91b38c9720d7e3dd5c623d491fed70ded3726ec49048f4"
EXPERIMENT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = EXPERIMENT / "results/host-histogram-precision-20260910/artifact-manifest.json"


class ReplayInterrupted(BaseException):
    def __init__(self, signum):
        self.signum = signum
        super().__init__(f"Replay interrupted by signal {signum}")


@contextmanager
def interruption_signals():
    def interrupt(signum, frame):
        raise ReplayInterrupted(signum)

    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        for sig in previous:
            signal.signal(sig, interrupt)
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def artifact(path: Path) -> dict:
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest}


def read_short_ids(path: Path, context: int) -> list[int]:
    raw = path.read_bytes()
    if len(raw) != 4 * SHORT_TOKENS:
        raise ValueError("Expected exactly 174 little-endian int32 input tokens")
    if hashlib.sha256(raw).hexdigest() != SHORT_IDS_SHA256:
        raise ValueError("Canonical short token-ID SHA-256 mismatch")
    if SHORT_TOKENS + 2048 > context:
        raise ValueError("Canonical prompt plus 2048-token ceiling exceeds context")
    return list(struct.unpack(f"<{SHORT_TOKENS}i", raw))


def verify_inputs(args, result: dict) -> None:
    manifest_bytes = args.artifact_manifest.read_bytes()
    manifest = json.loads(manifest_bytes)["files"]
    result["artifact_manifest"] = artifact(args.artifact_manifest)
    result["input_artifacts"] = {}
    for name, entry_key in (("params", "params"), ("token_ids", "input_ids"), ("qdq_file", "histogram_qdq")):
        observed = artifact(getattr(args, name))
        result["input_artifacts"][name] = observed
        expected = manifest[entry_key]
        if (observed["sha256"], observed["bytes"]) != (expected["sha256"], expected["bytes"]):
            raise ValueError(f"Artifact identity mismatch: {name}")


def _atomic_write(path: Path, writer) -> None:
    # Replace only a path reserved by this invocation; temporary files are local
    # to its directory, so a signal cannot leave the previous checkpoint torn.
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as destination:
            writer(destination)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


class Evidence:
    def __init__(self, args):
        self.output = args.output
        self.logits = args.logits
        self.progress = args.progress
        self.steps = Path(str(args.logits) + ".steps")
        paths = (self.output, self.logits, self.progress, self.steps)
        inputs = (args.params, args.token_ids, args.qdq_file, args.artifact_manifest)
        resolved = [p.resolve() for p in paths]
        if len(set(resolved)) != len(paths) or set(resolved) & {p.resolve() for p in inputs}:
            raise ValueError("Output paths must be distinct and must not alias inputs")
        if any(os.path.lexists(p) for p in paths):
            raise FileExistsError("Use fresh output/logit/progress paths; no overwrite or resume")
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation rejects symlinks and concurrent reservations.
            if path == self.steps:
                path.mkdir()
            else:
                with path.open("xb"):
                    pass

    def checkpoint(self, result: dict) -> None:
        raw = (json.dumps(result, indent=2, allow_nan=False) + "\n").encode()
        _atomic_write(self.output, lambda f: f.write(raw))

    def save_logits(self, logits, position: int) -> dict:
        import torch
        path = self.steps / f"position-{position:03d}.pt"
        with path.open("xb"):
            pass
        _atomic_write(path, lambda f: torch.save(logits, f))
        return artifact(path)

    def save_final_logits(self, logits) -> dict:
        import torch
        _atomic_write(self.logits, lambda f: torch.save(logits, f))
        return artifact(self.logits)

    def append(self, record: dict) -> None:
        with self.progress.open("a", encoding="utf-8") as journal:
            journal.write(json.dumps(record, allow_nan=False) + "\n")
            journal.flush()
            os.fsync(journal.fileno())


def summarize_logits(logits) -> dict:
    import torch
    values = logits.detach().float().reshape(-1)
    if not values.numel():
        raise ValueError("Empty next-token logit tensor")
    finite = bool(torch.isfinite(values).all())
    result = {
        "shape": list(logits.shape), "numel": values.numel(), "finite": finite,
        "nan_count": int(torch.isnan(values).sum()), "inf_count": int(torch.isinf(values).sum()),
        "argmax": None, "top_ids": [], "top_logits": [],
    }
    if finite:
        top_values, top_ids = torch.topk(values, min(10, values.numel()))
        result.update({
            # torch.argmax chooses the first index on a tie; topk tie order may differ.
            "argmax": int(values.argmax()), "top_ids": top_ids.tolist(),
            "top_logits": top_values.tolist(), "min": float(values.min()),
            "max": float(values.max()), "max_count": int((values == values.max()).sum()),
        })
    return result


def advance_state(config, states, outputs, position: int) -> None:
    n = config.n_layers
    if len(outputs) < 1 + 2 * n:
        raise ValueError("Missing required state outputs")
    for layer, kind in enumerate(config.layer_types):
        a, b = states[layer], states[n + layer]
        next_a, next_b = outputs[1 + layer], outputs[1 + n + layer]
        if kind == "linear_attention":
            if next_a.shape != a.shape or next_b.shape != b.shape:
                raise ValueError(f"Recurrent/convolution state geometry mismatch: layer {layer}")
            # Clone even if outputs alias inputs or reusable runtime buffers.
            states[layer] = next_a.detach().clone()
            states[n + layer] = next_b.detach().clone()
        elif kind == "full_attention":
            if next_a.shape != a[..., :1].shape or next_b.shape != b[:, :, :1, :].shape:
                raise ValueError(f"KV update geometry mismatch: layer {layer}")
            a[..., position].copy_(next_a[..., 0])
            b[:, :, position, :].copy_(next_b[:, :, 0, :])
        else:
            raise ValueError(f"Unknown layer type: {kind}")
    # Optional diagnostic hidden/component tensors after these outputs are ignored.


def load_runtime(params: Path, qdq_file: Path, context: int):
    import torch
    import qwen35_qnn_model  # noqa: F401 -- registers qwen35::softplus before PT2 load
    import torchao.quantization.pt2e.quantize_pt2e  # noqa: F401
    from executorch.examples.models.llama.model_args import ModelArgs
    config = ModelArgs(
        max_seq_len=context, max_context_len=context, max_batch_size=1,
        use_kv_cache=True, **json.loads(params.read_text())
    )
    return torch.export.load(qdq_file).module(), config


def run_replay(args, runtime_loader=load_runtime) -> dict:
    # Reserve before any input/model access. Existing artifacts are never changed.
    evidence = Evidence(args)
    started = time.perf_counter()
    result = {
        "schema_version": 1,
        "evidence_class": "host_saved_histogram_w4a16_qdq_full_short_replay",
        "status": "started_not_complete", "phase": "preflight",
        "prompt_tokens": SHORT_TOKENS, "context_tokens": args.context,
        "evaluated_tokens": 0, "state_updates_completed": 0,
        "last_input_position": None, "last_logits": None, "logits_artifact": None,
        "final_logits": None, "final_logits_artifact": None, "physical_execution": False,
        "progress_path": str(args.progress), "automatic_retry": False,
        "claim_limits": [
            "Host PT2E QDQ replay only; no QNN or Android execution in this phase.",
            "Teacher-forced input replay with computed next-token logits, not an autoregressive text sample or campaign.",
            "Per-position raw logits and the journal are checkpoints, not a resumable KV-state snapshot.",
            "A forced SIGKILL/power loss may leave started_not_complete with the last durable checkpoint; never infer completion.",
        ],
    }
    try:
        evidence.checkpoint(result)
        ids = read_short_ids(args.token_ids, args.context)
        verify_inputs(args, result)
        result["phase"] = "load"
        evidence.checkpoint(result)
        graph, config = runtime_loader(args.params, args.qdq_file, args.context)
        import torch
        from diagnose_quantized_output import make_state_templates
        if config.n_layers != len(config.layer_types):
            raise ValueError("Layer configuration does not match state ABI")
        states = make_state_templates(config, args.context)
        result["threads"] = torch.get_num_threads()
        result["phase"] = "replay"
        evidence.checkpoint(result)
        with torch.no_grad():
            for position, token in enumerate(ids):
                result["current_input_position"] = position
                mask = torch.full((1, 1, 1, args.context), -65504.0)
                mask[..., :position] = 0.0
                mask[..., -1] = 0.0
                outputs = graph(
                    torch.tensor([[token]], dtype=torch.int32), mask,
                    torch.tensor([[position]], dtype=torch.int32), *states,
                )
                # Persist actual output before summary/state validation can fail.
                logits = outputs[0].detach().cpu().clone()
                result["logits_artifact"] = evidence.save_logits(logits, position)
                result["last_input_position"] = position
                result["evaluated_tokens"] = position + 1
                result["last_logits"] = None
                summary = summarize_logits(logits)
                result["last_logits"] = summary
                evidence.append({"position": position, "input_token": token, "logits": summary, "artifact": result["logits_artifact"]})
                evidence.checkpoint(result)
                if not summary["finite"]:
                    raise FloatingPointError("Nonfinite logits; raw tensor retained")
                advance_state(config, states, outputs, position)
                result["state_updates_completed"] = position + 1
                evidence.checkpoint(result)
                if position == 0 or (position + 1) % 10 == 0 or position + 1 == len(ids):
                    print(f"histogram_qdq: token {position + 1}/{len(ids)}, argmax={summary['argmax']}", flush=True)
        result["final_logits_artifact"] = evidence.save_final_logits(logits)
        result.update(status="completed", phase="finished", final_logits=result["last_logits"])
    except BaseException as error:
        # Includes TERM/INT raised by the CLI handler. Re-raise after persisting;
        # failure must be visible to the outer resource supervisor, not exit 0.
        result["status"] = "interrupted" if isinstance(error, (ReplayInterrupted, KeyboardInterrupt)) else "error"
        result["error"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
        result["elapsed_seconds"] = time.perf_counter() - started
        result["progress_artifact"] = artifact(evidence.progress)
        evidence.checkpoint(result)
        raise
    result["elapsed_seconds"] = time.perf_counter() - started
    result["progress_artifact"] = artifact(evidence.progress)
    evidence.checkpoint(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--params", type=Path, required=True)
    parser.add_argument("--token-ids", type=Path, required=True)
    parser.add_argument("--qdq-file", type=Path, required=True)
    parser.add_argument("--artifact-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--logits", type=Path, required=True)
    parser.add_argument("--progress", type=Path, required=True)
    parser.add_argument("--context", type=int, default=4096)
    args = parser.parse_args()
    try:
        with interruption_signals():
            result = run_replay(args)
    except ReplayInterrupted as error:
        raise SystemExit(128 + error.signum)
    print(json.dumps(result["final_logits"], allow_nan=False), flush=True)


if __name__ == "__main__":
    main()

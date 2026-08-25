#!/usr/bin/env python3
"""Persistence-first client for one loaded llama.cpp server benchmark route."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import time
import urllib.parse
import urllib.request
from pathlib import Path

WORKLOAD_HASHES = {
    "short": "81d23ec04cb821625d3717ab50db7df3d9821a8d2987f1eb107fc90df9d1f2ae",
    "medium": "5e168aa3232f06c92959b686188192471b2d1a62cd1c857a616fd8e29456ddf1",
    "long": "092840fbe879259110fa4d0b15bc383012f16b7b42a38d224b2ead231e86aad8",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ids_sha(ids: list[int]) -> str:
    return sha(b"".join(struct.pack("<i", token) for token in ids))


def durable_json(path: Path, value: object) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


class Client:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def json(self, path: str, payload: object | None = None, timeout: int = 1800):
        body = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            self.base + path,
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)

    def stream(self, path: str, payload: object, timeout: int = 1800):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        return urllib.request.urlopen(request, timeout=timeout)


def wait_for_health(client: Client, deadline_seconds: int) -> tuple[int, dict]:
    started = time.monotonic_ns()
    deadline = time.monotonic() + deadline_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            health = client.json("/health", timeout=2)
            if health.get("status") == "ok":
                return time.monotonic_ns() - started, health
        except Exception as error:  # model load returns HTTP 503 until ready
            last_error = repr(error)
        time.sleep(0.1)
    raise TimeoutError(f"server health deadline exceeded: {last_error}")


def sequence(mode: str) -> list[tuple[str, str, str, int]]:
    if mode == "smoke":
        return [("smoke-short-01", "short", "smoke", 64)]
    result = [("first-short-01", "short", "first", 2048)]
    result += [(f"short-{index:02d}", "short", "warm", 2048) for index in range(1, 6)]
    result += [(f"medium-{index:02d}", "medium", "warm", 2048) for index in range(1, 6)]
    result += [(f"long-{index:02d}", "long", "warm", 2048) for index in range(1, 6)]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8027")
    parser.add_argument("--mode", choices=["smoke", "campaign"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workloads", type=Path, required=True)
    parser.add_argument("--setup-start-monotonic-ns", type=int)
    parser.add_argument("--health-deadline-seconds", type=int, default=600)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "outputs").mkdir()
    (args.output / "events").mkdir()
    (args.output / "rendered").mkdir()
    client = Client(args.base)
    health_wait_ns, health = wait_for_health(client, args.health_deadline_seconds)
    ready_ns = time.monotonic_ns()
    setup_ns = None if args.setup_start_monotonic_ns is None else ready_ns - args.setup_start_monotonic_ns

    workloads: dict[str, dict] = {}
    for tier in ("short", "medium", "long"):
        path = args.workloads / f"{tier}.json"
        raw = path.read_bytes()
        if sha(raw) != WORKLOAD_HASHES[tier]:
            raise ValueError(f"wrong canonical workload hash: {tier}")
        workloads[tier] = json.loads(raw)

    result = {
        "schema_version": 1,
        "scope": "android_smoke" if args.mode == "smoke" else "android_campaign",
        "mode": args.mode,
        "health": health,
        "setup": {
            "boundary": "host monotonic timestamp immediately before remote llama-server launch through first successful /health ready response",
            "seconds": None if setup_ns is None else setup_ns / 1e9,
            "health_poll_seconds_inside_boundary": health_wait_ns / 1e9,
        },
        "route": {
            "backend": "llama.cpp CPU",
            "threads": 4,
            "context_tokens": 8192,
            "thinking_enabled": False,
            "thinking_control": {"chat_template_kwargs": {"enable_thinking": False}},
            "sampler": "greedy argmax through temperature=-1 and temperature-only sampler chain",
            "cache_prompt": False,
            "slot_erase_before_every_request": True,
        },
        "prompts": {},
        "runs": [],
    }
    durable_json(args.output / "result.partial.json", result)

    expected_prompt: dict[str, tuple[str, list[int]]] = {}
    for run_id, tier, phase, output_cap in sequence(args.mode):
        erase = client.json("/slots/0?action=erase", {})
        request_start_ns = time.monotonic_ns()
        work = workloads[tier]
        template_request = {
            "messages": work["messages"],
            "chat_template_kwargs": {"enable_thinking": False},
        }
        rendered_response = client.json("/apply-template", template_request)
        rendered = rendered_response["prompt"]
        rendered_done_ns = time.monotonic_ns()
        tokens_response = client.json(
            "/tokenize", {"content": rendered, "add_special": False, "parse_special": True}
        )
        token_ids = tokens_response["tokens"]
        tokenization_done_ns = time.monotonic_ns()
        if len(token_ids) + 2048 > 8192:
            raise ValueError(f"{tier}: prompt plus ceiling exceeds context")
        if not rendered.endswith("<think>\n\n</think>\n\n"):
            raise ValueError(f"{tier}: enable_thinking=false suffix not applied")
        if tier in expected_prompt and expected_prompt[tier] != (rendered, token_ids):
            raise ValueError(f"{tier}: rendered bytes or token IDs changed within campaign")
        expected_prompt[tier] = (rendered, token_ids)
        rendered_path = args.output / "rendered" / f"{tier}.txt"
        if not rendered_path.exists():
            rendered_path.write_bytes(rendered.encode())
        prompt_record = {
            "workload_path": f"{tier}.json",
            "workload_sha256": WORKLOAD_HASHES[tier],
            "rendered_path": f"rendered/{tier}.txt",
            "rendered_bytes": len(rendered.encode()),
            "rendered_sha256": sha(rendered.encode()),
            "input_tokens": len(token_ids),
            "token_ids_int32le_sha256": ids_sha(token_ids),
            "max_output_tokens": 2048,
            "context_tokens": 8192,
            "truncated": False,
            "thinking_proof": {
                "enable_thinking": False,
                "ends_with_empty_think_block": True,
                "required_suffix": "<think>\\n\\n</think>\\n\\n",
            },
        }
        result["prompts"][tier] = prompt_record

        request_payload = {
            "prompt": rendered,
            "n_predict": output_cap,
            "temperature": -1.0,
            "samplers": ["temperature"],
            "repeat_penalty": 1.0,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            "dry_multiplier": 0.0,
            "cache_prompt": False,
            "return_tokens": True,
            "stream": True,
            "seed": 0,
            "timings_per_token": False,
        }
        run = {
            "id": run_id,
            "tier": tier,
            "phase": phase,
            "request_timeout_seconds": 1800,
            "output_token_cap": output_cap,
            "slot_erase_response": erase,
            "request": request_payload,
            "request_start_monotonic_ns": request_start_ns,
            "render_done_monotonic_ns": rendered_done_ns,
            "tokenization_done_monotonic_ns": tokenization_done_ns,
            "events_path": f"events/{run_id}.jsonl",
            "output_path": f"outputs/{run_id}.txt",
            "status": "in_progress",
        }
        result["runs"].append(run)
        durable_json(args.output / "result.partial.json", result)

        events_path = args.output / run["events_path"]
        output_path = args.output / run["output_path"]
        emitted_ids: list[int] = []
        first_token_ns = None
        final_event = None
        with events_path.open("w", encoding="utf-8") as events, output_path.open("w", encoding="utf-8") as output:
            try:
                with client.stream("/completion", request_payload, timeout=1800) as response:
                    for raw_line in response:
                        received_ns = time.monotonic_ns()
                        line = raw_line.decode("utf-8").strip()
                        if not line or line.startswith(":") or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            continue
                        event = json.loads(data)
                        event["client_received_monotonic_ns"] = received_ns
                        events.write(json.dumps(event, sort_keys=True) + "\n")
                        events.flush()
                        os.fsync(events.fileno())
                        chunk = event.get("content", "")
                        if chunk:
                            output.write(chunk)
                            output.flush()
                            os.fsync(output.fileno())
                        ids = event.get("tokens", [])
                        if ids and first_token_ns is None:
                            first_token_ns = received_ns
                        emitted_ids.extend(ids)
                        if event.get("stop"):
                            final_event = event
            except Exception as error:
                run["runtime_error"] = repr(error)

        end_ns = time.monotonic_ns()
        output_bytes = output_path.read_bytes()
        run.update({
            "status": "complete" if final_event is not None else "error",
            "request_end_monotonic_ns": end_ns,
            "runtime_error": run.get("runtime_error"),
            "final_event": final_event,
            "output_bytes": len(output_bytes),
            "output_sha256": sha(output_bytes),
            "output_tokens": len(emitted_ids),
            "emitted_token_ids_int32le_sha256": ids_sha(emitted_ids),
            "timing": {
                "render_seconds": (rendered_done_ns - request_start_ns) / 1e9,
                "tokenization_seconds": (tokenization_done_ns - rendered_done_ns) / 1e9,
                "request_to_first_token_seconds": None if first_token_ns is None else (first_token_ns - request_start_ns) / 1e9,
                "decode_first_to_final_delivery_seconds": None if first_token_ns is None else (end_ns - first_token_ns) / 1e9,
                "total_seconds": (end_ns - request_start_ns) / 1e9,
            },
            "missing_reasons": {},
        })
        if first_token_ns is None:
            run["missing_reasons"]["timing.request_to_first_token_seconds"] = "No generated token was delivered."
            run["missing_reasons"]["timing.decode_first_to_final_delivery_seconds"] = "No generated token was delivered."
        if final_event is None:
            run["stop_reason"] = "error"
            run["missing_reasons"]["runtime_timings"] = "No final server event was delivered."
        else:
            stop_map = {"eos": "eos", "limit": "max_tokens", "word": "stop_sequence"}
            run["stop_reason"] = stop_map.get(final_event.get("stop_type"), "error")
            server_timings = final_event.get("timings", {})
            run["server_timings"] = server_timings
            run["timing"]["prefill_seconds"] = server_timings.get("prompt_ms", None)
            if run["timing"]["prefill_seconds"] is not None:
                run["timing"]["prefill_seconds"] /= 1000.0
            run["timing"]["post_prefill_to_first_token_seconds"] = None
            run["missing_reasons"]["timing.post_prefill_to_first_token_seconds"] = (
                "llama.cpp server reports aggregate prompt_ms but does not expose a server-clock first-token timestamp alignable to it."
            )
            run["throughput"] = {
                "prefill_input_tokens_per_second": server_timings.get("prompt_per_second"),
                "prefill_input_tokens": server_timings.get("prompt_n"),
                "runtime_decode_tokens_per_second": server_timings.get("predicted_per_second"),
                "runtime_decode_tokens": server_timings.get("predicted_n"),
                "runtime_decode_first_token_included": True,
                "external_decode_tokens_per_second": (
                    None if len(emitted_ids) <= 1 or not run["timing"]["decode_first_to_final_delivery_seconds"]
                    else (len(emitted_ids) - 1) / run["timing"]["decode_first_to_final_delivery_seconds"]
                ),
                "external_decode_tokens": max(0, len(emitted_ids) - 1),
                "external_decode_first_token_included": False,
            }
        validation_errors = []
        if final_event is not None:
            if final_event.get("truncated"):
                validation_errors.append("server reported truncation")
            # tokens_cached is the slot's post-request cache size, not reused input.
            # The authoritative reused-prefix count is timings.cache_n.
            if server_timings.get("cache_n") != 0:
                validation_errors.append(
                    f"prompt cache reused or unproved: cache_n={server_timings.get('cache_n')!r}"
                )
            if server_timings.get("prompt_n") != len(token_ids):
                validation_errors.append(
                    f"full prompt was not evaluated: prompt_n={server_timings.get('prompt_n')!r}, expected={len(token_ids)}"
                )
            prompt_ms = server_timings.get("prompt_ms")
            if not isinstance(prompt_ms, (int, float)) or prompt_ms <= 0:
                validation_errors.append(f"prefill was not plausibly nonzero: prompt_ms={prompt_ms!r}")
        run["reset_validation"] = {
            "slot_erase_succeeded": erase.get("id_slot") == 0,
            "cache_n_zero": final_event is not None and server_timings.get("cache_n") == 0,
            "full_prompt_evaluated": final_event is not None and server_timings.get("prompt_n") == len(token_ids),
            "prefill_nonzero": final_event is not None and isinstance(server_timings.get("prompt_ms"), (int, float)) and server_timings["prompt_ms"] > 0,
            "errors": validation_errors,
        }
        if not run["reset_validation"]["slot_erase_succeeded"]:
            validation_errors.append("slot erase response did not confirm slot 0")
        run["output_sanity"] = {"looks_sensible": None, "issue_notes": None}
        durable_json(args.output / "result.partial.json", result)
        if validation_errors:
            raise ValueError(f"{run_id}: " + "; ".join(validation_errors))

    result["status"] = "complete"
    durable_json(args.output / "result.json", result)
    (args.output / "result.partial.json").unlink()
    print(args.output / "result.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Copy a completed phone run into committed, hash-bound experiment evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_key_values(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def parse_battery(path: Path) -> dict:
    values: dict[str, str] = {}
    for line in path.read_text(errors="replace").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    def integer(key: str):
        try: return int(values[key])
        except (KeyError, ValueError): return None
    plugged_code = integer("plugged")
    return {
        "level_percent": integer("level"),
        "temperature_c": None if integer("temperature") is None else integer("temperature") / 10.0,
        "status_code": integer("status"),
        "plugged_code": plugged_code,
        "plugged_code_missing_reason": None if plugged_code is not None else (
            "dumpsys battery did not expose a plugged field; the individual AC/USB/wireless booleans are retained."
        ),
        "ac_powered": values.get("AC powered") == "true" if "AC powered" in values else None,
        "usb_powered": values.get("USB powered") == "true" if "USB powered" in values else None,
        "wireless_powered": values.get("Wireless powered") == "true" if "Wireless powered" in values else None,
    }


def parse_thermal(path: Path) -> dict:
    text = path.read_text(errors="replace")
    match = re.search(r"Thermal Status:\s*(\d+)", text, re.I)
    return {
        "status_code": int(match.group(1)) if match else None,
        "status_missing_reason": None if match else "dumpsys thermalservice did not expose a summary Thermal Status field.",
    }


def parse_power(path: Path) -> dict:
    text = path.read_text(errors="replace")
    match = re.search(r"mWakefulness=([^\s]+)", text)
    return {
        "wakefulness": match.group(1) if match else None,
        "wakefulness_missing_reason": None if match else "dumpsys power did not expose mWakefulness.",
    }


def parse_memory(path: Path) -> dict:
    pss = [int(value) for value in re.findall(r"^Pss:\s+(\d+)\s+kB", path.read_text(errors="replace"), re.M)]
    text = path.read_text(errors="replace")
    hwm = [int(value) for value in re.findall(r"^VmHWM:\s+(\d+)\s+kB", text, re.M)]
    samples = text.count("\n--\n")
    return {
        "peak_sampled_pss_bytes": max(pss) * 1024 if pss else None,
        "peak_sampled_pss_missing_reason": None if pss else "No readable Pss sample was returned from /proc/<pid>/smaps_rollup.",
        "peak_vm_hwm_bytes": max(hwm) * 1024 if hwm else None,
        "peak_vm_hwm_missing_reason": None if hwm else "No readable VmHWM sample was returned from /proc/<pid>/status.",
        "sample_count": samples,
        "target_sampling_interval_seconds": 0.1,
        "lifecycle": "Remote llama-server process from immediately after PID publication through campaign completion.",
        "method": "Android shell reads of /proc/<pid>/smaps_rollup Pss and /proc/<pid>/status VmHWM.",
        "limitations": "Sampling begins just after server process launch and can miss startup allocations or peaks shorter than the sampling interval. VmHWM is process-lifetime cumulative RSS, not isolated model/KV memory.",
    }


def parse_gpu_samples(path: Path) -> dict:
    text = path.read_text(errors="replace")
    frequencies = [int(value) for value in re.findall(r"devfreq/cur_freq=(\d+)", text)]
    busy_percentages = [int(value) for value in re.findall(r"gpu_busy_percentage=(\d+)", text)]
    gpubusy = [
        (int(busy), int(total))
        for busy, total in re.findall(r"kgsl-3d0/gpubusy=(\d+)\s+(\d+)", text)
    ]
    return {
        "sample_count": text.count("\n--\n"),
        "target_sampling_interval_seconds": 0.1,
        "current_frequency_hz_min": min(frequencies) if frequencies else None,
        "current_frequency_hz_max": max(frequencies) if frequencies else None,
        "current_frequency_missing_reason": None if frequencies else "KGSL devfreq cur_freq was unavailable or unreadable to the Android shell.",
        "busy_percentage_max": max(busy_percentages) if busy_percentages else None,
        "busy_percentage_missing_reason": None if busy_percentages else "KGSL gpu_busy_percentage was unavailable or unreadable to the Android shell.",
        "gpubusy_counter_first": None if not gpubusy else {"busy": gpubusy[0][0], "total": gpubusy[0][1]},
        "gpubusy_counter_last": None if not gpubusy else {"busy": gpubusy[-1][0], "total": gpubusy[-1][1]},
        "gpubusy_counter_missing_reason": None if gpubusy else "KGSL gpubusy was unavailable or unreadable to the Android shell.",
        "method": "Android shell reads of public KGSL sysfs nodes; counters/frequency are operating evidence, not calibrated power.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--looks-sensible", choices=["true", "false", "null"], default="null")
    parser.add_argument("--issue-notes")
    args = parser.parse_args()
    sanity = {"true": True, "false": False, "null": None}[args.looks_sensible]
    if sanity is True and args.issue_notes is not None:
        raise ValueError("sensible output cannot carry issue notes")
    if sanity is False and not args.issue_notes:
        raise ValueError("broken output requires issue notes")
    if sanity is None and args.issue_notes is not None:
        raise ValueError("unchecked output cannot carry issue notes")

    cleanup = json.loads((args.input / "cleanup.json").read_text())
    if cleanup.get("cleanup_state") != "verified_absent":
        raise ValueError("phone cleanup is not verified absent")
    expected = (args.input / "expected-sha256.txt").read_text().strip()
    remote = (args.input / "remote-sha256.txt").read_text().strip()
    if expected != remote:
        raise ValueError("remote stage hashes do not match expected hashes")
    source_result = args.input / "client/result.json"
    result = json.loads(source_result.read_text())
    if result.get("status") != "complete":
        raise ValueError("client result is incomplete")
    proof = result.get("route", {}).get("backend_proof", {})
    required_proof = {
        "vulkan_device_count", "adreno_740_device", "all_layers_offloaded",
        "vulkan_model_buffer", "vulkan_compute_buffer",
    }
    if set(proof.get("required_matches", {})) != required_proof or proof.get("forbidden_matches") != {}:
        raise ValueError("complete Vulkan/Adreno offload proof is absent")
    if result["route"].get("observed_offloaded_layers") != 25:
        raise ValueError("all 25 model layers were not proven offloaded")

    args.output.mkdir(parents=True, exist_ok=False)
    for directory in ("outputs", "events", "rendered"):
        shutil.copytree(args.input / "client" / directory, args.output / directory)
    raw = args.output / "raw"
    raw.mkdir()
    raw_names = [
        "server.stdout.log", "server.stderr.log", "memory-samples.txt", "memory-sampler.stderr.log",
        "device.txt", "storage-before.txt", "battery-before.txt", "battery-after.txt",
        "thermal-before.txt", "thermal-after.txt", "power-before.txt", "power-after.txt",
        "expected-sha256.txt", "remote-sha256.txt", "local-hash-check.txt", "stage-hash-diff.txt",
        "push-server.txt", "push-model.txt", "adb-state.txt", "cleanup.json", "forward.txt", "client-base.txt",
        "gpu-before.txt", "gpu-after.txt", "gpu-samples.txt", "gpu-sampler.stderr.log",
    ]
    raw_hashes = {}
    for name in raw_names:
        source = args.input / name
        if source.exists():
            shutil.copyfile(source, raw / name)
            raw_hashes[name] = {"bytes": source.stat().st_size, "sha256": sha(source)}

    device = parse_key_values(args.input / "device.txt")
    result["experiment"] = "0030-qwen-3.5-2b-android-vulkan-gpu"
    result["arm_id"] = "qwen35-2b-unsloth-q4km-llamacpp-vulkan-adreno"
    result["source_client_result_sha256"] = sha(source_result)
    result["artifact"] = {
        "name": "Qwen3.5-2B-Q4_K_M.gguf",
        "source_kind": "third-party Unsloth GGUF conversion",
        "bytes": 1280835840,
        "sha256": "aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223",
    }
    result["runtime"] = {
        "name": "llama.cpp",
        "revision": "0a5ac49bce4c42893368585edf3ffb41a38f0108",
        "android_server_artifact_revision": 1,
        "android_server_bytes": 34242152,
        "android_server_sha256": "b806fc03df6510eb7a141aea093cec7a878a2aa7456ea076a84791fadec68c00",
        "embedded_web_ui": False,
        "provider_backend": "GGML Vulkan GPU offload",
        "provider_device": "Vulkan0 / Adreno (TM) 740",
        "requested_gpu_layers": 25,
        "observed_offloaded_layers": 25,
        "observed_total_offloadable_layers": 25,
        "cpu_boundary": "CPU remains responsible for server, tokenizer, sampler, scheduler/orchestration, and any operation unsupported by Vulkan; the route is not GPU-exclusive.",
        "threads": 4,
    }
    result["device"] = {
        "serial": device.get("serial"), "model": device.get("model"), "soc": device.get("soc"),
        "abi": device.get("abi"), "build_fingerprint": device.get("build_fingerprint"),
        "build_id": device.get("build_id"), "android_release": device.get("android_release"),
        "android_sdk": device.get("android_sdk"),
    }
    result["memory"] = parse_memory(args.input / "memory-samples.txt")
    result["gpu_telemetry"] = parse_gpu_samples(args.input / "gpu-samples.txt")
    result["operating_conditions"] = {
        "battery_before": parse_battery(args.input / "battery-before.txt"),
        "battery_after": parse_battery(args.input / "battery-after.txt"),
        "thermal_before": parse_thermal(args.input / "thermal-before.txt"),
        "thermal_after": parse_thermal(args.input / "thermal-after.txt"),
        "power_before": parse_power(args.input / "power-before.txt"),
        "power_after": parse_power(args.input / "power-after.txt"),
        "power_watts": None,
        "power_watts_missing_reason": "No calibrated external or OS energy measurement was available; battery charging state is context only.",
    }
    result["stage_and_cleanup"] = {
        "phone_lock": True,
        "local_remote_hashes_equal": True,
        "remote_root": cleanup["remote_root"],
        "cleanup_state": cleanup["cleanup_state"],
    }
    result["raw_files"] = raw_hashes
    for run in result["runs"]:
        output = args.output / run["output_path"]
        if sha(output) != run["output_sha256"]:
            raise ValueError(f"output hash mismatch: {run['id']}")
        run["output_sanity"] = {"looks_sensible": sanity, "issue_notes": args.issue_notes}
    (args.output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(args.output / "result.json")


if __name__ == "__main__":
    main()

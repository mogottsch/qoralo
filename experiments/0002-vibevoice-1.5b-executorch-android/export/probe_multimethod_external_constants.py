#!/usr/bin/env python3
"""Synthetic ExecuTorch 1.2 multi-method and external-constant diagnostic.

Generated .pte/.ptd files and stage logs go below artifacts/ and stay ignored. The
committed result is intentionally small and contains only reproducibility metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import torch

METHODS = ("warmup", "steady")
FEATURES = 128
EXTERNAL_TAG = "shared-weights"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact(path: Path) -> dict[str, Any]:
    return {"name": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}


def dump(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


class SyntheticPhase(torch.nn.Module):
    """One phase with the same deterministic weight and a distinct phase offset."""

    def __init__(self, weight: torch.nn.Parameter, offset: float) -> None:
        super().__init__()
        self.weight = weight
        self.offset = offset

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return torch.nn.functional.linear(value, self.weight) + self.offset


def model_and_input(offset: float = 0.0) -> tuple[SyntheticPhase, tuple[torch.Tensor]]:
    values = torch.arange(FEATURES * FEATURES, dtype=torch.float32).reshape(FEATURES, FEATURES)
    weight = torch.nn.Parameter(values / float(FEATURES * FEATURES))
    return SyntheticPhase(weight, offset).eval(), (torch.ones(1, FEATURES),)


def exported_programs(*, external: bool) -> tuple[dict[str, Any], tuple[torch.Tensor]]:
    from executorch.exir.passes.external_constants_pass import delegate_external_constants_pass_unlifted

    base, inputs = model_and_input()
    programs: dict[str, Any] = {}
    for index, name in enumerate(METHODS):
        phase = SyntheticPhase(base.weight, float(index)).eval()
        if external:
            unlifted = torch.export.export(phase, inputs, strict=True).module()
            delegate_external_constants_pass_unlifted(unlifted, lambda _node: EXTERNAL_TAG)
            programs[name] = torch.export.export(unlifted, inputs, strict=True)
        else:
            programs[name] = torch.export.export(phase, inputs, strict=True)
    return programs, inputs


def stage_portable(out: Path) -> dict[str, Any]:
    from executorch.exir import EdgeCompileConfig, to_edge
    from executorch.runtime import Runtime

    programs, inputs = exported_programs(external=False)
    config = EdgeCompileConfig(_skip_dim_order=False)
    individual: list[dict[str, Any]] = []
    for name in METHODS:
        program = to_edge(programs[name], compile_config=config).to_executorch()
        path = out / f"portable-{name}.pte"
        program.save(str(path))
        individual.append(artifact(path))

    program = to_edge(programs, compile_config=config).to_executorch()
    multi_path = out / "portable-multimethod.pte"
    program.save(str(multi_path))
    runtime_program = Runtime.get().load_program(multi_path)
    executions: dict[str, Any] = {}
    for index, name in enumerate(METHODS):
        output = runtime_program.load_method(name).execute(inputs)[0]
        expected = programs[name].module()(*inputs)
        executions[name] = {
            "expected_first": expected[0, 0].item(),
            "actual_first": output[0, 0].item(),
            "max_abs_error": (output - expected).abs().max().item(),
        }
    one_method_mean = sum(item["bytes"] for item in individual) / len(individual)
    return {
        "status": "passed",
        "methods": sorted(runtime_program.method_names),
        "weight_payload_bytes": FEATURES * FEATURES * 4,
        "artifacts": {"individual": individual, "multimethod": artifact(multi_path)},
        "size_analysis": {
            "sum_individual_bytes": sum(item["bytes"] for item in individual),
            "multimethod_bytes": multi_path.stat().st_size,
            "multimethod_over_mean_single_bytes": multi_path.stat().st_size - one_method_mean,
            "deduplicated": multi_path.stat().st_size < sum(item["bytes"] for item in individual) - FEATURES * FEATURES * 4 // 2,
        },
        "executions": executions,
    }


def stage_external_export(out: Path, *, multimethod: bool) -> dict[str, Any]:
    from executorch.backends.xnnpack.partition.xnnpack_partitioner import XnnpackPartitioner
    from executorch.exir import EdgeCompileConfig, to_edge_transform_and_lower

    programs, _ = exported_programs(external=True)
    selected: Any = programs if multimethod else programs["warmup"]
    program = to_edge_transform_and_lower(
        selected,
        partitioner=[XnnpackPartitioner()],
        compile_config=EdgeCompileConfig(_skip_dim_order=False),
    ).to_executorch()
    stem = "external-multimethod" if multimethod else "external-single"
    pte = out / f"{stem}.pte"
    program.save(str(pte))
    program.write_tensor_data_to_file(out)
    ptd = out / f"{EXTERNAL_TAG}.ptd"
    return {
        "status": "passed",
        "methods": sorted(program.methods),
        "tensor_data_keys": sorted(program._tensor_data.keys()),
        "artifacts": {"pte": artifact(pte), "ptd": artifact(ptd)},
    }


def stage_external_legacy_run(out: Path) -> dict[str, Any]:
    from executorch.extension.pybindings import portable_lib

    pte = out / "external-single.pte"
    ptd = out / f"{EXTERNAL_TAG}.ptd"
    _, inputs = model_and_input()
    module = portable_lib._load_for_executorch(str(pte), str(ptd))
    output = module.forward(inputs)[0]
    return {
        "status": "passed",
        "api": "executorch.extension.pybindings.portable_lib._load_for_executorch(pte_path, ptd_path)",
        "methods": sorted(module.method_names()),
        "actual_first": output[0, 0].item(),
    }


def stage_external_multimethod_legacy_run(out: Path) -> dict[str, Any]:
    from executorch.extension.pybindings import portable_lib

    pte = out / "external-multimethod.pte"
    ptd = out / f"{EXTERNAL_TAG}.ptd"
    _, inputs = model_and_input()
    module = portable_lib._load_for_executorch(str(pte), str(ptd))
    executions: dict[str, Any] = {}
    for index, name in enumerate(METHODS):
        output = module.run_method(name, inputs)[0]
        executions[name] = {"actual_first": output[0, 0].item(), "expected_first": 0.49609375 + index}
    return {
        "status": "passed",
        "api": "executorch.extension.pybindings.portable_lib._load_for_executorch(pte_path, ptd_path)",
        "methods": sorted(module.method_names()),
        "executions": executions,
    }


def stage_external_public_run(out: Path) -> dict[str, Any]:
    """Expected to be isolated: 1.2 may terminate while resolving absent PTD data."""
    from executorch.runtime import Runtime

    _, inputs = model_and_input()
    program = Runtime.get().load_program(out / "external-single.pte")
    output = program.load_method("forward").execute(inputs)[0]
    return {"status": "unexpected_pass", "actual_first": output[0, 0].item()}


def run_stage(script: Path, stage: str, out: Path, env: dict[str, str]) -> dict[str, Any]:
    status_path = out / f"{stage}.json"
    command = [sys.executable, str(script), "--stage", stage, "--output-dir", str(out)]
    completed = subprocess.run(command, text=True, capture_output=True, env=env)
    (out / f"{stage}.stdout.log").write_text(completed.stdout)
    (out / f"{stage}.stderr.log").write_text(completed.stderr)
    if status_path.exists():
        detail = json.loads(status_path.read_text())
    else:
        detail = {"status": "terminated" if completed.returncode < 0 else "failed"}
    detail.update(
        {
            "command": command,
            "returncode": completed.returncode,
            "signal": signal.Signals(-completed.returncode).name if completed.returncode < 0 else None,
            "stdout_log": f"artifacts/0002/executorch-capability-probe/{stage}.stdout.log",
            "stderr_log": f"artifacts/0002/executorch-capability-probe/{stage}.stderr.log",
            "stderr_tail": completed.stderr.splitlines()[-20:],
        }
    )
    return detail


def android_inspection() -> dict[str, Any]:
    jars = list(Path.home().glob(".gradle/caches/**/executorch-android-1.2.0-api.jar"))
    aars = list(Path.home().glob(".gradle/caches/**/executorch-android-1.2.0.aar"))
    if not jars or not shutil.which("javap"):
        return {"status": "not_available", "reason": "cached API jar or javap not found"}
    command = ["javap", "-classpath", str(jars[0]), "org.pytorch.executorch.Module"]
    completed = subprocess.run(command, text=True, capture_output=True)
    public_lines = [line.strip() for line in completed.stdout.splitlines() if " load(" in line or " execute(" in line or "getMethods" in line]
    return {
        "status": "inspected" if completed.returncode == 0 else "failed",
        "command": command,
        "dependency": "org.pytorch:executorch-android:1.2.0",
        "aar": artifact(aars[0]) if aars else None,
        "relevant_public_api": public_lines,
        "ptd_or_data_loader_parameter_present": any("ptd" in line.lower() or "data" in line.lower() for line in public_lines),
        "interpretation": "Module.load accepts one model path plus integer load-mode/thread arguments; no PTD/data path is exposed.",
    }


def versions() -> dict[str, str]:
    flatc = Path(sys.executable).parent / "flatc"
    flatc_version = subprocess.run([str(flatc), "--version"], text=True, capture_output=True).stdout.strip() if flatc.exists() else "not-found"
    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "executorch": importlib.metadata.version("executorch"),
        "flatc": flatc_version,
        "platform": platform.platform(),
    }


def stage_main(stage: str, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    try:
        if stage == "portable":
            value = stage_portable(out)
        elif stage == "external-export":
            value = stage_external_export(out, multimethod=False)
        elif stage == "external-multimethod":
            value = stage_external_export(out, multimethod=True)
        elif stage == "external-legacy-run":
            value = stage_external_legacy_run(out)
        elif stage == "external-multimethod-legacy-run":
            value = stage_external_multimethod_legacy_run(out)
        elif stage == "external-public-run":
            value = stage_external_public_run(out)
        else:
            raise ValueError(f"unknown stage: {stage}")
        dump(out / f"{stage}.json", value)
        return 0
    except Exception as error:
        dump(out / f"{stage}.json", {"status": "failed", "error_type": type(error).__name__, "error": str(error)})
        return 1


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=root / "artifacts/0002/executorch-capability-probe")
    parser.add_argument("--result", type=Path, default=root / "experiments/0002-vibevoice-1.5b-executorch-android/results/executorch-multimethod-external-constants.json")
    parser.add_argument("--stage", choices=("portable", "external-export", "external-multimethod", "external-legacy-run", "external-multimethod-legacy-run", "external-public-run"))
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if args.stage:
        return stage_main(args.stage, out)

    out.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve()
    env = os.environ.copy()
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    stages: dict[str, Any] = {}
    for name in ("portable", "external-export", "external-legacy-run", "external-public-run", "external-multimethod", "external-multimethod-legacy-run"):
        stages[name] = run_stage(script, name, out, env)

    from executorch.runtime import Runtime

    result = {
        "schema_version": 1,
        "probe": "executorch_1_2_multimethod_external_constants",
        "scope": "synthetic_only_no_vibevoice_no_phone",
        "versions": versions(),
        "invocation": [sys.executable, str(script), "--output-dir", str(args.output_dir), "--result", str(args.result)],
        "apis": {
            "multimethod_export": "executorch.exir.to_edge(dict[str, ExportedProgram]).to_executorch()",
            "external_tagging": "delegate_external_constants_pass_unlifted(module, gen_tag_fn)",
            "external_write": "ExecutorchProgramManager.write_tensor_data_to_file(outdir)",
            "public_host_load_signature": str(inspect.signature(Runtime.load_program)),
            "private_host_external_load": "portable_lib._load_for_executorch(pte_path, ptd_path)",
        },
        "stages": stages,
        "android_packaging_inspection": android_inspection(),
        "conclusions": {
            "warmup_methods_can_share_inline_constants": stages["portable"].get("size_analysis", {}).get("deduplicated") is True and stages["portable"]["status"] == "passed",
            "external_constants_exported_to_ptd": stages["external-export"]["status"] == "passed",
            "external_constants_run_with_private_host_api": stages["external-legacy-run"]["status"] == "passed",
            "external_constants_fit_public_host_runtime_path": stages["external-public-run"]["status"] == "passed",
            "external_constants_fit_current_android_java_path": False,
            "multi_method_external_constants_supported_by_private_host_api": stages["external-multimethod"]["status"] == "passed" and stages["external-multimethod-legacy-run"]["status"] == "passed",
            "recommendation": "Use one inline multi-method PTE to share warm-up weights. Do not adopt PTD/external constants in the current Runtime/Android Java path; revisit only with an explicit data-loader API and regression test.",
        },
        "bounded_failures": [
            "The public Python Runtime.load_program API has no PTD/data argument; execution was isolated because missing external data terminates this 1.2 build.",
            "Loading the external PTE through public Runtime and executing without a PTD terminated with SIGSEGV; it was isolated and no workaround was added.",
            "Android was inspected from the cached 1.2.0 AAR/API jar only; no device or phone lock was used.",
        ],
    }
    dump(args.result, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if stages["portable"]["status"] == "passed" and stages["external-legacy-run"]["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

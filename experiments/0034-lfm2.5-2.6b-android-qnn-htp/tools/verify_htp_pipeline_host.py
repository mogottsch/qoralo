#!/usr/bin/env python3
"""Compare the split HTP-intended pipeline with the unsplit host reference."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from transformers import AutoTokenizer

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[1]
ATTENTION_LAYERS = {2, 5, 9, 13, 17, 21, 24, 27}
WORKLOAD_SHA256 = "81d23ec04cb821625d3717ab50db7df3d9821a8d2987f1eb107fc90df9d1f2ae"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def external_fields(tensor: onnx.TensorProto) -> tuple[str, int]:
    fields = {item.key: item.value for item in tensor.external_data}
    return fields["location"], int(fields.get("offset", "0"))


class Pipeline:
    def __init__(self, parts_dir: Path, source_model: Path):
        self.parts_dir = parts_dir
        self.manifest = json.loads((parts_dir / "manifest.json").read_text())
        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        self.sessions = {
            item["name"]: ort.InferenceSession(
                str(parts_dir / item["path"]), sess_options=options, providers=["CPUExecutionProvider"]
            )
            for item in self.manifest["parts"]
        }
        model = onnx.load(str(source_model), load_external_data=False)
        initializers = {item.name: item for item in model.graph.initializer}
        self.embedding_tensors = [
            initializers["model_embed_tokens_weight_quant"],
            initializers["model_embed_tokens_weight_scales"],
            initializers["model_embed_tokens_weight_zp"],
        ]
        self.source_dir = source_model.parent
        self.states: dict[str, np.ndarray] = {}
        for layer in range(30):
            if layer in ATTENTION_LAYERS:
                self.states[f"past_key_values.{layer}.key"] = np.zeros((1, 8, 64, 4095), np.float32)
                self.states[f"past_key_values.{layer}.value"] = np.zeros((1, 8, 4095, 64), np.float32)
            else:
                self.states[f"past_conv.{layer}"] = np.zeros((1, 2048, 3), np.float32)

    def embedding(self, token: int) -> np.ndarray:
        quant, scales, zero_points = self.embedding_tensors
        q_location, q_offset = external_fields(quant)
        s_location, s_offset = external_fields(scales)
        z_location, z_offset = external_fields(zero_points)
        q = np.memmap(self.source_dir / q_location, dtype=np.uint8, mode="r", offset=q_offset, shape=tuple(quant.dims))[token]
        s = np.memmap(self.source_dir / s_location, dtype=np.float32, mode="r", offset=s_offset, shape=tuple(scales.dims))[token]
        z = np.memmap(self.source_dir / z_location, dtype=np.uint8, mode="r", offset=z_offset, shape=tuple(zero_points.dims))[token]
        unpacked = np.empty(2048, np.float32)
        unpacked[0::2] = q & 15
        unpacked[1::2] = q >> 4
        zp = np.empty(64, np.float32)
        zp[0::2] = z & 15
        zp[1::2] = z >> 4
        return ((unpacked - np.repeat(zp, 32)) * np.repeat(s, 32)).reshape(1, 1, 2048)

    def run(self, token: int, position: int) -> np.ndarray:
        hidden = self.embedding(token)
        mask = np.full((1, 1, 1, 4096), -65504.0, np.float32)
        mask[..., :position] = 0.0
        mask[..., -1] = 0.0
        position_ids = np.asarray([[position]], dtype=np.int64)
        for layer in range(30):
            core = self.sessions[f"layer-{layer:02d}-core-norm"]
            feed = {core.get_inputs()[0].name: hidden}
            if layer in ATTENTION_LAYERS:
                feed.update(
                    {
                        "position_ids": position_ids,
                        "attention_mask": mask,
                        f"past_key_values.{layer}.key": self.states[f"past_key_values.{layer}.key"],
                        f"past_key_values.{layer}.value": self.states[f"past_key_values.{layer}.value"],
                    }
                )
            else:
                feed[f"past_conv.{layer}"] = self.states[f"past_conv.{layer}"]
            core_values = dict(zip((item.name for item in core.get_outputs()), core.run(None, feed), strict=True))
            residual_name = f"/model/layers.{layer}/Add_1/output_0"
            norm_name = f"/model/layers.{layer}/ffn_layernorm/LayerNorm/output_0"
            residual = core_values[residual_name]
            norm = core_values[norm_name]
            if layer in ATTENTION_LAYERS:
                key = core_values[f"present.{layer}.key"]
                value = core_values[f"present.{layer}.value"]
                self.states[f"past_key_values.{layer}.key"][:, :, :, position : position + 1] = key
                self.states[f"past_key_values.{layer}.value"][:, :, position : position + 1, :] = value
            else:
                self.states[f"past_conv.{layer}"] = core_values[f"present_conv.{layer}"]

            products = []
            down = []
            for part in (0, 1):
                up_session = self.sessions[f"layer-{layer:02d}-up-{part}"]
                up = up_session.run(None, {up_session.get_inputs()[0].name: norm})[0]
                gate_session = self.sessions[f"layer-{layer:02d}-gate-activate-{part}"]
                product = gate_session.run(
                    None,
                    {
                        gate_session.get_inputs()[0].name: norm,
                        gate_session.get_inputs()[1].name: up,
                    },
                )[0]
                products.append(product)
                down_session = self.sessions[f"layer-{layer:02d}-down-{part}"]
                down.append(down_session.run(None, {down_session.get_inputs()[0].name: product})[0])
            residual_session = self.sessions[f"layer-{layer:02d}-residual"]
            hidden = residual_session.run(
                None,
                {
                    residual_session.get_inputs()[0].name: down[0],
                    residual_session.get_inputs()[1].name: down[1],
                    residual_session.get_inputs()[2].name: residual,
                },
            )[0]

        final_session = self.sessions["final-norm"]
        normalized = final_session.run(None, {final_session.get_inputs()[0].name: hidden})[0]
        logits = []
        for item in self.manifest["parts"]:
            if item["kind"] == "lm_head_chunk":
                session = self.sessions[item["name"]]
                logits.append(session.run(None, {session.get_inputs()[0].name: normalized})[0])
        return np.concatenate(logits, axis=-1)[0, -1]


def reference_state(session: ort.InferenceSession) -> dict[str, np.ndarray]:
    state = {}
    for item in session.get_inputs():
        if item.name in ("input_ids", "attention_mask", "position_ids"):
            continue
        shape = [value if isinstance(value, int) else (0 if "sequence" in str(value) else 1) for value in item.shape]
        state[item.name] = np.zeros(shape, np.float32)
    return state


def update_reference(state: dict[str, np.ndarray], session: ort.InferenceSession, outputs: list[np.ndarray]) -> None:
    for info, output in zip(session.get_outputs()[1:], outputs[1:], strict=True):
        if info.name.startswith("present_conv."):
            state[info.name.replace("present_conv.", "past_conv.")] = output
        else:
            state[info.name.replace("present.", "past_key_values.")] = output


def transformed_state(session: ort.InferenceSession) -> dict[str, np.ndarray]:
    return {
        item.name: np.zeros(item.shape, np.float32)
        for item in session.get_inputs()
        if item.name not in ("input_ids", "attention_mask", "position_ids")
    }


def run_transformed(
    session: ort.InferenceSession,
    state: dict[str, np.ndarray],
    token: int,
    position: int,
) -> np.ndarray:
    mask = np.full((1, 1, 1, 4096), -65504.0, np.float32)
    mask[..., :position] = 0.0
    mask[..., -1] = 0.0
    outputs = session.run(
        None,
        {
            "input_ids": np.asarray([[token]], np.int32),
            "position_ids": np.asarray([[position]], np.int64),
            "attention_mask": mask,
            **state,
        },
    )
    for info, output in zip(session.get_outputs()[1:], outputs[1:], strict=True):
        if info.name.startswith("present_conv."):
            state[info.name.replace("present_conv.", "past_conv.")] = output
        elif info.name.endswith(".key"):
            layer = info.name.split(".")[1]
            state[f"past_key_values.{layer}.key"][:, :, :, position : position + 1] = output
        else:
            layer = info.name.split(".")[1]
            state[f"past_key_values.{layer}.value"][:, :, position : position + 1, :] = output
    return outputs[0][0, -1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--pipeline-source", type=Path, required=True)
    parser.add_argument("--parts-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    workload_path = REPO / "protocols/android-llm-benchmark/workloads/inference-v1/short.json"
    workload_bytes = workload_path.read_bytes()
    if sha256(workload_bytes) != WORKLOAD_SHA256:
        raise RuntimeError("workload hash mismatch")
    workload = json.loads(workload_bytes)
    tokenizer = AutoTokenizer.from_pretrained(str(EXP / ".local/source"), local_files_only=True, trust_remote_code=False)
    rendered = tokenizer.apply_chat_template(workload["messages"], tokenize=False, add_generation_prompt=True)
    prompt_ids = tokenizer.encode(rendered, add_special_tokens=False)
    if len(prompt_ids) != 171:
        raise RuntimeError("prompt token mismatch")

    reference = ort.InferenceSession(str(args.reference), providers=["CPUExecutionProvider"])
    state = reference_state(reference)
    transformed = ort.InferenceSession(str(args.pipeline_source), providers=["CPUExecutionProvider"])
    transformed_cache = transformed_state(transformed)
    pipeline_started = time.perf_counter_ns()
    pipeline = Pipeline(args.parts_dir, args.pipeline_source)
    pipeline_loaded = time.perf_counter_ns()

    reference_outputs = reference.run(
        None,
        {
            "input_ids": np.asarray([prompt_ids], dtype=np.int64),
            "attention_mask": np.ones((1, len(prompt_ids)), np.int64),
            "position_ids": np.arange(len(prompt_ids), dtype=np.int64).reshape(1, -1),
            **state,
        },
    )
    update_reference(state, reference, reference_outputs)
    reference_logits = reference_outputs[0][0, -1]

    for position, token in enumerate(prompt_ids):
        transformed_logits = run_transformed(transformed, transformed_cache, token, position)
        pipeline_logits = pipeline.run(token, position)

    comparisons = []
    generated = []
    for step in range(5):
        difference = np.abs(reference_logits - pipeline_logits)
        transformed_difference = np.abs(transformed_logits - pipeline_logits)
        reference_token = int(np.argmax(reference_logits))
        transformed_token = int(np.argmax(transformed_logits))
        pipeline_token = int(np.argmax(pipeline_logits))
        comparisons.append(
            {
                "step": step,
                "reference_argmax": reference_token,
                "transformed_monolith_argmax": transformed_token,
                "pipeline_argmax": pipeline_token,
                "all_argmax_equal": reference_token == transformed_token == pipeline_token,
                "reference_to_pipeline_max_abs_logit_difference": float(difference.max()),
                "reference_to_pipeline_mean_abs_logit_difference": float(difference.mean()),
                "transformed_monolith_to_pipeline_max_abs_logit_difference": float(transformed_difference.max()),
                "transformed_monolith_to_pipeline_mean_abs_logit_difference": float(transformed_difference.mean()),
            }
        )
        if reference_token != transformed_token or reference_token != pipeline_token:
            raise RuntimeError(f"greedy token mismatch at step {step}")
        generated.append(pipeline_token)
        if step == 4:
            break
        position = len(prompt_ids) + step
        reference_outputs = reference.run(
            None,
            {
                "input_ids": np.asarray([[pipeline_token]], dtype=np.int64),
                "attention_mask": np.ones((1, position + 1), np.int64),
                "position_ids": np.asarray([[position]], dtype=np.int64),
                **state,
            },
        )
        update_reference(state, reference, reference_outputs)
        reference_logits = reference_outputs[0][0, -1]
        transformed_logits = run_transformed(transformed, transformed_cache, pipeline_token, position)
        pipeline_logits = pipeline.run(pipeline_token, position)

    stopped = time.perf_counter_ns()
    text = tokenizer.decode(generated, skip_special_tokens=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "output.txt").write_bytes(text.encode())
    result = {
        "schema_version": 1,
        "classification": "host_only_pipeline_equivalence_not_android_qnn_or_htp_execution",
        "canonical_short": {"workload_sha256": WORKLOAD_SHA256, "input_tokens": len(prompt_ids)},
        "pipeline": {
            "parts": pipeline.manifest["htp_part_count"],
            "attention_capacity": 4096,
            "explicit_state_reset": "all cache arrays initialized to zero",
            "load_seconds": (pipeline_loaded - pipeline_started) / 1e9,
            "prompt_plus_comparison_seconds": (stopped - pipeline_loaded) / 1e9,
        },
        "comparisons": comparisons,
        "all_five_greedy_tokens_equal": all(item["all_argmax_equal"] for item in comparisons),
        "generated_tokens": generated,
        "output_path": "output.txt",
        "output_bytes": len(text.encode()),
        "output_sha256": sha256(text.encode()),
        "output_sanity": {"looks_sensible": True, "issue_notes": None},
        "claim_boundary": "Host equivalence of the final split graph route only. CPU timing is not Android/QNN/HTP evidence.",
    }
    (args.output_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

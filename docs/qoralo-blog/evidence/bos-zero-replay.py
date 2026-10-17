#!/usr/bin/env python3
"""Host-only replay: what start-of-sequence (BOS) input reproduces the old Android failure?

Run from the repository root with the retained local Python environment:

  experiments/0024-pocket-tts-qnn-precompiled-context-startup/.local/export-venv/bin/python \
    docs/qoralo-blog/evidence/bos-zero-replay.py

It ports the old runner's loop (experiments/0014-.../tools/pocket_alba_cpu_runner.cc) to
ONNX Runtime Python on host CPU and varies only the first AR input. It does not use the
phone, generate audio, or make a listening claim.

Graph caveat: the exact original flow_lm_main.onnx (sha256 021288bd...) is not retained.
This uses the 0024 same-size reconstruction (different hash). It is checked below against
the retained host run (first logit -9.8847, EOS step 53) and against the retained Android
fixed-cache run (57 logits).
"""
import hashlib, json
from pathlib import Path
import numpy as np
import onnx
import onnxruntime as ort

L = Path("experiments/0024-pocket-tts-qnn-precompiled-context-startup/.local")
R14 = Path("experiments/0014-pocket-fp-onnx-qnn-htp/results")
OUT = Path("docs/qoralo-blog/evidence/bos-zero-replay.json")
IDS = [1456,603,597,602,854,640,791,261,260,1332,323,288,285,287,489,594,1355,1049,265,311,2081,3697,273,519,1836,263]
H, D, SRC, DST = 16, 64, 126, 1000
GRAPH = L / "onnx-controlled/flow_lm_main.onnx"

opts = ort.SessionOptions(); opts.intra_op_num_threads = 1; opts.inter_op_num_threads = 1
def sess(n): return ort.InferenceSession(str(L / f"onnx-controlled/{n}.onnx"), opts, providers=["CPUExecutionProvider"])
text, main, flow = sess("text_conditioner"), sess("flow_lm_main"), sess("flow_lm_flow")
IN = [i.name for i in main.get_inputs()]; OUTN = [o.name for o in main.get_outputs()]
packed = np.fromfile(L / "assets/alba-flow-cache-v1.f32", dtype="<f4")
noise = np.fromfile(L / "assets/numpy-randomstate-seed0-temp0p3-292x32.f32", dtype="<f4")[:134 * 32].reshape(134, 32)
assert hashlib.sha256(packed.tobytes()).hexdigest() == "eb6e2d714fe75cb9a726c7742f32e7c6b500cc6de4dae8b533f2bfa7b41bc6d2"
assert hashlib.sha256(noise.tobytes()).hexdigest() == "c130a822ce776253ccbab68a642697698862bfe4d000d6bdd03f0836d62d8c94"
PER = 2 * SRC * H * D
emb = text.run(None, {"token_ids": np.array([IDS], np.int64)})[0]

def init_state():
    st = []
    for layer in range(6):
        c = np.full((2, 1, DST, H, D), np.nan, np.float32)   # same NaN-filled 1000-slot cache as the runner
        c[:, 0, :SRC] = packed[layer * PER:(layer + 1) * PER].reshape(2, SRC, H, D)
        st += [c, np.zeros((0,), np.float32), np.array([SRC], np.int64)]
    return st

def run_main(seq, txt, state):
    r = main.run(OUTN, dict(zip(IN, [seq, txt] + state)))
    return r[0], float(r[1].reshape(-1)[0]), r[2:]

empty_seq = np.zeros((1, 0, 32), np.float32); empty_text = np.zeros((1, 0, 1024), np.float32)
_, _, STATE0 = run_main(empty_seq, emb, init_state())           # text prefill, done once

def step0(bos):
    return run_main(bos.reshape(1, 1, 32).astype(np.float32), empty_text, [x.copy() for x in STATE0])[1]

def replay(bos, max_frames=134):
    state = [x.copy() for x in STATE0]; cur = np.zeros(32, np.float32); logits = []; eos = -1
    for step in range(max_frames):
        seq = bos.reshape(1, 1, 32).astype(np.float32) if step == 0 else cur.reshape(1, 1, 32)
        cond, logit, state = run_main(seq, empty_text, state); logits.append(logit)
        if eos < 0 and logit > -4: eos = step
        if eos >= 0 and step >= eos + 3: break
        n = noise[step]
        d = flow.run(None, {"c": cond, "s": np.zeros((1, 1), np.float32), "t": np.ones((1, 1), np.float32), "x": n.reshape(1, 32)})[0].reshape(-1)
        cur = (n + d).astype(np.float32)
    return logits, eos

def replay_states(bos, frames):
    """Like replay(), but also returns the hidden state c (what the frame and stop heads both read) and each frame."""
    state = [x.copy() for x in STATE0]; cur = np.zeros(32, np.float32); cs, lat = [], []
    for step in range(frames):
        seq = bos.reshape(1, 1, 32).astype(np.float32) if step == 0 else cur.reshape(1, 1, 32)
        cond, logit, state = run_main(seq, empty_text, state); cs.append(cond.reshape(-1).copy())
        n = noise[step]
        d = flow.run(None, {"c": cond, "s": np.zeros((1, 1), np.float32), "t": np.ones((1, 1), np.float32), "x": n.reshape(1, 32)})[0].reshape(-1)
        cur = (n + d).astype(np.float32); lat.append(cur.copy())
    return np.array(cs), np.array(lat)

def diff(a, b):
    m = min(len(a), len(b)); d = np.abs(np.array(a[:m]) - np.array(b[:m]))
    return {"steps_compared": m, "max_abs": round(float(d.max()), 4), "mean_abs": round(float(d.mean()), 5), "step0_abs": round(float(d[0]), 5)}

android_orig = json.load(open(R14 / "android-alba-original-cpu.json"))["result"]["eos_logits"]
android_fixed = json.load(open(R14 / "alba-quality-recovery.json"))["android_fixed_cache_cpu"]["result"]["eos_logits"]

g = onnx.load(str(GRAPH), load_external_data=False)
nodes = {n.name: n for n in g.graph.node}
isnan, where = nodes["/IsNaN"], nodes["/Where"]
assert list(isnan.input) == ["sequence"] and list(where.input) == ["/IsNaN_output_0", "flow_lm.bos_emb", "sequence"]
bos_emb = next(onnx.numpy_helper.to_array(i) for i in g.graph.initializer if i.name == "flow_lm.bos_emb")

nan = np.full(32, np.nan, np.float32); zero = np.zeros(32, np.float32)
correct, eos_c = replay(nan); zeros, eos_z = replay(zero)
assert abs(correct[0] - (-9.8847)) < 1e-4 and eos_c == 53          # retained host run
scan = {}
for k in range(0, 33):
    b = nan.copy(); b[:k] = 0; scan[f"first_{k}_zero_rest_nan"] = round(step0(b), 4)
for k in range(1, 33):
    b = nan.copy(); b[32 - k:] = 0; scan[f"last_{k}_zero_rest_nan"] = round(step0(b), 4)
target = round(android_orig[0], 4)
matches = sorted(k for k, v in scan.items() if abs(v - target) < 5e-4)

FR = 56   # frames the correct run produces before it stops
cn, ln = replay_states(nan, FR); cz, lz = replay_states(zero, FR)
rel = lambda x, y: np.linalg.norm(x - y, axis=1) / np.linalg.norm(x, axis=1)   # ||zero - correct|| / ||correct||
rc, rl = rel(cn, cz), rel(ln, lz)
frame_drift = {
  "definition": "||zero-input - correct-input|| / ||correct-input||, per frame, same text, voice cache and noise; frames 0..55 of the correct run",
  "hidden_state_c": {"frame0": round(float(rc[0]), 3), "median": round(float(np.median(rc)), 3), "per_frame": [round(float(x), 3) for x in rc]},
  "latent_frame": {"frame0": round(float(rl[0]), 3), "median": round(float(np.median(rl)), 3), "per_frame": [round(float(x), 3) for x in rl]},
  "note": "The stop score and the next frame are both read from c (flow_lm_main outputs conditioning and eos_logit; see tools/export_flow_qnn_static.py: c=out_norm(x)[:,-1]; return (c, out_eos(c))). Each frame is the next step's input (runner loop).",
}
result = {
  "schema_version": 1,
  "purpose": "Which first-step BOS input reproduces the retained original-dynamic Android CPU failure?",
  "host_only": True,
  "graph": {"path": str(GRAPH), "sha256": hashlib.sha256(GRAPH.read_bytes()).hexdigest(),
            "original_0012_sha256": "021288bdcfb2e70cad3c2c3f96701b644d84aa98627898f255ec7bed69d9a95e",
            "caveat": "same byte size, different hash; reproduces the retained host first logit and EOS step"},
  "ort_version": ort.__version__,
  "graph_bos_rule": "Where(IsNaN(sequence), flow_lm.bos_emb, sequence): a NaN input element is replaced by the learned BOS embedding",
  "bos_emb_l2_norm": round(float(np.linalg.norm(bos_emb)), 4),
  "validation": {
    "correct_nan_bos": {"first_logit": round(correct[0], 4), "eos_step": eos_c, "retained_host": {"first_logit": -9.8847, "eos_step": 53}},
    "correct_nan_bos_vs_android_fixed_cache_cpu_57_logits": diff(correct, android_fixed)},
  "step0_logit": {"correct_nan": round(correct[0], 4), "all_zeros": round(step0(zero), 4), "android_original_retained": target},
  "inputs": {
    "token_ids": IDS, "token_ids_sha256": hashlib.sha256(np.array(IDS, "<i8").tobytes()).hexdigest(),
    "text_embedding_sha256": hashlib.sha256(emb.astype("<f4").tobytes()).hexdigest(),
    "alba_cache_pack_sha256": hashlib.sha256(packed.tobytes()).hexdigest(),
    "noise_134x32_sha256": hashlib.sha256(noise.tobytes()).hexdigest(),
    "text_conditioner_sha256": hashlib.sha256((L / "onnx-controlled/text_conditioner.onnx").read_bytes()).hexdigest(),
    "flow_lm_flow_sha256": hashlib.sha256((L / "onnx-controlled/flow_lm_flow.onnx").read_bytes()).hexdigest(),
    "provider": "CPUExecutionProvider, 1 intra-op / 1 inter-op thread"},
  "partial_zero_scan_step0": {
    "patterns_tested": len(scan), "unique_patterns": 64,
    "note": "first_32 and last_32 are the same all-zero input and first_0 is the correct all-NaN input; 62 are genuinely partial prefix/suffix zeroings. Not exhaustive over all possible 32-float inputs.",
    "partial_patterns_matching_android_within_5e-4": [m for m in matches if m not in ("first_32_zero_rest_nan", "last_32_zero_rest_nan")],
    "all_zero_matches": [m for m in matches if m in ("first_32_zero_rest_nan", "last_32_zero_rest_nan")]},
  "full_trajectory": {
    "all_zero_bos_vs_android_original": diff(zeros, android_orig),
    "correct_nan_bos_vs_android_original": diff(correct, android_orig),
    "all_zero_replay_eos_step": eos_z, "android_original_eos_step": -1, "frame_cap": 134,
    "max_logit": {"all_zero_replay": round(max(zeros), 3), "android_original": round(max(android_orig), 3), "eos_threshold": -4}},
  "frame_drift": frame_drift,
  "logits": {"correct_nan_bos_replay": [round(x, 3) for x in correct], "all_zero_bos_replay": [round(x, 3) for x in zeros],
             "android_original_retained": [round(x, 3) for x in android_orig]},
}
OUT.write_text(json.dumps(result, indent=1) + "\n")
print(json.dumps({k: v for k, v in result.items() if k != "logits"}, indent=1))

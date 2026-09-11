#!/usr/bin/env python3
"""Case-specific static HTP derivatives with explicit native EDGE semantics.

Not an app-ready generic pack. Original FP32 weights and position table remain
unchanged. Vector uses the stable Softplus identity and replaces 28 symmetric
EDGE Pads with Gather at runtime native-boundary indices. The four coordinate
arrays depend only on this route's own nativeL, never CPU durations/features.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import time

REPO = Path(__file__).resolve().parents[4]
ROOT = Path(__file__).resolve().parents[1]
OLD = REPO / 'experiments/0023-supertonic-qnn-precompiled-context-startup/improvements/0001-whole-chapter-capacity'
spec = importlib.util.spec_from_file_location('retained_capacity', OLD / 'tools/onnx_capacity.py')
capacity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capacity)
PINS = json.loads((OLD / 'protocol/target.json').read_text())['sources']
RADII = (2, 4, 8, 16)


def sha(path):
    return capacity.sha(path)


def constant_pad_values(model, node):
    """Evaluate only a bounded shape-constant ancestor graph, no neural operators."""
    import onnx
    from onnx import helper
    from onnx.reference import ReferenceEvaluator
    producers = {o: n for n in model.graph.node for o in n.output}
    needed = set()
    def visit(value):
        if value in needed:
            return
        needed.add(value)
        parent = producers.get(value)
        if parent:
            for i in parent.input:
                visit(i)
    visit(node.input[1])
    nodes = [n for n in model.graph.node if any(o in needed for o in n.output)]
    initializers = [v for v in model.graph.initializer if v.name in needed]
    allowed = {'Constant', 'ConstantOfShape', 'Concat', 'Reshape', 'Slice', 'Transpose', 'Cast'}
    if len(nodes) > 32 or any(n.op_type not in allowed for n in nodes) or any(
            v.data_type != onnx.TensorProto.INT64 or list(v.dims) != [6] for v in initializers):
        raise ValueError('unrecognized Pad shape-constant recipe')
    graph = helper.make_graph(nodes, 'pad_constant_recipe', [],
        [helper.make_tensor_value_info(node.input[1], onnx.TensorProto.INT64, [6])], initializers)
    return ReferenceEvaluator(helper.make_model(graph, opset_imports=list(model.opset_import))).run(None, {})[0].tolist()


def edge_indices(native_length, bucket_length):
    import numpy as np
    if not 1 <= native_length <= bucket_length <= 1000:
        raise ValueError('native/bucket length invalid')
    return {f'native_edge_indices_r{r}': np.clip(np.arange(-r, bucket_length+r, dtype=np.int32),
                                               0, native_length-1) for r in RADII}


def lower_native_edges(model, bucket_length):
    import onnx
    from onnx import helper
    result = onnx.ModelProto()
    result.CopyFrom(model)
    occupied = {x for n in model.graph.node for x in [*n.input, *n.output]}
    names = [f'native_edge_indices_r{r}' for r in RADII]
    if occupied.intersection(names):
        raise ValueError('native-edge ABI name collision')
    rows = []
    for i, node in enumerate(model.graph.node):
        if node.op_type != 'Pad':
            continue
        values = constant_pad_values(model, node)
        attrs = {a.name: helper.get_attribute_value(a) for a in node.attribute}
        if len(node.input) != 2 or len(node.output) != 1 or attrs != {'mode': b'edge'} or \
                '/convnext.' not in node.name or not node.name.endswith('/dwconv/Pad'):
            raise ValueError('unexpected vector Pad contract')
        radius = values[2]
        if values != [0, 0, radius, 0, 0, radius] or radius not in RADII:
            raise ValueError('unexpected vector symmetric EDGE radius')
        replacement = helper.make_node('Gather', [node.input[0], f'native_edge_indices_r{radius}'],
            list(node.output), axis=2, name=node.name + '/native_boundary_Gather')
        result.graph.node[i].CopyFrom(replacement)
        rows.append(dict(source_name=node.name, radius=radius,
                         source_sha256=hashlib.sha256(node.SerializeToString()).hexdigest(),
                         replacement_sha256=hashlib.sha256(replacement.SerializeToString()).hexdigest()))
    if len(rows) != 28 or set(r['radius'] for r in rows) != set(RADII):
        raise ValueError('expected exactly28 vector EDGE sites across four radii')
    for radius, name in zip(RADII, names):
        result.graph.input.append(helper.make_tensor_value_info(name, onnx.TensorProto.INT32, [bucket_length+2*radius]))
    return result, rows


def derive(source, component, text_length, latent_length):
    import onnx
    if max(text_length, latent_length) > 1000:
        raise ValueError('original position cap must not be extended')
    result = capacity.specialize(source, component, text_length, latent_length)
    edges = []
    if component == 'vector':
        result = capacity.stable_softplus(result)
        result, edges = lower_native_edges(result, latent_length)
    result = onnx.shape_inference.infer_shapes(result, strict_mode=True, data_prop=False)
    onnx.checker.check_model(result, full_check=True)
    # Exhaustive byte-level check of all original learned/nonlearned initializers.
    original = list(source.graph.initializer)
    new = list(result.graph.initializer)
    if len(new) != len(original) + int(component == 'vector'):
        raise ValueError('unexpected initializer count')
    if any(a.SerializeToString() != b.SerializeToString() for a, b in zip(original, new)):
        raise ValueError('original initializer changed')
    expected = list(source.graph.node)
    if component == 'vector':
        index = next(i for i, n in enumerate(expected) if n.name == capacity.SOFTPLUS)
        expected[index:index+1] = capacity.replacement_nodes()
        by_name = {n.name: n for n in result.graph.node}
        for i, n in enumerate(expected):
            if n.op_type == 'Pad':
                expected[i] = by_name[n.name + '/native_boundary_Gather']
    if [n.SerializeToString() for n in expected] != [n.SerializeToString() for n in result.graph.node]:
        raise ValueError('unapproved computational-node delta')
    inputs = {v.name: capacity.value_info(v)['shape'] for v in result.graph.input}
    outputs = {v.name: capacity.value_info(v)['shape'] for v in result.graph.output}
    return result, dict(status='source_derivative_only_not_QNN_proof', component=component,
        inputs=inputs, outputs=outputs, source_nodes=len(source.graph.node), derived_nodes=len(result.graph.node),
        all_original_initializer_bytes_unchanged=True, source_initializer_count=len(original),
        original_position_extent=1000 if component == 'vector' else None,
        stable_softplus_identity=component == 'vector', native_boundary_gathers=edges,
        native_edge_coordinate_recipe='clip(arange(-radius,bucketL+radius),0,own_nativeL-1),INT32' if edges else None,
        model_execution=False, generic_app_ready_pack=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--component', choices=tuple(PINS), required=True)
    p.add_argument('--text-length', type=int, required=True)
    p.add_argument('--latent-length', type=int, default=1)
    p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args()
    if '.local' not in args.output_dir.resolve().parts:
        p.error('private graph output only')
    freeze = json.loads((ROOT.parent / 'protocol/freeze.json').read_text())
    protocol = json.loads((ROOT.parent / 'protocol/inputs.json').read_text())
    ts = {c['text_extent'] for c in protocol['chunks']}
    if freeze['status'] != 'frozen':
        raise ValueError('inputs not frozen')
    if args.component in ('duration', 'text') and args.text_length not in ts:
        raise ValueError('DP/text must use exact frozen nativeT, not a padding bucket')
    if args.component == 'vector' and args.text_length < max(ts):
        raise ValueError('bucket does not preserve complete frozen segment')
    binding = freeze['cpu_original_model_bindings'][args.component]
    source_path = Path(binding['source'])
    pin = PINS[args.component]
    if sha(source_path) != pin['sha256'] or source_path.stat().st_size != pin['bytes'] or binding['sha256'] != pin['sha256']:
        raise ValueError('official FP32 source pin differs')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    result = dict(component=args.component, source=pin, status='started')
    try:
        import onnx
        source = onnx.load(source_path, load_external_data=False)
        model, delta = derive(source, args.component, args.text_length, args.latent_length)
        output = args.output_dir / (args.component + '.onnx')
        with output.open('xb') as f:
            f.write(model.SerializeToString())
        (args.output_dir / 'structural-delta.json').write_text(json.dumps(delta, indent=2) + '\n')
        result.update(status=delta['status'], inputs=delta['inputs'], outputs=delta['outputs'],
                      derivative=dict(path=str(output.resolve()), bytes=output.stat().st_size, sha256=sha(output)))
    except BaseException as e:
        result.update(status='error', error=str(e))
        raise
    finally:
        result.update(elapsed_seconds=time.monotonic()-started,
                      process_ru_maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        (args.output_dir / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

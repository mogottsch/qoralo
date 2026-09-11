#!/usr/bin/env python3
"""Source-only new-shape FP32 derivatives. Never imports a neural runtime.

Experiment0036 has an explicit full-route task; old0023 per-attempt releases are
historical and are neither reused nor modified. Only arithmetic positional extent,
public shapes and the retained stable Softplus identity may change here.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import time

REPO = Path(__file__).resolve().parents[4]
OLD = REPO / 'experiments/0023-supertonic-qnn-precompiled-context-startup/improvements/0001-whole-chapter-capacity'
spec = importlib.util.spec_from_file_location('retained_capacity', OLD / 'tools/onnx_capacity.py')
capacity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capacity)
PINS = json.loads((OLD / 'protocol/target.json').read_text())['sources']


def sha(path):
    return capacity.sha(path)


def extend_positions(model, extent):
    import onnx
    from onnx import helper, numpy_helper
    if type(extent) is not int or not 1000 <= extent <= 16384:
        raise ValueError('invalid arithmetic positional extent')
    capacity.reject_external(model)
    capacity.require_position_capacity(model, 1000, 1000)
    result = copy.deepcopy(model)
    target = next(v for v in result.graph.initializer if v.name == capacity.INCREMENTS)
    target.CopyFrom(helper.make_tensor(target.name, onnx.TensorProto.INT64,
                                       [1, extent, 1], list(range(extent))))
    before = next(v for v in model.graph.initializer if v.name == capacity.INCREMENTS)
    assert numpy_helper.to_array(target).reshape(-1)[:1000].tolist() == numpy_helper.to_array(before).reshape(-1).tolist()
    for old, new in zip(model.graph.initializer, result.graph.initializer):
        if old.name != capacity.INCREMENTS and old.SerializeToString() != new.SerializeToString():
            raise ValueError('non-position initializer changed')
    return result


def derive(source, component, text_length, latent_length):
    import onnx
    expected_in, expected_out = capacity.io_shapes(component, text_length, latent_length)
    capacity.reject_external(source)
    if text_length != 3200:
        raise ValueError('experiment0036 frozen text extent is3200')
    result = extend_positions(source, max(1000, text_length, latent_length)) if component == 'vector' else copy.deepcopy(source)
    for values, shapes in ((result.graph.input, expected_in), (result.graph.output, expected_out)):
        if [v.name for v in values] != list(shapes):
            raise ValueError('source ABI order differs')
        for value in values:
            tensor = value.type.tensor_type
            dtype = onnx.TensorProto.INT64 if value.name == 'text_ids' else onnx.TensorProto.FLOAT
            if tensor.elem_type != dtype or len(tensor.shape.dim) != len(shapes[value.name]):
                raise ValueError('source ABI type/rank differs')
            for dim, size in zip(tensor.shape.dim, shapes[value.name]):
                dim.ClearField('dim_param')
                dim.dim_value = size
    result = onnx.shape_inference.infer_shapes(result, strict_mode=True, data_prop=False)
    if component == 'vector':
        result = capacity.stable_softplus(result)
    onnx.checker.check_model(result, full_check=True)
    expected_nodes = list(source.graph.node)
    if component == 'vector':
        indices = [i for i, n in enumerate(expected_nodes) if n.name == capacity.SOFTPLUS]
        if len(indices) != 1:
            raise ValueError('unexpected Softplus identity')
        i = indices[0]
        expected_nodes[i:i+1] = capacity.replacement_nodes()
    def blobs(values):
        return [v.SerializeToString() for v in values]
    if blobs(expected_nodes) != blobs(result.graph.node):
        raise ValueError('unapproved computation-node change')
    original = list(source.graph.initializer)
    derived = list(result.graph.initializer)
    if len(derived) != len(original) + int(component == 'vector'):
        raise ValueError('unexpected initializer count')
    rows = []
    for before, after in zip(original, derived):
        same = before.SerializeToString() == after.SerializeToString()
        if before.name != after.name or (not same and not (component == 'vector' and before.name == capacity.INCREMENTS)):
            raise ValueError('learned/other initializer changed')
        rows.append({'name': before.name, 'unchanged': same,
                     'before_sha256': hashlib.sha256(before.SerializeToString()).hexdigest(),
                     'after_sha256': hashlib.sha256(after.SerializeToString()).hexdigest()})
    return result, {'all_learned_and_other_initializers_unchanged': True,
                    'initializers': rows, 'inputs': expected_in, 'outputs': expected_out,
                    'source_nodes': len(source.graph.node), 'derived_nodes': len(result.graph.node),
                    'position_extent': max(1000, text_length, latent_length) if component == 'vector' else None,
                    'position_prefix_and_theta_preserved': True if component == 'vector' else None,
                    'stable_softplus_identity': component == 'vector', 'model_execution': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--component', choices=tuple(PINS), required=True)
    parser.add_argument('--text-length', type=int, default=3200)
    parser.add_argument('--latent-length', type=int, default=1,
                        help='Ignored for duration/text ABI; must be frozen before vector/vocoder.')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    pin = PINS[args.component]
    source_path = args.source_root / pin['filename']
    if source_path.stat().st_size != pin['bytes'] or sha(source_path) != pin['sha256']:
        raise ValueError('official FP32 source pin differs')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    result = {'component': args.component, 'source': pin, 'status': 'started'}
    try:
        import onnx
        source = onnx.load(str(source_path), load_external_data=False)
        derivative, delta = derive(source, args.component, args.text_length, args.latent_length)
        output = args.output_dir / (args.component + '.onnx')
        with output.open('xb') as stream:
            stream.write(derivative.SerializeToString())
        (args.output_dir / 'structural-delta.json').write_text(json.dumps(delta, indent=2) + '\n')
        if sha(source_path) != pin['sha256']:
            raise ValueError('source changed')
        result.update(status='source_derivative_only_not_QNN_proof',
                      derivative={'path':str(output.resolve()), 'bytes':output.stat().st_size, 'sha256':sha(output)},
                      inputs=delta['inputs'], outputs=delta['outputs'])
    except BaseException as error:
        result.update(status='error', error=str(error))
        raise
    finally:
        result.update(elapsed_seconds=time.monotonic()-started,
                      process_ru_maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        (args.output_dir / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

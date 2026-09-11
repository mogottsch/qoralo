#!/usr/bin/env python3
"""AR171 source-only derivative: scale query instead of score. No QNN/AOT work."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import onnx
from onnx import helper, numpy_helper

EMBED = '/model/embed_tokens/GatherBlockQuantized/output_0'
LAYERS = (2, 5, 9, 13, 17, 21, 24, 27)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def rewrite(model):
    """Copy the protobuf; all parameters, interfaces and unrelated nodes stay exact."""
    model = copy.deepcopy(model)
    inputs = {v.name: v for v in model.graph.input}
    shape = lambda v: [d.dim_value for d in v.type.tensor_type.shape.dim]
    if shape(inputs[EMBED]) != [1, 171, 2048] or shape(inputs['attention_mask']) != [1, 1, 171, 4096]:
        raise ValueError('Only the fixed AR171/capacity4096 graph is authorized')
    scale = next(t for t in model.graph.initializer if t.name == '__attn_scale')
    value = numpy_helper.to_array(scale)
    if value.dtype != np.float32 or value.shape != () or value.item() != 0.125:
        raise ValueError('Expected exact scalar FLOAT32 0.125')
    producers = {y: n for n in model.graph.node for y in n.output}
    consumers = {}
    for n in model.graph.node:
        for x in n.input:
            consumers.setdefault(x, []).append(n.name)
    outputs = {v.name for v in model.graph.output}
    replacement, removed, changes = {}, set(), []
    for n in model.graph.node:
        if n.op_type != 'Mul' or list(n.input)[-1:] != ['__attn_scale']:
            continue
        score = producers[n.input[0]]
        if score.op_type != 'MatMul' or len(score.output) != 1:
            raise ValueError('Unexpected score producer')
        if consumers[score.output[0]] != [n.name] or score.output[0] in outputs:
            raise ValueError('Unscaled score has another consumer')
        query, key = score.input
        if not query.endswith('/htp_chunk/query') or not key.endswith('/htp_chunk/key_r'):
            raise ValueError('Unexpected query/key boundary')
        scaled_query = query.removesuffix('/query') + '/scaled_query'
        if scaled_query in producers:
            raise ValueError('Already transformed')
        qscale = helper.make_node('Mul', [query, '__attn_scale'], [scaled_query], name=scaled_query)
        matmul = copy.deepcopy(score)
        matmul.input[0] = scaled_query
        matmul.output[0] = n.output[0]
        replacement[score.name] = [qscale, matmul]
        removed.add(n.name)
        changes.append({'query': query, 'key': key, 'scaled_query': scaled_query,
                        'retired_score': score.output[0], 'scaled_score': n.output[0],
                        'original_matmul': score.name, 'removed_mul': n.name})
    if len(changes) != 8 or len(replacement) != 8:
        raise ValueError(f'Expected exactly eight attention scale sites, got {len(changes)}')
    nodes = []
    for n in model.graph.node:
        if n.name not in removed:
            nodes.extend(replacement.get(n.name, [n]))
    model.graph.ClearField('node')
    model.graph.node.extend(nodes)
    retired = {x['retired_score'] for x in changes}
    value_info = [v for v in model.graph.value_info if v.name not in retired]
    model.graph.ClearField('value_info')
    model.graph.value_info.extend(value_info)
    return model, changes


def external_paths(model, source):
    locations = sorted({dict((e.key, e.value) for e in t.external_data)['location']
                        for t in model.graph.initializer if t.external_data})
    for location in locations:
        if Path(location).name != location:
            raise ValueError('Expected basename-only external data reference')
    return {location: (Path(source).parent / location).resolve(strict=True) for location in locations}


def stage(source, destination, copy_budget_bytes=6 << 30):
    if destination.parent.resolve() == source.parent.resolve():
        raise ValueError('Never stage into the immutable baseline directory')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    baseline = onnx.load(source, load_external_data=False)
    derivative, changes = rewrite(baseline)
    paths = external_paths(baseline, source)
    if sum(p.stat().st_size for p in paths.values()) > copy_budget_bytes:
        raise RuntimeError('External copies exceed the remaining campaign disk budget')
    destination.parent.mkdir(parents=True, exist_ok=True)
    copies = []
    for location, original in paths.items():
        target = destination.parent / location
        if target.exists() or target.is_symlink():
            raise FileExistsError(target)
        before = sha(original)
        shutil.copyfile(original, target)
        copied, after = sha(target), sha(original)
        if target.is_symlink() or target.stat().st_nlink != 1 or target.samefile(original):
            raise ValueError('External data copy must be an independent regular file')
        if not (before == copied == after):
            raise ValueError('External data before/copy/original-after SHA mismatch')
        copies.append({'source': str(original), 'copy': str(target), 'bytes': target.stat().st_size,
                       'source_before_sha256': before, 'copy_sha256': copied,
                       'source_after_sha256': after, 'copy_link_count': target.stat().st_nlink})
    # Saving with unloaded external data only writes the small protobuf, never weights.
    onnx.save(derivative, destination)
    onnx.checker.check_model(str(destination), full_check=False)
    assert [x.SerializeToString() for x in baseline.graph.initializer] == [x.SerializeToString() for x in derivative.graph.initializer]
    for field in ('input', 'output'):
        assert [x.SerializeToString() for x in getattr(baseline.graph, field)] == [x.SerializeToString() for x in getattr(derivative.graph, field)]
    return {'source_sha256': sha(source), 'derivative_sha256': sha(destination),
            'site_count': len(changes), 'changes': changes, 'external_copies': copies,
            'initializers_and_interfaces_unchanged': True, 'aot_or_accelerator_work': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(json.dumps(stage(args.source, args.destination), indent=2, sort_keys=True))

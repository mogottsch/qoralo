#!/usr/bin/env python3
"""Prepare an exact-node layer-4/one-head derivative plus whole-candidate scope.

Reads ONNX metadata without external weights, then only bounded scalar/axis
initializers used by the derivative. Original candidate and data stay unchanged.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import resource

from value_precision_path import override_float16

TRACK = Path(__file__).resolve().parents[1]
RUNS = TRACK / '.local/runs'
SOURCES = {
    1: ('global-value-fp16-20260910T090755Z-attempt-05', '077b5ce33f694e4a04210e2b37af9e5c9dd4b80d63dc741dfbedbdbea1e73c63', 'f67d8ae994cd28625ad50f18f7652680e675be7cd0603bd04319d3b3a3a1dac3'),
    128: ('global-value-fp16-20260910T095945Z-attempt-06', '0b36dc55b669a54469b669a86364d112cc82f3811b11c2f8662cc7dbd49527c0', '1813412b395adde9033e9a8eb0a076f5fd62bc14217af7670a93750968ba165c'),
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def discover(model):
    producers = {name: n for n in model.graph.node for name in n.output}
    layers = []
    for layer, cat, count in ((4, 'cat_58', 8), (9, 'cat_118', 8), (14, 'cat_178', 40)):
        cache_in, cache_out = f'past_value_{layer}_h0_in', f'past_value_{layer}_h0_out'
        concat = producers[cat]
        assert concat.op_type == 'Concat' and len(concat.input) == 2
        norm_path = []
        cur = concat.input[1]
        while True:
            n = producers[cur]
            norm_path.append(cur)
            if n.op_type == 'Mul':
                norm = n
                break
            assert n.op_type in ('Cast', 'Identity', 'Transpose') and len(n.input) == 1
            cur = n.input[0]
        assert norm.name == f'node_mul_{4709 + (layer-4)//5 * 5425}'
        consumers = [n for n in model.graph.node if cat in n.input]
        assert len(consumers) == count
        assert all(n.op_type == 'MatMul' and n.input[1] == cat and len(n.output) == 1 for n in consumers)
        names = {cache_in, cache_out, cat, concat.input[0], *norm_path,
                 *(n.output[0] for n in consumers)}
        layers.append({'layer': layer, 'cache_input': cache_in, 'cache_output': cache_out,
                       'concat': cat, 'normalization_output': norm.output[0],
                       'v_projection_boundary': norm.input[0],
                       'consumer_nodes': [n.name for n in consumers],
                       'consumer_output_names': [n.output[0] for n in consumers],
                       'float16_override_names': sorted(names)})
    return layers


def main():
    resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
    p = argparse.ArgumentParser()
    p.add_argument('--ar', type=int, choices=(1, 128), required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    import onnx
    from onnx import helper, numpy_helper, external_data_helper
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    run, onnx_sha, enc_sha = SOURCES[args.ar]
    source = RUNS / run / f'onnx/ar{args.ar}_cl4096_1_of_1/ar{args.ar}_cl4096_1_of_1.onnx'
    encpath = source.with_suffix('.encodings')
    assert digest(source) == onnx_sha and digest(encpath) == enc_sha
    model = onnx.load(source, load_external_data=False)
    enc = json.loads(encpath.read_text())
    layers = discover(model)
    all_names = set().union(*(set(l['float16_override_names']) for l in layers))
    full_enc, full_changes = override_float16(enc, all_names)
    # This is the complete future candidate encoding file, not a converted model.
    (out / 'full-candidate.encodings').write_text(json.dumps(full_enc, indent=2) + '\n')
    del full_enc
    selected = layers[0]
    producers = {name: n for n in model.graph.node for name in n.output}
    mm = next(n for n in model.graph.node if n.name == selected['consumer_nodes'][0])
    boundary_names = [selected['v_projection_boundary'], selected['cache_input'], mm.input[0]]
    outputs = [selected['cache_output'], mm.output[0]]
    inits = {t.name: t for t in model.graph.initializer}
    needed_nodes, needed_inits = set(), set()
    pending = list(outputs)
    while pending:
        name = pending.pop()
        if name in boundary_names:
            continue
        if name in inits:
            needed_inits.add(name)
            continue
        node = producers[name]
        if node.name in needed_nodes:
            continue
        needed_nodes.add(node.name)
        pending.extend(n for n in node.input if n)
    nodes = [copy.deepcopy(n) for n in model.graph.node if n.name in needed_nodes]
    vi = {v.name: v for v in list(model.graph.value_info) + list(model.graph.input) + list(model.graph.output)}
    constants, constant_evidence = [], []
    for name in sorted(needed_inits):
        tensor = copy.deepcopy(inits[name])
        ext = {e.key: e.value for e in tensor.external_data}
        # Guard each external read; never materialize a checkpoint weight array.
        element_count = 1
        for d in tensor.dims:
            element_count *= d
        assert element_count <= 1024, (name, tensor.dims)
        if tensor.data_location == onnx.TensorProto.EXTERNAL:
            assert int(ext.get('length', '0')) in range(1, 8193), (name, ext)
            location = (source.parent / ext['location']).resolve()
            assert location == source.with_suffix('.data').resolve()
            external_data_helper.load_external_data_for_tensor(tensor, str(source.parent))
            tensor.data_location = onnx.TensorProto.DEFAULT
            tensor.ClearField('external_data')
        values = numpy_helper.to_array(tensor).tolist()
        constant_evidence.append({'name': name, 'dims': list(tensor.dims), 'values': values,
                                  'serialized_sha256': hashlib.sha256(tensor.SerializeToString()).hexdigest(),
                                  'source_external_data': ext})
        constants.append(tensor)
    fragment = helper.make_model(helper.make_graph(nodes, f'gemma_value_island_ar{args.ar}',
                    [copy.deepcopy(vi[n]) for n in boundary_names],
                    [copy.deepcopy(vi[n]) for n in outputs], constants),
                    opset_imports=[copy.deepcopy(o) for o in model.opset_import],
                    producer_name='saved-gemma-value-island-derivative')
    fragment.ir_version = model.ir_version
    onnx.checker.check_model(fragment)
    onnx.save(fragment, out / 'derivative.onnx')
    used = set(boundary_names + outputs) | {x for n in nodes for x in list(n.input) + list(n.output)}
    filtered = copy.deepcopy(enc)
    filtered['activation_encodings'] = [e for e in enc['activation_encodings'] if e['name'] in used]
    filtered['param_encodings'] = [e for e in enc['param_encodings'] if e['name'] in needed_inits]
    candidate, changes = override_float16(filtered, all_names & used)
    for label, data in (('control', filtered), ('candidate', candidate)):
        (out / f'{label}.encodings').write_text(json.dumps(data, indent=2) + '\n')
    result = {'ar': args.ar, 'source_onnx': str(source), 'source_onnx_sha256': onnx_sha,
              'source_encodings_sha256': enc_sha, 'all_layers': layers,
              'full_override_count': len(all_names), 'full_changes': full_changes,
              'derivative_scope': 'layer4, first value-MatMul head, exact original nodes/constants/shapes; V-projection/probability are boundary inputs',
              'derivative_nodes': [n.name for n in nodes], 'derivative_inputs': boundary_names,
              'derivative_outputs': outputs, 'constants': constant_evidence, 'derivative_changes': changes,
              'derivative_onnx_sha256': digest(out / 'derivative.onnx'),
              'full_candidate_encodings_sha256': digest(out / 'full-candidate.encodings'),
              'external_weight_arrays_loaded': False, 'inference': False, 'phone_access': False,
              'full_conversion_done': False}
    (out / 'preparation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'ar': args.ar, 'full_override_count': len(all_names), 'derivative_nodes': len(nodes), 'constants': constant_evidence}))


if __name__ == '__main__':
    main()

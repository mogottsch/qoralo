#!/usr/bin/env python3
"""Inspect pinned ONNX metadata; prepare one derivative only with a new bound release.

No Torch, ORT, QNN, model-forward or context-generation code. External tensor data
is never loaded. Embedded initializers are necessarily parsed with the protobuf;
inspection decodes only small constants (<=32 values) plus the explicitly scoped
1000-element INT64 position table, never floating weight arrays.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'protocol/target.json'
SOFTPLUS = '/vector_estimator/vector_field/time_encoder/mlp/mlp.1/Softplus'
SOFTPLUS_INPUT = '/vector_estimator/vector_field/time_encoder/mlp/mlp.0/linear/Gemm_output_0'
SOFTPLUS_OUTPUT = SOFTPLUS + '_output_0'
SOFTPLUS_CONSUMER = '/vector_estimator/vector_field/time_encoder/mlp/mlp.1/Tanh'
INCREMENTS = 'vector_estimator.tts.ttl.vector_field.main_blocks.3.attn.increments'
THETA = 'vector_estimator.tts.ttl.vector_field.main_blocks.3.attn.theta'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def save(path, value):
    with Path(path).open('x') as stream: json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def source_identity(path, target, component):
    expected = target['sources'][component]
    if path.is_symlink() or not path.is_file() or path.stat().st_size != expected['bytes']:
        raise ValueError('source size/type does not match pinned official graph')
    digest = sha(path)
    if digest != expected['sha256']: raise ValueError('source hash differs from pinned official graph')
    return {'path': str(path.resolve()), 'bytes': path.stat().st_size, 'sha256': digest}


def io_shapes(component, t, l):
    if type(t) is not int or type(l) is not int or not 10 <= t <= 16384 or not 1 <= l <= 10000:
        raise ValueError('T/L outside app manifest ranges')
    if component == 'duration': return {'text_ids': [1,t], 'style_dp': [1,8,16], 'text_mask': [1,1,t]}, {'duration': [1]}
    if component == 'text': return {'text_ids': [1,t], 'style_ttl': [1,50,256], 'text_mask': [1,1,t]}, {'text_emb': [1,256,t]}
    if component == 'vector': return {'noisy_latent': [1,144,l], 'text_emb': [1,256,t], 'style_ttl': [1,50,256], 'latent_mask': [1,1,l], 'text_mask': [1,1,t], 'current_step': [1], 'total_step': [1]}, {'denoised_latent': [1,144,l]}
    if component == 'vocoder': return {'latent': [1,144,l]}, {'wav_tts': [1,3072*l]}
    raise ValueError('unknown component')


def value_info(value):
    tensor = value.type.tensor_type
    return {'name': value.name, 'dtype': tensor.elem_type,
            'shape': [d.dim_value if d.HasField('dim_value') else d.dim_param or None for d in tensor.shape.dim]}


def tensor_info(tensor, constant_attribute=False):
    import onnx
    result = {'name': tensor.name, 'dtype': tensor.data_type, 'shape': list(tensor.dims),
              'elements': math.prod(tensor.dims), 'external': bool(tensor.external_data) or tensor.data_location == onnx.TensorProto.EXTERNAL}
    result['small_values'] = None
    result['values_reason'] = 'external data forbidden' if result['external'] else 'more than32 values or unsupported dtype; metadata only'
    positional_constant = (tensor.name == INCREMENTS and tensor.data_type == 7 and list(tensor.dims) == [1,1000,1]) or (tensor.name == THETA and tensor.data_type == 1 and list(tensor.dims) == [1,1,32])
    limit = 1000 if positional_constant else 32
    allowed_types = (1,2,3,4,5,6,7,9,10,11,12,13) if constant_attribute or positional_constant else (2,3,4,5,6,7,9,12,13)
    if not result['external'] and result['elements'] <= limit and tensor.data_type in allowed_types:
        from onnx import numpy_helper
        array = numpy_helper.to_array(tensor).reshape(-1)
        result['small_values'] = [v.item() if not isinstance(v.item(), float) or math.isfinite(v.item()) else repr(v.item()) for v in array]
        result['values_reason'] = 'explicitly scoped positional constant' if positional_constant else 'bounded constant decoding, at most32 elements'
    return result


def inspect_graph(model):
    import onnx
    nodes = []
    for node in model.graph.node:
        attrs = {}
        for attr in node.attribute:
            if attr.type == onnx.AttributeProto.TENSOR: attrs[attr.name] = tensor_info(attr.t, constant_attribute=node.op_type == 'Constant')
            elif attr.type == onnx.AttributeProto.INT: attrs[attr.name] = attr.i
            elif attr.type == onnx.AttributeProto.INTS: attrs[attr.name] = list(attr.ints)
            elif attr.type == onnx.AttributeProto.FLOAT: attrs[attr.name] = attr.f if math.isfinite(attr.f) else repr(attr.f)
            elif attr.type == onnx.AttributeProto.STRING: attrs[attr.name] = attr.s.decode('utf-8', errors='backslashreplace')
            else: attrs[attr.name] = {'unresolved_attribute_type': attr.type, 'reason': 'not interpreted by bounded metadata inspector'}
        nodes.append({'name': node.name, 'op': node.op_type, 'domain': node.domain, 'inputs': list(node.input), 'outputs': list(node.output), 'attributes': attrs})
    return {'ir_version': model.ir_version, 'opsets': [{'domain': x.domain, 'version': x.version} for x in model.opset_import],
            'inputs': [value_info(x) for x in model.graph.input], 'outputs': [value_info(x) for x in model.graph.output],
            'value_info': [value_info(x) for x in model.graph.value_info],
            'initializers': [tensor_info(x) for x in model.graph.initializer], 'nodes': nodes,
            'operator_counts': dict(Counter(x.op_type for x in model.graph.node)),
            'range_nodes': [x['name'] for x in nodes if x['op'] == 'Range'],
            'uninspected_sparse_initializers': len(model.graph.sparse_initializer),
            'uninspected_local_functions': len(model.functions),
            'larger_shape_support': None, 'larger_shape_support_reason': 'Metadata only: no full-model shape inference/checker, derivative, runtime or forward.'}


def reject_external(model):
    import onnx
    for tensor in model.graph.initializer:
        if tensor.external_data or tensor.data_location == onnx.TensorProto.EXTERNAL:
            raise ValueError('external initializers forbidden in derivative path')
    if model.graph.sparse_initializer or model.functions: raise ValueError('unsupported sparse initializer/local function')
    for node in model.graph.node:
        for attr in node.attribute:
            if attr.type in (onnx.AttributeProto.GRAPH, onnx.AttributeProto.GRAPHS, onnx.AttributeProto.TENSORS):
                raise ValueError('nested graph/tensor collection needs separate review')
            if attr.type == onnx.AttributeProto.TENSOR and (attr.t.external_data or attr.t.data_location == onnx.TensorProto.EXTERNAL):
                raise ValueError('external Constant tensor forbidden')


def require_position_capacity(model, t, l):
    """Fail before transformation: the original rotary table cannot supply >1000 positions."""
    import onnx
    matches = [v for v in model.graph.initializer if v.name == INCREMENTS]
    if len(matches) != 1 or matches[0].data_type != onnx.TensorProto.INT64 or list(matches[0].dims) != [1,1000,1]:
        raise ValueError('unrecognized vector positional-table contract; separate review required')
    if matches[0].external_data or matches[0].data_location == onnx.TensorProto.EXTERNAL:
        raise ValueError('external positional table forbidden')
    from onnx import numpy_helper
    if numpy_helper.to_array(matches[0]).reshape(-1).tolist() != list(range(1000)):
        raise ValueError('opaque/non-arange positional table; stop for separate review')
    if max(t,l) > 1000:
        raise ValueError('vector positional table has only1000 entries; T/L expansion requires a separately reviewed constant/graph change')


def specialize(model, component, t, l):
    """Pure protobuf transform; tests use synthetic graphs only in preparation."""
    import onnx
    reject_external(model)
    expected_in, expected_out = io_shapes(component, t, l)
    if component == 'vector': require_position_capacity(model,t,l)
    if [x.name for x in model.graph.input] != list(expected_in) or [x.name for x in model.graph.output] != list(expected_out):
        raise ValueError('I/O names or order differ from pinned component ABI')
    result = onnx.ModelProto(); result.CopyFrom(model)
    for values, expected in ((result.graph.input, expected_in), (result.graph.output, expected_out)):
        for value in values:
            shape = expected[value.name]
            tensor = value.type.tensor_type
            wanted_dtype = onnx.TensorProto.INT64 if value.name == 'text_ids' else onnx.TensorProto.FLOAT
            if tensor.elem_type != wanted_dtype or len(tensor.shape.dim) != len(shape): raise ValueError('ABI dtype/rank mismatch')
            for d, size in zip(tensor.shape.dim, shape): d.ClearField('dim_param'); d.dim_value = size
    # Source graph ONLY: shape inference may reject internally fixed conflicting shapes.
    result = onnx.shape_inference.infer_shapes(result, strict_mode=True, data_prop=False)
    onnx.checker.check_model(result, full_check=True)
    if [n.SerializeToString() for n in model.graph.node] != [n.SerializeToString() for n in result.graph.node]: raise ValueError('specialization changed computation nodes')
    if [x.SerializeToString() for x in model.graph.initializer] != [x.SerializeToString() for x in result.graph.initializer]: raise ValueError('specialization changed initializers')
    return result


def stable_softplus(model):
    """Same audited seven-node identity, on the newly source-bound derivative."""
    import onnx
    from onnx import helper
    reject_external(model)
    if [(x.domain, x.version) for x in model.opset_import if x.domain in ('', 'ai.onnx')] not in ([('',19)], [('ai.onnx',19)]): raise ValueError('requires standard opset19')
    matches = [(i,n) for i,n in enumerate(model.graph.node) if n.name == SOFTPLUS]
    if len(matches) != 1: raise ValueError('must have exactly one locked Softplus node')
    index, node = matches[0]
    if node.op_type != 'Softplus' or node.domain not in ('','ai.onnx') or list(node.input) != [SOFTPLUS_INPUT] or list(node.output) != [SOFTPLUS_OUTPUT] or node.attribute: raise ValueError('Softplus contract differs')
    known = [v for v in [*model.graph.input,*model.graph.output,*model.graph.value_info] if v.name == SOFTPLUS_INPUT]
    if len(known) != 1 or value_info(known[0]) != {'name': SOFTPLUS_INPUT, 'dtype': onnx.TensorProto.FLOAT, 'shape': [2,256]}: raise ValueError('expected Softplus float32[2,256] input')
    consumers = [n for n in model.graph.node if SOFTPLUS_OUTPUT in n.input]
    if len(consumers) != 1 or consumers[0].name != SOFTPLUS_CONSUMER or consumers[0].op_type != 'Tanh' or consumers[0].domain not in ('','ai.onnx'): raise ValueError('unexpected Softplus consumer')
    if SOFTPLUS_OUTPUT in {v.name for v in model.graph.output}: raise ValueError('Softplus is an unexpected graph output')
    prefix = SOFTPLUS + '/stable'; one = prefix + '/one'
    names = [prefix+'/'+s for s in ('relu','abs','neg_abs','exp','one_plus_exp','log')]
    occupied = {s for n in model.graph.node for s in [*n.input,*n.output]} | {v.name for v in [*model.graph.initializer,*model.graph.input,*model.graph.output,*model.graph.value_info]}
    if occupied.intersection([one,*names]): raise ValueError('replacement tensor collision')
    relu, absolute, neg, exponent, plus, logarithm = names
    specs = [('Relu',[SOFTPLUS_INPUT],[relu],'Relu'),('Abs',[SOFTPLUS_INPUT],[absolute],'Abs'),('Neg',[absolute],[neg],'Neg'),('Exp',[neg],[exponent],'Exp'),('Add',[exponent,one],[plus],'AddOne'),('Log',[plus],[logarithm],'Log'),('Add',[relu,logarithm],[SOFTPLUS_OUTPUT],'AddFinal')]
    added = [helper.make_node(op, inputs, outputs, name=prefix+'/'+label) for op,inputs,outputs,label in specs]
    if {n.name for n in added}.intersection(n.name for n in model.graph.node): raise ValueError('replacement node collision')
    result = onnx.ModelProto(); result.CopyFrom(model)
    del result.graph.node[index]
    for offset, item in enumerate(added): result.graph.node.insert(index+offset,item)
    result.graph.initializer.append(helper.make_tensor(one, onnx.TensorProto.FLOAT, [], [1.0]))
    onnx.checker.check_model(result, full_check=True)
    unchanged = list(result.graph.node[:index]) + list(result.graph.node[index+7:])
    original = list(model.graph.node[:index]) + list(model.graph.node[index+1:])
    if [n.SerializeToString() for n in unchanged] != [n.SerializeToString() for n in original]: raise ValueError('non-target node mutation')
    if [v.SerializeToString() for v in result.graph.initializer[:-1]] != [v.SerializeToString() for v in model.graph.initializer]: raise ValueError('original initializer mutation')
    return result


def validate_release(path, component, source, output, target_path=TARGET):
    release = json.loads(Path(path).read_text())
    expected = {'approved': True, 'permission': 'one_source_derivative_only_no_execution', 'component': component,
                'source_sha256': source['sha256'], 'target_sha256': sha(target_path), 'helper_sha256': sha(__file__),
                'output_dir': str(output.resolve())}
    if release != expected: raise ValueError('missing/mismatched explicit derivative-only release')
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['inspect','derive'])
    parser.add_argument('--component', choices=['duration','text','vector','vocoder'], required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--release', type=Path)
    args = parser.parse_args()
    target = json.loads(TARGET.read_text())
    # Gate derive BEFORE reading a sizeable model. Exact source bytes checked below.
    if args.mode == 'derive':
        if args.release is None: parser.error('derive requires a separately approved output/source/target/helper-bound release')
        validate_release(args.release, args.component, target['sources'][args.component], args.output_dir)
    if args.output_dir.exists(): raise FileExistsError('output directory must be fresh')
    args.output_dir.mkdir(parents=True)
    status = {'status':'started', 'mode':args.mode, 'component':args.component, 'external_data_loaded':False,
              'embedded_initializers_parsed':False, 'model_forwards':0, 'runtime_loads':0, 'qnn_compile_calls':0,
              'target_sha256':sha(TARGET), 'helper_sha256':sha(__file__)}
    start = time.monotonic()
    try:
        source = source_identity(args.source, target, args.component); status['source'] = source
        import onnx
        model = onnx.load(str(args.source), load_external_data=False)
        status['embedded_initializers_parsed'] = True
        status['onnx_version'] = onnx.__version__; status['python_version'] = sys.version
        if args.mode == 'inspect':
            save(args.output_dir/'metadata.json', inspect_graph(model))
            status['full_derivative_written'] = False
        else:
            derivative = specialize(model,args.component,target['text_length'],target['latent_length'])
            if args.component == 'vector': derivative = stable_softplus(derivative)
            path = args.output_dir / (args.component+'.onnx')
            onnx.save_model(derivative,str(path),save_as_external_data=False)
            status['full_derivative_written'] = True
            status['derivative'] = {'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path)}
            status['specialization_preserved_nodes_and_initializers'] = True
            status['only_operator_change'] = 'one Softplus replaced with7 stable nodes +scalar1' if args.component=='vector' else None
        if sha(args.source) != source['sha256']: raise ValueError('source changed during inspection/transformation')
        status['status'] = 'complete'
        status['prohibited_modules_imported'] = [s for s in sys.modules if s.split('.')[0] in ('torch','onnxruntime','executorch')]
        if status['prohibited_modules_imported']: raise RuntimeError('prohibited runtime import')
    except BaseException as error:
        status.update(status='error', error={'type':type(error).__name__, 'message':str(error)})
        raise
    finally:
        status['elapsed_seconds'] = time.monotonic()-start
        status['process_ru_maxrss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        save(args.output_dir/'result.json',status)
    print(json.dumps(status,indent=2))


if __name__ == '__main__': main()

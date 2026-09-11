#!/usr/bin/env python3
"""One source-only collection: JSON/text and zstd metadata, never a model/runtime import."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
EXP = OUT.parents[1]
REPO = EXP.parents[1]
AUDIT = EXP / 'results/persistent-state-range-audit-20260910'
PKG = REPO / 'artifacts/venv-executorch-1.2/lib/python3.11/site-packages/executorch/backends/qualcomm'
CPP = EXP / '.local/executorch/backends/qualcomm'


def identity(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def save(name, obj):
    with (OUT/name).open('x') as f:
        json.dump(obj, f, indent=2, allow_nan=False)
        f.write('\n')


def main():
    start = time.monotonic()
    metadata_path = AUDIT/'metadata/metadata.json'
    metadata = json.loads(metadata_path.read_text())
    selected = [s for s in metadata['states'] if s['state_index'] in (3, 15)]
    assert len(selected) == 2
    for s in selected:
        assert s['kind'] == 'key_cache_update'
        assert s['input_shape'] == [1, 2, 256, 4095]
        assert s['output_shape'] == [1, 2, 256, 1]
        assert s['carry_transport'] == 'write_new_token_at_position_axis_3'
        assert s['native_finalized_encodings'] is None
    observations = {}
    for label in ('qdq_p0', 'qnn_p0'):
        path = AUDIT/f'observations/{label}.json'
        saved = json.loads(path.read_text())
        rows = [s for s in saved['states'] if s['state_index'] in (3, 15)]
        assert [s['next_input_quantizers'][0]['coverage']['code_clipped_total'] for s in rows] == [1, 0]
        observations[label] = {'source': identity(path), 'selected_preexisting_rows': rows}
    save('selected-states.json', {'source': identity(metadata_path), 'states': selected,
          'preexisting_observations': observations, 'new_tensor_deserializations': 0,
          'control_limit': 'state15 matches K geometry/transport but has unequal read/write domains; clean retained samples are not a no-clipping guarantee'})

    # Recover ONLY the already-retained graph metadata, never open PT2/PTE/weights.
    compressed = EXP/'results/conv-history-encoding-audit-20260910/raw/graph-model.json.zst'
    assert identity(compressed)['sha256'] == '4769c006b7c008c0173a40b7171e63c3d0b075ac41dd0d249b38df18498b1ac5'
    raw = subprocess.run(['zstd', '-dc', str(compressed)], check=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15).stdout
    assert len(raw) == 32499235
    assert hashlib.sha256(raw).hexdigest() == '2d879235c4d4a47643378e3ec3739bd587d4b0a68b23097b8ba64092ce20ad86'
    graph = json.loads(raw)['graph_module']['graph']
    nodes = {o['as_tensor']['name']: n for n in graph['nodes'] for o in n['outputs'] if 'as_tensor' in o}
    def lean(node):
        return {k: node[k] for k in ('name', 'target', 'inputs', 'outputs')}
    def parent(n):
        return n['inputs'][0]['arg'].get('as_tensor', {}).get('name') if n['inputs'] else None
    def scalars(n):
        return {x['name']: next(iter(x['arg'].values())) for x in n['inputs']
                if set(x['arg']) & {'as_float', 'as_int', 'as_scalar_type'}}
    paths = []
    for state, cat_name in zip(selected, ('cat_7', 'cat_34')):
        cat = nodes[cat_name]
        assert cat['target'] == 'torch.ops.aten.cat.default' and scalars(cat)['dim'] == -1
        names = [x['name'] for x in cat['inputs'][0]['arg']['as_tensors']]
        assert names[0] == state['input']['quantizers'][0]['branches'][0]['dq_node']
        children = [n for n in graph['nodes'] if parent(n) == cat_name]
        q = [n for n in children if n['target'] == 'torch.ops.quantized_decomposed.quantize_per_tensor.default']
        assert len(q) == 1
        dq = [n for n in graph['nodes'] if parent(n) == q[0]['outputs'][0]['as_tensor']['name']]
        assert len(dq) == 1 and 'dequantize_per_tensor' in dq[0]['target']
        assert scalars(q[0]) == scalars(dq[0])
        rows = [cat, *[nodes[n] for n in names], nodes[parent(nodes[names[1]])], q[0], dq[0]]
        paths.append({'state_index': state['state_index'], 'cat_name': cat_name,
                      'cat_encoding': scalars(q[0]), 'current_key_encoding': scalars(nodes[names[1]]),
                      'source_nodes': [lean(n) for n in rows],
                      'cat_tensor_metadata': graph['tensor_values'][cat_name],
                      'native_corresponding_node_name': None,
                      'native_name_reason': 'No selected-state postpass/native wrapper capture from the full model retained here.'})
    save('selected-cat-paths.json', {'compressed_source': identity(compressed),
         'recovered_metadata_bytes': len(raw), 'recovered_metadata_sha256': hashlib.sha256(raw).hexdigest(),
         'selected_paths': paths, 'model_archives_opened': 0, 'tensor_payloads_read': 0})
    del graph, nodes, raw

    specs = [
        (EXP/'results/host-histogram-precision-20260910/reproduction/compile.sh', [(5,19)], 'historical full-model route'),
        (EXP/'tools/compile_exact_qnn.py', [(528,563)], 'TagQuantIO disabled, sharding and lowering'),
        (AUDIT/'source/replay_saved_qdq.py.txt', [(1,19)], 'float cache insertion; not replacement or shifting'),
        (AUDIT/'source/qwen35_qnn_model.py.txt', [(10,35)], 'K update versus full attention cache consumer'),
        (PKG/'_passes/annotate_quant_attrs.py', [(48,60),(84,129)], 'annotation and per-consumer requantization'),
        (PKG/'_passes/qnn_pass_manager.py', [(253,273)], 'preprocess ordering'),
        (PKG/'_passes/insert_io_qdq.py', [(78,90),(124,151)], 'move input attrs onto inserted Q, insert output DQ'),
        (PKG/'_passes/insert_requantize.py', [(56,82),(90,102)], 'per-consumer Convert insertion'),
        (PKG/'builders/utils.py', [(146,161)], 'UINT16 carrier deduction'),
        (PKG/'builders/node_visitor.py', [(51,60),(250,296),(318,344),(353,360),(379,405),(443,490)], 'encoding sign, tensor type/name/dtype and fake-input wrappers'),
        (PKG/'builders/op_quantize.py', [(28,65)], 'submitted Quantize operator'),
        (PKG/'builders/op_dequantize.py', [(26,54)], 'submitted Dequantize operator'),
        (PKG/'builders/op_to.py', [(35,77),(145,152)], 'Cast versus Convert decision, not host math'),
        (PKG/'qnn_preprocess.py', [(48,73),(117,145)], 'build then Compile, no finalized internal-tensor query'),
        (CPP/'aot/python/PyQnnManagerAdaptor.cpp', [(58,63)], 'float32 scale, int32 negative zero point'),
        (CPP/'aot/wrappers/TensorWrapper.cpp', [(119,134),(150,152),(225,239)], 'buffer binding, id-only update, restore constructor'),
        (CPP/'runtime/backends/QnnGraphCommon.cpp', [(95,105),(122,128)], 'tensor creation then id metadata update'),
        (CPP/'runtime/QnnManager.cpp', [(329,356),(387,402),(589,611),(632,648)], 'allocate/map buffers, finalize without encoding refresh'),
        (CPP/'runtime/QnnManager.h', [(102,115)], 'getters return stored vectors'),
        (CPP/'aot/python/PyQnnManagerAdaptor.h', [(244,272),(302,326)], 'Compile returns binary; graph getters wrap manager vectors'),
        (CPP/'runtime/backends/QnnBackendCache.cpp', [(18,31),(150,184)], 'binary-info public graph I/O only'),
        (CPP/'runtime/QnnExecuTorchBackend.cpp', [(139,186)], 'runtime maps client buffers then graphExecute'),
        (Path('/home/moritz/opt/qairt/2.49.0.260730/include/QNN/QnnTypes.h'), [(510,518)], 'SDK public scale-offset definition, not an execution observation'),
    ]
    prior = EXP/'results/conv-history-native-fullchain-20260910/raw/request.json'
    old = {x['path']: x['sha256'] for x in json.loads(prior.read_text())['sources']}
    evidence = []
    for path, ranges, role in specs:
        item = identity(path)
        lines = path.read_text().splitlines()
        item.update(role=role, passages=[{'start_line':a,'end_line':b,'text':'\n'.join(lines[a-1:b])} for a,b in ranges])
        item['matches_prior_selected_python_pin'] = item['sha256'] == old[str(path)] if str(path) in old else None
        evidence.append(item)
    assert all(x['matches_prior_selected_python_pin'] is not False for x in evidence)
    same_cpp = []
    for rel in ('runtime/QnnManager.cpp','runtime/QnnExecuTorchBackend.cpp','aot/wrappers/TensorWrapper.cpp','aot/python/PyQnnManagerAdaptor.h'):
        a = CPP/rel; b = EXP/'.local/executorch-src/backends/qualcomm'/rel
        assert a.read_bytes() == b.read_bytes()
        same_cpp.append({'inspected': identity(a), 'other_checkout': identity(b), 'equal': True})
    save('source-evidence.json', {'sources':evidence,'prior_python_pin_source':identity(prior),'matching_cpp_checkouts':same_cpp,
         'limit':'Source binding only; selected Python pins agree with historical request. C++ checkout equality is not proof of exact loaded-binary provenance or internal finalized graph metadata.'})
    save('collection.json', {'status':'source_collection_complete','elapsed_seconds':time.monotonic()-start,
         'new_model_or_sdk_imports': [x for x in ('torch','executorch','onnxruntime') if x in sys.modules],
         'model_sessions_or_forwards':0,'SDK_calls':0,'tensor_bundle_deserializations':0,
         'metadata_json_recovery_count':1,'no_full_audit_or_sweep_reexecution':True,
         'execution_release_created':False})
    print('Source-only collection complete: two states and two immediate K-cache Cat paths; no runtime/model imports.')


if __name__ == '__main__':
    main()

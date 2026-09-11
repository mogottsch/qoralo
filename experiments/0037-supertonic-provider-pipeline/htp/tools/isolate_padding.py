#!/usr/bin/env python3
"""Isolate text/latent padding using preserved source-CPU probe activations."""
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import time
from check_padding import EXP, compare, pad, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if '.local' not in args.output.resolve().parts:
        p.error('private output only')
    resource.setrlimit(resource.RLIMIT_AS, (8 << 30, 8 << 30))
    signal.alarm(900)
    os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='4', MKL_NUM_THREADS='1')
    import numpy as np
    import onnx
    from onnx import helper
    from onnx.reference import ReferenceEvaluator
    import onnxruntime as ort
    args.output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    freeze = json.loads((EXP / 'protocol/freeze.json').read_text())
    baseline = json.loads((args.baseline / 'result.json').read_text())
    bundle = EXP / '.local/common/bundle'
    for name, expected in freeze['bundle_files_sha256'].items():
        if sha(bundle / name) != expected:
            raise ValueError('shared bundle changed')
    result = dict(status='started', numpy=np.__version__, onnxruntime=ort.__version__,
                  baseline_sha256=sha(args.baseline / 'result.json'), chunks=[], padding_metadata={})
    try:
        sessions = {}
        for name in ['text', 'vector', 'vocoder']:
            binding = freeze['cpu_original_model_bindings'][name]
            path = Path(binding['source'])
            if sha(path) != binding['sha256']:
                raise ValueError('source mismatch')
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 4
            opts.inter_op_num_threads = 1
            opts.log_severity_level = 3
            sessions[name] = ort.InferenceSession(str(path), opts, providers=['CPUExecutionProvider'])
            if name == 'text':
                continue
            model = onnx.load(path)
            producers = {o: n for n in model.graph.node for o in n.output}
            padding = []
            for node in model.graph.node:
                if node.op_type != 'Pad':
                    continue
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
                graph = helper.make_graph(nodes, 'constant_pad_recipe_only', [],
                    [helper.make_tensor_value_info(node.input[1], onnx.TensorProto.INT64, [6])], initializers)
                constant_model = helper.make_model(graph, opset_imports=list(model.opset_import))
                values = ReferenceEvaluator(constant_model).run(None, {})[0].tolist()
                padding.append(dict(name=node.name, input=node.input[0], mode=helper.get_attribute_value(next(a for a in node.attribute if a.name == 'mode')).decode(), pads=values))
            result['padding_metadata'][name] = padding
            del model
        ttl = np.fromfile(bundle / 'style_ttl.f32', '<f4').reshape(1, 50, 256)
        total = np.fromfile(bundle / 'total_steps.f32', '<f4')
        schedule = np.fromfile(bundle / 'current_steps.f32', '<f4')
        for row in baseline['chunks']:
            i, t, length = row['index'], row['text_extent'], row['native_latent']
            saved = np.load(args.baseline / f'chunk-{i:03d}.npz')
            folder = bundle / f'{i:03d}'
            ids = np.fromfile(folder / 'text_ids.i64', '<i8').reshape(1, t)
            mask = np.fromfile(folder / 'text_mask.f32', '<f4').reshape(1, 1, t)
            emb = sessions['text'].run(None, dict(text_ids=ids, text_mask=mask, style_ttl=ttl))[0]
            record = dict(index=i, text_extent=t, native_latent=length, cases={})
            for label, tb, lb in [('text_only', 320, length), ('latent_only', t, 512)]:
                latent = pad(saved['initial'], lb)
                steps = []
                for step in schedule:
                    latent = sessions['vector'].run(None, dict(noisy_latent=latent, text_emb=pad(emb, tb),
                        text_mask=pad(mask, tb), latent_mask=pad(np.ones((1, 1, length), np.float32), lb),
                        style_ttl=ttl, current_step=np.asarray([step], np.float32), total_step=total))[0]
                    if step == 0:
                        native_first = sessions['vector'].run(None, dict(noisy_latent=saved['initial'], text_emb=emb,
                            text_mask=mask, latent_mask=np.ones((1, 1, length), np.float32), style_ttl=ttl,
                            current_step=np.asarray([step], np.float32), total_step=total))[0]
                        steps.append(dict(step=0, **compare(native_first, latent[..., :length])))
                record['cases'][label] = dict(first_step=steps[0], final=compare(saved['native'], latent[..., :length]))
                np.save(args.output / f'chunk-{i:03d}-{label}.npy', latent)
            result['chunks'].append(record)
            print(json.dumps(record), flush=True)
        result['status'] = 'complete'
    except BaseException as e:
        result.update(status='error', error=str(e))
        raise
    finally:
        result.update(elapsed_seconds=time.monotonic()-start,
                      process_ru_maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        (args.output / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    main()

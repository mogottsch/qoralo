"""Opt-in capture hooks; dependencies are injected, no QNN imports or execution.

Tests inject mock classes. A future separately authorized adapter may inject the
real pass/backend classes and PyQnnTensorWrapper. Pre-Compile wrappers are NOT a
finalized/fused QNN graph. No methods here initialize a backend or compile/run it.
"""
from __future__ import annotations

from contextlib import contextmanager
import inspect
import math
import struct


QUANT_KEYS = ('quant_attrs', 'requantize', 'axis_order', 'qcom_tensor_name', 'quant_io')


def shape_dtype(value):
    if isinstance(value, (list, tuple)):
        return [shape_dtype(v) for v in value]
    if hasattr(value, 'shape') and hasattr(value, 'dtype'):
        return {'shape': [str(d) if not isinstance(d, int) else d for d in value.shape],
                'dtype': str(value.dtype)}
    return None


def small(value, depth=0):
    """Metadata only; no tensor storage reads. Missing representations are explicit."""
    if depth > 12:
        return {'unavailable': 'metadata nesting bound'}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else {'nonfinite': str(value)}
    if isinstance(value, dict):
        return {str(k): small(v, depth+1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [small(v, depth+1) for v in value]
    if hasattr(value, 'op') and hasattr(value, 'name'):
        return {'node': value.name}
    if hasattr(value, 'shape') and hasattr(value, 'dtype'):
        return {**shape_dtype(value), 'values': None, 'reason': 'tensor metadata only; no payload read'}
    return {'type': type(value).__name__, 'text': str(value)}


def graph_snapshot(program):
    gm = getattr(program, 'graph_module', program)
    rows = []
    for node in gm.graph.nodes:
        if len(rows) >= 512:
            raise ValueError('This capture hook is bounded to tiny graphs (512 nodes)')
        rows.append({'name': node.name, 'op': node.op, 'target': str(node.target),
                     'args': small(node.args), 'kwargs': small(node.kwargs),
                     'value_metadata': shape_dtype(node.meta.get('val')),
                     # Preserve every non-value metadata field, including actual QCOM key spellings.
                     'metadata': {str(k): small(v) for k, v in node.meta.items() if k != 'val'}})
    return {'nodes': rows, 'node_count': len(rows), 'tensor_payloads_read': False}


def tensor_encoding(wrapper, tensor_view):
    """Read real wrapper getters when supplied; tested with API-shaped mocks only.

GetEncodings exposes scale/offset/axis, not the full encoding-kind/bitwidth tag.
Do not fabricate those missing fields. QNN offsets are NOT PyTorch zero points.
"""
    view = tensor_view(wrapper)
    dtype = str(view.GetDataType())
    row = {'name': view.GetName(), 'shape': [int(x) for x in view.GetDims()],
           'qnn_dtype': dtype, 'encoding_kind': None, 'bitwidth': None,
           'getter_limit': 'binding exposes scale/offset/axis but not full quantization-kind/bitwidth',
           'encodings': None, 'axis': None}
    if 'FIXED_POINT' not in dtype:
        row['encoding_reason'] = 'not a fixed-point tensor; GetEncodings not called'
        return row
    try:
        enc = view.GetEncodings()
        if enc.data is None or len(enc.data) == 0:
            raise ValueError('GetEncodings returned no data')
        if len(enc.data) > 64:
            raise ValueError('encoding row bound exceeded (tiny per-tensor probe only)')
        rows = []
        for item in enc.data:
            scale = float(item['scale']); offset = int(item['offset'])
            if not math.isfinite(scale):
                raise ValueError('nonfinite encoding scale')
            rows.append({'scale': scale, 'scale_float32_le_hex': struct.pack('<f', scale).hex(),
                         'qnn_offset': offset})
        row.update(encodings=rows, axis=int(enc.axis))
    except Exception as error:
        row['encoding_reason'] = f'{type(error).__name__}: {error}'
    return row


class Hooks:
    def __init__(self, store):
        self.store = store
        self.counter = 0

    def emit(self, kind, payload):
        self.counter += 1
        self.store.json(f'taps/{self.counter:04d}-{kind}.json', payload)

    def graph(self, kind, program, **extra):
        try:
            payload = graph_snapshot(program)
        except Exception as error:
            payload = {'unavailable': f'{type(error).__name__}: {error}'}
        self.emit(kind, {**extra, **payload})

    def wrappers(self, py_wrappers, tensor_view):
        rows = []
        for py_wrapper in py_wrappers:
            try:
                op = py_wrapper.GetOpWrapper()
                row = {'name': op.GetName(), 'type': op.GetOpType(), 'package': op.GetPackageName()}
                for name, getter in (('inputs', op.GetInputTensors), ('outputs', op.GetOutputTensors)):
                    tensors = []
                    for wrapper in getter():
                        try:
                            tensors.append(tensor_encoding(wrapper, tensor_view))
                        except Exception as error:
                            tensors.append({'unavailable': f'{type(error).__name__}: {error}'})
                    row[name] = tensors
                rows.append(row)
            except Exception as error:
                rows.append({'unavailable': f'{type(error).__name__}: {error}'})
        self.emit('qnn-wrapper-encodings', {
            'phase': 'after _build_op_wrappers, before QnnManager.Compile',
            'actual_native_getters_verified': False,
            'verification_note': 'source preparation tested mock bindings only; execution adapter must separately record actual native invocation provenance',
            'finalized_or_fused_graph': False, 'operators': rows})

    def manager_io(self, manager):
        """Optional getter-only tap AFTER an authorized compile; never allocates/loads."""
        rows = []
        try:
            for name in manager.GetGraphNames():
                row = {'name': name}
                for key, getter in (('inputs', manager.GetGraphInputs), ('outputs', manager.GetGraphOutputs)):
                    try:
                        row[key] = [tensor_encoding(t, lambda x: x) for t in getter(name)]
                    except Exception as error:
                        row[key] = {'unavailable': f'{type(error).__name__}: {error}'}
                rows.append(row)
            self.emit('manager-io', {'graphs': rows, 'scope': 'manager-reported graph IO only; not internal finalized/fused graph'})
        except Exception as error:
            self.emit('manager-io', {'unavailable': f'{type(error).__name__}: {error}'})

    @contextmanager
    def install(self, pass_types, backend_class, tensor_view, visitor_class=None):
        """Process-local patches, always restored. Caller supplies reviewed classes.

Attach to each capture/preprocess pass __call__, NodeVisitor encoding selection,
and QnnBackend._build_op_wrappers (which precedes Compile in pinned source).
This does NOT call the passes, builder, compiler or runtime on entry.
"""
        restorations = []
        def patch(cls, name, replacement):
            own = name in cls.__dict__
            original = inspect.getattr_static(cls, name)
            restorations.append((cls, name, own, original))
            setattr(cls, name, replacement)
        try:
            for cls in dict.fromkeys(pass_types):
                original = cls.__call__
                def wrap_pass(instance, program, *args, _original=original, _cls=cls, **kwargs):
                    identity = f'{_cls.__module__}.{_cls.__name__}'
                    self.graph('before-pass', program, pass_type=identity)
                    try:
                        result = _original(instance, program, *args, **kwargs)
                    except BaseException as error:
                        self.graph('failed-pass', program, pass_type=identity,
                                   error={'type': type(error).__name__, 'message': str(error)})
                        raise
                    self.graph('after-pass', getattr(result, 'graph_module', program), pass_type=identity)
                    return result
                patch(cls, '__call__', wrap_pass)
            if visitor_class is not None:
                original_conf = visitor_class.get_quant_encoding_conf
                def encoding(instance, node, target, *args, **kwargs):
                    result = original_conf(instance, node, target, *args, **kwargs)
                    self.emit('selected-encoding', {'node': node.name, 'consumer': target.name,
                                                   'encoding_config_before_get_data_type': small(result),
                                                   'finalized_qnn_encoding': False})
                    return result
                patch(visitor_class, 'get_quant_encoding_conf', encoding)
            original_build = backend_class._build_op_wrappers
            def build(program, *args, **kwargs):
                self.graph('before-wrapper-build', program)
                try:
                    result = original_build(program, *args, **kwargs)
                except BaseException as error:
                    self.graph('failed-wrapper-build', program, error={'type': type(error).__name__, 'message': str(error)})
                    raise
                self.graph('after-wrapper-build', program)
                if isinstance(result, bytes):
                    self.emit('qnn-wrapper-encodings', {'unavailable': 'opaque context loader result; no wrapper encodings'})
                else:
                    self.wrappers(result, tensor_view)
                return result
            patch(backend_class, '_build_op_wrappers', staticmethod(build))
            yield self
        finally:
            for cls, name, own, original in reversed(restorations):
                if own:
                    setattr(cls, name, original)
                else:
                    delattr(cls, name)

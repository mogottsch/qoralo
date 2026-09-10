"""Native-aware extension of the immutable mock-tested probe hooks.

Importing this module does not import QNN. Introspection may import the native
binding but never constructs a manager/tensor wrapper or invokes backend APIs.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib
import math
from pathlib import Path
import struct

from conv_history_probe_hooks import Hooks


def file_identity(path):
    path = Path(path)
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def enum_table(enum_type):
    rows = []
    for name, value in enum_type.__members__.items():
        try:
            code = int(value)
        except (TypeError, ValueError):
            code = int(value.value)
        rows.append({'name': name, 'code': code, 'str': str(value), 'repr': repr(value)})
    return rows


def dtype_identity(raw, table):
    """Resolve native enums, integers, enum.value wrappers, or canonical names."""
    code = None
    for candidate in (raw, getattr(raw, 'value', None)):
        try:
            if candidate is not None and not (isinstance(candidate, float) and not candidate.is_integer()):
                code = int(candidate); break
        except (ValueError, TypeError, OverflowError):
            pass
    name = getattr(raw, 'name', None)
    names = {name, str(raw), str(raw).rsplit('.', 1)[-1]}
    match = next((row for row in table if code is not None and row['code'] == code), None)
    if match is None and code is None:
        match = next((row for row in table if row['name'] in names), None)
    return {'raw_str': str(raw), 'raw_type': type(raw).__name__, 'code': code if match is None else match['code'],
            'name': None if match is None else match['name'], 'resolved': match is not None,
            'fixed_point': None if match is None else 'FIXED_POINT' in match['name']}


def native_tensor_encoding(wrapper, view_factory, table):
    view = view_factory(wrapper)
    identity = dtype_identity(view.GetDataType(), table)
    row = {'name': str(view.GetName()), 'shape': [int(d) for d in view.GetDims()],
           'dtype': identity, 'encoding_kind': None, 'bitwidth': None, 'axis': None, 'encodings': None,
           'getter_limit': 'scale/offset/axis exposed; complete encoding-kind/bitwidth is not exposed'}
    if identity['fixed_point'] is not True:
        row['encoding_reason'] = ('unresolved actual dtype; no encoding inference' if not identity['resolved']
                                  else 'known non-fixed-point dtype; no quantization encoding requested')
        return row
    try:
        enc = view.GetEncodings()
        if enc.data is None or not 0 < len(enc.data) <= 64:
            raise ValueError('missing/oversized encoding array')
        values = []
        for item in enc.data:
            scale, offset = float(item['scale']), int(item['offset'])
            if not math.isfinite(scale) or scale <= 0:
                raise ValueError('invalid scale')
            values.append({'scale': scale, 'scale_float32_le_hex': struct.pack('<f', scale).hex(),
                           'qnn_offset': offset})
        row.update(axis=int(enc.axis), encodings=values)
    except Exception as error:
        row['encoding_reason'] = f'{type(error).__name__}: {error}'
    return row


@contextmanager
def deny_manager_creation(binding):
    original = binding.QnnManager
    counts = {'manager_constructor_attempts': 0}
    class ForbiddenManager:
        def __init__(self, *args, **kwargs):
            counts['manager_constructor_attempts'] += 1
            raise PermissionError('Backend manager construction forbidden in preparation')
    binding.QnnManager = ForbiddenManager
    try:
        yield counts
    finally:
        binding.QnnManager = original


def introspect_binding():
    """Caller sets QNN_SDK_ROOT before import to prevent SDK installer activation."""
    import os
    root = os.environ.get('QNN_SDK_ROOT')
    if not root or not Path(root).is_dir():
        raise RuntimeError('Existing QNN_SDK_ROOT required; never activate auto SDK install')
    binding = importlib.import_module('executorch.backends.qualcomm.python.PyQnnManagerAdaptor')
    manager_type = binding.QnnManager
    with deny_manager_creation(binding) as counts:
        classes = {}
        for name in ('PyQnnTensorWrapper', 'PyQnnOpWrapper', 'OpWrapper'):
            cls = getattr(binding, name)
            classes[name] = {method: getattr(cls, method).__doc__ for method in dir(cls)
                             if method.startswith('Get')}
        report = {'evidence_class': 'native_binding_interface_introspection_only',
                  'binding': file_identity(binding.__file__), 'dtype_table': enum_table(binding.Qnn_DataType_t),
                  'getter_docstrings': classes, 'manager_methods_seen_not_called': [n for n in dir(manager_type) if not n.startswith('_')],
                  'counts': counts, 'backend_init_compile_run': False,
                  'native_tensor_wrappers_constructed': False, 'actual_tensor_getters_invoked': False}
    return binding, report


class NativeHooks(Hooks):
    def __init__(self, store, table, provenance):
        super().__init__(store)
        self.table, self.provenance = table, provenance
        self.tap_errors = []
        self.wrapper_batches = 0
        self.tensor_rows = []

    def emit(self, kind, payload):
        if 'unavailable' in payload:
            self.tap_errors.append({'kind': kind, 'reason': payload['unavailable']})
        super().emit(kind, {'capture_provenance': self.provenance, **payload})

    def wrappers(self, py_wrappers, tensor_view):
        rows = []
        self.wrapper_batches += 1
        for item in py_wrappers:
            try:
                op = item.GetOpWrapper()
                row = {'name': op.GetName(), 'type': op.GetOpType(), 'package': op.GetPackageName()}
                for key, getter in (('inputs', op.GetInputTensors), ('outputs', op.GetOutputTensors)):
                    row[key] = []
                    for tensor in getter():
                        try:
                            record = native_tensor_encoding(tensor, tensor_view, self.table)
                        except Exception as error:
                            record = {'unavailable': f'{type(error).__name__}: {error}'}
                        row[key].append(record); self.tensor_rows.append(record)
                rows.append(row)
            except Exception as error:
                self.tap_errors.append({'kind': 'wrapper', 'reason': str(error)})
                rows.append({'unavailable': f'{type(error).__name__}: {error}'})
        self.emit('native-wrapper-encodings', {'phase': 'returned from _build_op_wrappers, before Compile',
                                              'operators': rows, 'finalized_or_fused_graph': False})

    def manager_io(self, manager):
        rows = []
        try:
            for name in manager.GetGraphNames():
                row = {'name': name}
                for key, getter in (('inputs', manager.GetGraphInputs), ('outputs', manager.GetGraphOutputs)):
                    try:
                        row[key] = [native_tensor_encoding(t, lambda x: x, self.table) for t in getter(name)]
                    except Exception as error:
                        row[key] = {'unavailable': f'{type(error).__name__}: {error}'}
                rows.append(row)
            self.emit('native-manager-io', {'graphs': rows, 'scope': 'manager IO only, not internal finalized graph'})
        except Exception as error:
            self.emit('native-manager-io', {'unavailable': f'{type(error).__name__}: {error}'})

    def summary(self):
        missing = [r for r in self.tensor_rows if 'unavailable' in r or not r.get('dtype', {}).get('resolved')
                   or (r.get('dtype', {}).get('fixed_point') and r.get('encodings') is None)]
        return {'wrapper_batches': self.wrapper_batches, 'tensor_getter_rows': len(self.tensor_rows),
                'missing_tensor_rows': missing, 'tap_errors': self.tap_errors,
                'wrapper_scale_offset_capture_complete': bool(self.tensor_rows) and not missing and not any(e['kind']=='wrapper' for e in self.tap_errors),
                'full_encoding_kind_known': False, 'internal_finalized_graph_known': False,
                'provenance': self.provenance}

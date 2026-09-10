import inspect,json,sys
from pathlib import Path
exp=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(exp/'tools'))
import conv_history_probe as probe
import conv_history_qnn_adapter as adapter
from conv_history_native_hooks import introspect_binding,deny_manager_creation,NativeHooks
binding,interface=introspect_binding()
store=probe.Evidence(Path(__file__).parent/'inspection')
with deny_manager_creation(binding) as counts:
    api=adapter.load_compiler_api()
    job=api.get_capture_program_passes()
    passes=[*job,api.FoldQDQ,api.InsertRequantize,api.InsertIOQDQ,api.LayoutTransform,api.FuseConsecutiveCast,api.FuseConsecutiveTranspose]
    hooks=NativeHooks(store,interface['dtype_table'],{'kind':'native_interface_install_only','binding':interface['binding']})
    with hooks.install(passes,api.QnnBackend,binding.PyQnnTensorWrapper,api.NodeVisitor):
        assert hooks.counter==0
    result={'evidence_class':'real_python_compile_api_import_and_hook_install_only',
            'binding':interface['binding'],'manager_constructor_attempts':counts['manager_constructor_attempts'],
            'passes_installed':[p.__name__ for p in dict.fromkeys(passes)],'pass_invocations':0,'wrapper_builds':0,
            'tensor_getters_invoked':0,'backend_init_compile_run':False,'hooks_restored':True,
            'lower_signature':str(inspect.signature(api.to_edge_transform_and_lower_to_qnn)),
            'htp_spec_signature':str(inspect.signature(api.generate_htp_compiler_spec))}
store.json('result.json',result)
print(json.dumps(result,indent=2))

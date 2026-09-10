from __future__ import annotations
import builtins
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import onnx_capacity as tool
import onnx
from onnx import helper, TensorProto as TP


def toy_component(component, t=2048, l=2048):
    ins, outs = tool.io_shapes(component,t,l)
    inputs = [helper.make_tensor_value_info(n, TP.INT64 if n=='text_ids' else TP.FLOAT,
                [f'dim_{n}_{i}' for i in range(len(s))]) for n,s in ins.items()]
    outputs = [helper.make_tensor_value_info(n,TP.FLOAT,[f'out_{i}' for i in range(len(s))]) for n,s in outs.items()]
    name, shape = next(iter(outs.items()))
    # Declares output geometry, never allocates/evaluates the large tensor.
    size = helper.make_tensor('output_dims',TP.INT64,[len(shape)],shape)
    initializers=[size]
    if component=='vector':initializers.append(helper.make_tensor(tool.INCREMENTS,TP.INT64,[1,1000,1],list(range(1000))))
    graph = helper.make_graph([helper.make_node('ConstantOfShape',['output_dims'],[name])],component,inputs,outputs,initializers)
    return helper.make_model(graph,opset_imports=[helper.make_opsetid('',19)])


def toy_softplus():
    x=helper.make_tensor_value_info(tool.SOFTPLUS_INPUT,TP.FLOAT,[2,256])
    y=helper.make_tensor_value_info('y',TP.FLOAT,[2,256])
    graph=helper.make_graph([
        helper.make_node('Softplus',[x.name],[tool.SOFTPLUS_OUTPUT],name=tool.SOFTPLUS),
        helper.make_node('Tanh',[tool.SOFTPLUS_OUTPUT],['y'],name=tool.SOFTPLUS_CONSUMER),
    ],'toy',[x],[y])
    return helper.make_model(graph,opset_imports=[helper.make_opsetid('',19)])


class CapacityTests(unittest.TestCase):
    def test_target_matches_official_inventory(self):
        target=json.loads(tool.TARGET.read_text());repo=ROOT.parents[3]
        inventory=json.loads((repo/'experiments/0011-supertonic-official-fp32-phone-comparison/results/source-inventory.json').read_text())
        records={Path(r['path']).name:r for r in inventory['assets']}
        self.assertEqual(inventory['revision'],target['source_revision'])
        for source in target['sources'].values():
            self.assertEqual(records[source['filename']]['sha256'],source['sha256'])
            self.assertEqual(records[source['filename']]['bytes'],source['bytes'])

    def test_capacity_arithmetic(self):
        self.assertEqual([1,6291456],tool.io_shapes('vocoder',2048,2048)[1]['wav_tts'])
        self.assertAlmostEqual(142.6634013605442,2048*3072/44100)
        self.assertEqual(1723,math.ceil(120*44100/3072))
        self.assertLess(1024*3072/44100,120)

    def test_four_synthetic_abi_specializations_no_execution(self):
        for component in ('duration','text','vector','vocoder'):
            length=1000 if component=='vector' else 2048
            original=toy_component(component,t=length,l=length);before=original.SerializeToString()
            result=tool.specialize(original,component,length,length)
            ins,outs=tool.io_shapes(component,length,length)
            self.assertEqual(ins,{v.name:tool.value_info(v)['shape'] for v in result.graph.input})
            self.assertEqual(outs,{v.name:tool.value_info(v)['shape'] for v in result.graph.output})
            self.assertEqual(before,original.SerializeToString())
            self.assertEqual([v.SerializeToString() for v in original.graph.initializer],[v.SerializeToString() for v in result.graph.initializer])

    def test_original_vector_table_blocks_both_target_and_1024_intermediate(self):
        for t,l in ((2048,2048),(1024,1024),(1001,1000),(1000,1001)):
            model=toy_component('vector',t=t,l=l);before=model.SerializeToString()
            with self.assertRaisesRegex(ValueError,'only1000'):tool.specialize(model,'vector',t,l)
            self.assertEqual(before,model.SerializeToString())
        model=toy_component('vector',t=1000,l=1000);tool.require_position_capacity(model,1000,1000)
        model.graph.initializer[-1].dims[1]=2048
        with self.assertRaisesRegex(ValueError,'unrecognized'):tool.require_position_capacity(model,2048,2048)

    def test_saved_vector_table_and_two_mask_axis_paths(self):
        meta=json.loads((ROOT/'results/host-preparation-20260910/raw/inspect-vector-01/data/metadata.json').read_text())
        initial={x['name']:x for x in meta['initializers']};nodes={n['name']:n for n in meta['nodes']}
        self.assertEqual([1,1000,1],initial[tool.INCREMENTS]['shape']);self.assertEqual(7,initial[tool.INCREMENTS]['dtype'])
        uses=[n for n in meta['nodes'] if tool.INCREMENTS in n['inputs']]
        self.assertEqual(2,len(uses));self.assertTrue(all(n['op']=='Slice' for n in uses))
        for node in uses:
            self.assertEqual([0],initial[node['inputs'][1]]['small_values'])
            self.assertEqual([1],initial[node['inputs'][3]]['small_values']);self.assertEqual([1],initial[node['inputs'][4]]['small_values'])
        for length in (238,1000,1024,2048):self.assertEqual(min(length,1000),len(list(range(1000))[:length]))
        self.assertEqual(['batch_size',144,'latent_length'],meta['inputs'][0]['shape'])
        self.assertEqual(['batch_size',256,'text_length'],meta['inputs'][1]['shape'])
        trig=[n for n in meta['nodes'] if n['op'] in ('Sin','Cos') and '/attn/' in n['name']]
        self.assertEqual(4,len(trig))
        for n in trig:self.assertEqual(8,len([u for u in meta['nodes'] if n['outputs'][0] in u['inputs']]))

    def test_exact_arange_and_mask_normalized_position_semantics(self):
        meta=json.loads((ROOT/'results/host-preparation-20260910/raw/inspect-vector-positional-02/data/metadata.json').read_text())
        initial={x['name']:x for x in meta['initializers']}
        self.assertEqual(list(range(1000)),initial[tool.INCREMENTS]['small_values'])
        theta=initial[tool.THETA]['small_values'];self.assertEqual(32,len(theta))
        for j,value in enumerate(theta):self.assertAlmostEqual(value/(10*10000**(-j/32)),1.,places=6)
        # Synthetic arithmetic only: a larger integer-table prefix is identical;
        # dividing by capacity instead of active length would change phases.
        original=list(range(1000));hypothesis=list(range(2048))
        self.assertEqual(original,hypothesis[:1000])
        for active in (238,700,1000):
            for index in (0,10,active-1):
                self.assertEqual(original[index]/active*theta[0],hypothesis[index]/active*theta[0])
        self.assertNotEqual(10/238*theta[0],10/2048*theta[0])
        mask_sums=[n for n in meta['nodes'] if n['name'].endswith('/attn/ReduceSum') or n['name'].endswith('/attn/ReduceSum_1')]
        self.assertEqual(2,len(mask_sums))
        self.assertTrue(all(initial[n['inputs'][1]]['small_values']==[1,2] for n in mask_sums))

    def test_opaque_and_external_position_tables_rejected(self):
        model=toy_component('vector',1000,1000);model.graph.initializer[-1].int64_data[-1]=-1
        with self.assertRaisesRegex(ValueError,'opaque'):tool.require_position_capacity(model,1000,1000)
        model=toy_component('vector',1000,1000);table=model.graph.initializer[-1]
        table.data_location=TP.EXTERNAL;table.external_data.add(key='location',value='/not/read/positions')
        with self.assertRaisesRegex(ValueError,'external'):tool.require_position_capacity(model,1000,1000)

    def test_input_name_order_rank_and_dtype_fail_closed(self):
        for mutation in ('name','order','dtype','rank'):
            model=toy_component('duration')
            if mutation=='name':model.graph.input[0].name='not_text'
            elif mutation=='order':model.graph.input.reverse()
            elif mutation=='dtype':model.graph.input[0].type.tensor_type.elem_type=TP.FLOAT
            else:model.graph.input[0].type.tensor_type.shape.dim.add().dim_value=1
            with self.assertRaises(ValueError):tool.specialize(model,'duration',2048,2048)

    def test_conflicting_internal_fixed_shape_is_not_silently_rewritten(self):
        model=toy_component('text',t=239,l=238)
        with self.assertRaises(Exception):tool.specialize(model,'text',2048,2048)

    def test_external_payload_never_decoded_and_transform_rejects_it(self):
        model=toy_component('duration');tensor=model.graph.initializer[0]
        tensor.data_location=TP.EXTERNAL;tensor.external_data.add(key='location',value='/forbidden/weights.bin')
        self.assertTrue(tool.tensor_info(tensor)['external']);self.assertIsNone(tool.tensor_info(tensor)['small_values'])
        with self.assertRaisesRegex(ValueError,'external'):tool.specialize(model,'duration',2048,2048)

    def test_large_and_float_initializers_are_metadata_only(self):
        floating=helper.make_tensor('learned_scalar',TP.FLOAT,[1],[7.0])
        self.assertIsNone(tool.tensor_info(floating)['small_values'])
        small=helper.make_tensor('dims',TP.INT64,[2],[144,3072])
        self.assertEqual([144,3072],tool.tensor_info(small)['small_values'])
        large=helper.make_tensor('positions',TP.INT64,[33],list(range(33)))
        self.assertIsNone(tool.tensor_info(large)['small_values'])
        self.assertEqual([7.0],tool.tensor_info(floating,constant_attribute=True)['small_values'])

    def test_metadata_inspection_preserves_protobuf(self):
        model=toy_component('text');before=model.SerializeToString();meta=tool.inspect_graph(model)
        self.assertEqual(before,model.SerializeToString());self.assertIsNone(meta['larger_shape_support'])
        self.assertEqual(1,meta['operator_counts']['ConstantOfShape'])

    def test_softplus_seven_node_identity_preserves_original(self):
        model=toy_softplus();before=model.SerializeToString();result=tool.stable_softplus(model)
        self.assertEqual(before,model.SerializeToString());self.assertEqual(8,len(result.graph.node))
        self.assertEqual(['Relu','Abs','Neg','Exp','Add','Log','Add','Tanh'],[n.op_type for n in result.graph.node])
        self.assertEqual(1,len(result.graph.initializer));self.assertEqual(result.SerializeToString(),tool.stable_softplus(model).SerializeToString())
        self.assertEqual(model.graph.node[-1].SerializeToString(),result.graph.node[-1].SerializeToString())

    def test_softplus_scalar_stability_not_model_forward(self):
        for x in (-1000.,-30.,-1.,0.,1.,30.,1000.):
            transformed=max(x,0.)+math.log(1+math.exp(-abs(x)))
            expected=max(x,0.)+math.log1p(math.exp(-abs(x)))
            self.assertAlmostEqual(transformed,expected,places=12)
            self.assertTrue(math.isfinite(transformed))

    def test_softplus_target_shape_opset_consumer_and_collision_gates(self):
        for change in ('shape','opset','consumer','collision','missing'):
            model=toy_softplus()
            if change=='shape':model.graph.input[0].type.tensor_type.shape.dim[0].dim_value=1
            elif change=='opset':model.opset_import[0].version=18
            elif change=='consumer':model.graph.node[1].name='unexpected'
            elif change=='collision':model.graph.initializer.append(helper.make_tensor(tool.SOFTPLUS+'/stable/one',TP.FLOAT,[],[1.]))
            else:model.graph.node[0].name='other'
            with self.assertRaises(ValueError):tool.stable_softplus(model)

    def test_release_is_exact_and_output_source_target_helper_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);release=root/'release.json';out=root/'out';source={'sha256':'s'}
            data={'approved':True,'permission':'one_source_derivative_only_no_execution','component':'duration','source_sha256':'s','target_sha256':tool.sha(tool.TARGET),'helper_sha256':tool.sha(tool.__file__),'output_dir':str(out.resolve())}
            release.write_text(json.dumps(data));self.assertEqual(data,tool.validate_release(release,'duration',source,out))
            for key in data:
                bad=dict(data);bad[key]=None;release.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):tool.validate_release(release,'duration',source,out)

    def test_no_release_cli_rejects_before_source_access_or_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary)/'out'
            result=subprocess.run([sys.executable,str(ROOT/'tools/onnx_capacity.py'),'derive','--component','duration','--source','/must/not/read/model.onnx','--output-dir',str(out)],capture_output=True,text=True)
            self.assertNotEqual(0,result.returncode);self.assertIn('requires a separately approved',result.stderr);self.assertFalse(out.exists())

    def test_transforms_do_not_import_model_runtimes(self):
        real_import=builtins.__import__
        def denied(name,*args,**kwargs):
            if name.split('.')[0] in ('torch','onnxruntime','executorch'):raise AssertionError('model runtime import')
            return real_import(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=denied):
            tool.inspect_graph(toy_component('duration'));tool.specialize(toy_component('duration'),'duration',2048,2048);tool.stable_softplus(toy_softplus())
        self.assertFalse(any(name in sys.modules for name in ('torch','onnxruntime','executorch')))


if __name__=='__main__':unittest.main()

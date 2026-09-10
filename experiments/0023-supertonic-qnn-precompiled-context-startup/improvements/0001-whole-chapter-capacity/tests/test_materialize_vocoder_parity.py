import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import onnx
from onnx import helper as h,TensorProto as T

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import materialize_vocoder_parity as parity


def constant(name,values,shape=None):
    return h.make_node('Constant',[],[name],name=name,value=h.make_tensor('',T.INT64,shape or [len(values)],values))


def fixture():
    nodes=[constant('feature_shape',[1,512,12288]),h.make_node('ConstantOfShape',['feature_shape'],['feature'],name='feature')];initializers=[]
    for i,target in zip((1,4),parity.TARGETS):
        base=f'/decoder/convnext.{i}/dwconv';w=f'tts.ae.decoder.convnext.{i}.dwconv.net.weight';b=f'tts.ae.decoder.convnext.{i}.dwconv.net.bias'
        nodes += [constant(base+'/pad_controls',[0,0,12,0,0,0]),h.make_node('Pad',['feature',base+'/pad_controls'],[base+'/Pad_output_0'],name=base+'/Pad',mode='edge'),h.make_node('Conv',[base+'/Pad_output_0',w,b],[target+'_output_0'],name=target,**parity.EXPECTED_ATTRS),h.make_node('Identity',[target+'_output_0'],[base+'/consumer'],name=base+'/consumer')]
        initializers += [h.make_tensor(w,T.FLOAT,[512,1,7],[0.5]*3584),h.make_tensor(b,T.FLOAT,[512],[0.25]*512)]
    nodes += [constant('wav_shape',[1,6291456]),h.make_node('ConstantOfShape',['wav_shape'],['wav_tts'],name='wav')]
    return h.make_model(h.make_graph(nodes,'synthetic-no-forward',[h.make_tensor_value_info('latent',T.FLOAT,[1,144,2048])],[h.make_tensor_value_info('wav_tts',T.FLOAT,[1,6291456])],initializers),opset_imports=[h.make_opsetid('',19)])


class ParityMaterializationTests(unittest.TestCase):
    def test_exact_two_site_transform_and_shape_proof_source_unchanged(self):
        source=fixture();original=source.SerializeToString();derived,proof=parity.transform(source);delta=parity.structural_delta(source,derived)
        self.assertEqual(original,source.SerializeToString());self.assertEqual(len(source.graph.node)+14,len(derived.graph.node));self.assertEqual(len(source.graph.initializer)+7,len(derived.graph.initializer))
        self.assertTrue(delta['all_original_initializer_bytes_and_order_unchanged']);self.assertEqual(2,len(proof['isolated_shape_proofs']))
        self.assertEqual(14,len(derived.graph.value_info)-len(source.graph.value_info));onnx.checker.check_model(derived,full_check=True)

    def test_each_branch_is_batch1_nondilated_and_original_consumers_preserved(self):
        source=fixture();derived,_=parity.transform(source);new={n.name:n for n in derived.graph.node}
        for n in source.graph.node:
            if n.name not in parity.TARGETS:self.assertEqual(n.SerializeToString(),new[n.name].SerializeToString())
        for target in parity.TARGETS:
            for branch in ('even','odd'):
                node=new[target+'/parity_'+branch+'_conv'];self.assertEqual([1],parity.attributes(node)['dilations']);self.assertEqual(512,parity.attributes(node)['group'])
                info=next(v for v in derived.graph.value_info if v.name==node.output[0])
                self.assertEqual([1,512,6144],[d.dim_value for d in info.type.tensor_type.shape.dim])
            self.assertEqual([target+'_output_0'],list(new[target+'/parity_restore'].output))

    def test_source_gates_fail_closed(self):
        for mutation in ('padding','dilation','weights','opset','IO','external'):
            model=fixture()
            if mutation=='padding':next(n for n in model.graph.node if n.name.endswith('/pad_controls')).attribute[0].t.int64_data[2]=6
            elif mutation=='dilation':next(a for n in model.graph.node if n.name==parity.TARGETS[0] for a in n.attribute if a.name=='dilations').ints[0]=4
            elif mutation=='weights':model.graph.initializer[0].dims[0]=256
            elif mutation=='opset':model.opset_import[0].version=18
            elif mutation=='IO':model.graph.input[0].type.tensor_type.shape.dim[2].dim_value=1024
            else:model.graph.initializer[0].data_location=T.EXTERNAL
            with self.assertRaises(ValueError):parity.transform(model)

    def test_namespace_and_second_transform_rejected(self):
        model=fixture();model.graph.initializer.append(h.make_tensor(parity.PREFIX+'collision',T.INT64,[1],[0]))
        with self.assertRaises(ValueError):parity.transform(model)
        derived,_=parity.transform(fixture())
        with self.assertRaises(ValueError):parity.transform(derived)

    def test_exhaustive_delta_rejects_nonpermitted_mutations(self):
        source=fixture();derived,_=parity.transform(source)
        for mutation in ('weight','other_node','public_IO','model_metadata','control','value_info','replacement'):
            bad=copy.deepcopy(derived)
            if mutation=='weight':bad.graph.initializer[0].float_data[0]=7.0
            elif mutation=='other_node':next(n for n in bad.graph.node if n.name.endswith('/Pad')).attribute[0].s=b'constant'
            elif mutation=='public_IO':bad.graph.output[0].name='changed'
            elif mutation=='model_metadata':bad.doc_string='changed'
            elif mutation=='control':bad.graph.initializer[-1].int64_data[2]=17
            elif mutation=='value_info':bad.graph.value_info[0].type.tensor_type.shape.dim[-1].dim_value=17
            else:next(n for n in bad.graph.node if n.name.endswith('/parity_concat')).attribute[0].i=2
            with self.assertRaises(ValueError):parity.structural_delta(source,bad)

    def test_actual_pad_builder_integer_algebra_and_oversize_refusal(self):
        nodes=[constant('len',[4]),h.make_node('ConstantOfShape',['len'],['zeros'],name='zeros',value=h.make_tensor('',T.INT64,[1],[0])),constant('pad',[12,0]),h.make_node('Concat',['pad','zeros'],['joined'],axis=0),constant('shape',[-1,2]),h.make_node('Reshape',['joined','shape'],['matrix']),constant('start',[-1]),constant('end',[-9223372036854775807]),constant('axis',[0]),constant('step',[-1]),h.make_node('Slice',['matrix','start','end','axis','step'],['reverse']),h.make_node('Transpose',['reverse'],['transposed'],perm=[1,0]),constant('flatshape',[-1]),h.make_node('Reshape',['transposed','flatshape'],['pads']),h.make_node('Cast',['pads'],['cast'],to=T.INT64)]
        model=h.make_model(h.make_graph(nodes,'integer-controls',[],[]));self.assertEqual([0,0,12,0,0,0],parity.pad_value(model,'cast'))
        model.graph.node[0].attribute[0].t.int64_data[0]=100
        with self.assertRaises(ValueError):parity.pad_value(model,'cast')

    def test_release_rejected_before_model_load(self):
        with tempfile.TemporaryDirectory() as temp:
            command=[sys.executable,str(ROOT/'tools/materialize_vocoder_parity.py'),'--source','DOES_NOT_EXIST','--output-dir',str(Path(temp)/'out')]
            plan=subprocess.run(command,capture_output=True,text=True);self.assertEqual(0,plan.returncode);self.assertIn('PLAN_ONLY_NO_MODEL_PARSE',plan.stdout)
            denied=subprocess.run(command+['--execute'],capture_output=True,text=True);self.assertNotEqual(0,denied.returncode);self.assertIn('separate exact release',denied.stderr)
            self.assertFalse((Path(temp)/'out').exists())
        self.assertNotIn('onnxruntime',sys.modules);self.assertNotIn('torch',sys.modules)


if __name__=='__main__':unittest.main()

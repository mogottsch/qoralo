#!/usr/bin/env python3
"""Compile the precision-gated AR pair with the unchanged accepted HTP recipe."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import resource
import sys
import time
from unittest.mock import patch

from prepare_value_precision_derivative import digest
from value_precision_path import parse_dlc_csv

HERE = Path(__file__).resolve()
TRACK, EXP = HERE.parents[1], HERE.parents[3]
LEGACY = EXP/'tools/compile_qairt_cache_aligned.py'
LEGACY_SHA = 'cf997a64ec255d53b51f4b26e42ff426e8a06acce1c8626077be79698272a67b'


def pair_contract(graphs):
    expected = {f"{'past' if layer in (4,9,14) else 'swa'}_{kind}_{layer}_h0_out"
                for layer in range(15) for kind in ('key','value')}
    names = set(graphs[1]['io']['output']) - {'logits'}
    other_names = set(graphs[128]['io']['output']) - {'logits'}
    if names != expected or other_names != expected:
        raise ValueError('expected the exact30 global/SWA cache outputs in both ARs')
    for output in sorted(names):
        inp = output.removesuffix('_out') + '_in'
        entries = [graphs[ar]['io'][role][name] for ar in (1,128) for role,name in (('input',inp),('output',output))]
        def signature(e):
            return (e['datatype'], None if e['datatype'] == 'Float_16' else e['encoding'])
        if any(signature(e) != signature(entries[0]) for e in entries):
            raise ValueError('active four-way cache signature mismatch: '+output)
    return {'cache_count':30, 'active_four_way_contract_passed':True,
            'float_annotation_semantics':'Float16 storage has no active integer scale/offset; raw annotations remain retained'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--ar1-validation', type=Path, required=True)
    p.add_argument('--ar128-validation', type=Path, required=True)
    p.add_argument('--run-dir', type=Path, required=True)
    args = p.parse_args()
    run = args.run_dir.resolve()
    run.mkdir(parents=True,exist_ok=False,mode=0o700)
    start = time.monotonic()
    record = {'classification':'started', 'phase':'verifying_paired_inputs', 'inference':False, 'phone_access':False,
              'accepted_recipe_sha256':LEGACY_SHA, 'wrapper_sha256':digest(HERE)}
    def retain():
        record['elapsed_seconds'] = time.monotonic()-start
        record['ru_maxrss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        (run/'result.json').write_text(json.dumps(record,indent=2)+'\n')
    retain()
    try:
        assert digest(LEGACY) == LEGACY_SHA
        paths, evidence, graphs = {}, {}, {}
        for ar, path in ((1,args.ar1_validation),(128,args.ar128_validation)):
            d=json.loads(path.read_text())
            assert d['passed'] and d['ar']==ar and d['core_gate']['passed'] and d['coupled_exit_gate']['passed']
            assert d['coupled_exit_gate']['head_group_count']==7
            dlc=Path(d['dlc']['path']);assert dlc.stat().st_size==d['dlc']['bytes'] and digest(dlc)==d['dlc']['sha256']
            csv=path.parent/'inspection-01/model.csv';assert digest(csv)==d['csv_sha256']
            graphs[ar]=parse_dlc_csv(csv)
            paths[ar]=dlc;evidence[ar]={'validation_path':str(path),'validation_sha256':digest(path),'dlc':d['dlc']}
        record['pair_contract']=pair_contract(graphs)
        record['inputs']=evidence
        record['substitutions']=['DLC paths/hashes','fresh context output directory']
        record['compile_options_changed']=False
        retain()
        record['phase']='native_setup'
        retain()
        sys.path.insert(0,str(EXP/'tools'))
        spec=importlib.util.spec_from_file_location('accepted_value_path_recipe',LEGACY)
        legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
        legacy.COMPILE_CACHE=run/'context-cache'
        legacy.EXPECTED_DLCS={ar:evidence[ar]['dlc']['sha256'] for ar in (1,128)}
        legacy.find_dlc=lambda ar: paths[ar]
        from qairt.gen_ai_api.gen_ai_builder_factory import GenAIBuilderFactory
        create=GenAIBuilderFactory.create
        calls=0
        def observe_create(*pos,**kw):
            builder=create(*pos,**kw)
            original=builder.compile
            def observe(models,config):
                nonlocal calls
                calls+=1
                assert calls==1
                names=[m.name for m in models]
                assert names==[f'ar{ar}_cl4096_1_of_1' for ar in (1,128)]
                assert [g.name for g in config.graph_custom_configs]==names
                assert [Path(m.module.path).resolve() for m in models]==[paths[ar].resolve() for ar in (1,128)]
                assert builder._prepare_embedding_lut is False
                record['compiler_config']=config.model_dump(mode='json')
                record['phase']='native_context_compile'
                retain()
                compiled=original(models,config)
                binary=Path(compiled.module.path)
                record['context']={'path':str(binary),'bytes':binary.stat().st_size,'sha256':digest(binary),'name':compiled.name}
                record['compile_calls']=calls
                record['classification']='paired_value_precision_context_compiled_metadata_gate_pending'
                record['phase']='complete'
                retain()
                return compiled
            builder.compile=observe
            return builder
        with patch.object(GenAIBuilderFactory,'create',side_effect=observe_create):
            legacy.main()
        return 0
    except Exception as e:
        record['classification']='paired_value_precision_preflight_error' if record['phase']=='verifying_paired_inputs' else 'paired_value_precision_compile_error'
        record['error']={'type':type(e).__name__,'message':str(e)}
        retain()
        raise


if __name__=='__main__':
    raise SystemExit(main())

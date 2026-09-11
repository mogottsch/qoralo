#!/usr/bin/env python3
"""Prepare a private observation-only Genie source build; never loads a model.

The stock tokenQuery shortcut is not used: its LUT branch omits this model's
per-layer embedding vector. Keep the original text-query path and sampler.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import os

TRACK=Path(__file__).resolve().parents[1]
SDK=Path('/home/moritz/opt/qairt/2.49.40.260810')
BASIC_SHA='a9a91951e2ad13101291899589d328f61e15e71bde8a6c7cd3314727d9c0e71b'
ANDROID_MK_SHA='dae4095715c638de12f12f820182b03476232e9703580f98784ecf87ef22da5b'
EXTRA_CPP=('src/qualla/encoders/modalityEncoder.cpp',
           'src/qualla/encoders/audio-encoders/audioEncoder.cpp',
           'src/qualla/decoders/image-decoders/imageDecoder.cpp')
NEEDLE='    tokens[0] = _last_tok = sampler.process(logits);'
OBSERVER='\n    gemma_trace_selected_id(_n_generated, _last_tok, _ctx->is_eos(_last_tok), _n_past);'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_source(source):
    if hashlib.sha256(source.encode()).hexdigest()!=BASIC_SHA:
        raise ValueError('pinned BasicDialog source changed')
    if source.count(NEEDLE)!=3:
        raise ValueError('expected three non-batch real sampler sites')
    return '#include "selected_id_trace.hpp"\n'+source.replace(NEEDLE,NEEDLE+OBSERVER)


def patch_android_recipe(source):
    """Complete supplied Android file inventory; no source implementation edits."""
    if hashlib.sha256(source.encode()).hexdigest()!=ANDROID_MK_SHA:
        raise ValueError('pinned Android recipe changed')
    include_anchor='PACKAGE_C_INCLUDES += -I $(LOCAL_PATH)/../src/qualla/engines/qnn-htp\n'
    added_include='PACKAGE_C_INCLUDES += -I $(LOCAL_PATH)/../src/qualla/engines\n'
    source_anchor='LOCAL_MODULE                   := libGenie\n'
    added_sources=''.join('MY_SRC_FILES                   += $(LOCAL_PATH)/../'+p+'\n' for p in EXTRA_CPP)
    if source.count(include_anchor)!=1 or source.count(source_anchor)!=1:
        raise ValueError('Android recipe anchors differ')
    patched=source.replace(include_anchor,include_anchor+added_include).replace(source_anchor,added_sources+source_anchor)
    assert patched.replace(added_include,'').replace(added_sources,'')==source
    return patched


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir',required=True,type=Path)
    p.add_argument('--complete-android-recipe',action='store_true')
    args=p.parse_args();root=args.run_dir.resolve()
    if not root.is_relative_to((TRACK/'.local/selected-id-trace-runs').resolve()):
        p.error('fresh owned private trace run required')
    os.umask(0o077);root.mkdir(parents=True,exist_ok=False)
    original=SDK/'examples/Genie/Genie'
    src=root/'sdk-source/examples/Genie/Genie'
    source=(original/'src/qualla/dialogs/basic.cpp').read_text()
    patched=patch_source(source)
    shutil.copytree(original,src)
    (root/'sdk-source/include').symlink_to(SDK/'include',target_is_directory=True)
    target=src/'src/qualla/dialogs/basic.cpp';target.write_text(patched)
    shutil.copyfile(TRACK/'tools/selected_id_trace.hpp',target.with_name('selected_id_trace.hpp'))
    if args.complete_android_recipe:
        (src/'make/Android.mk').write_text(patch_android_recipe((original/'make/Android.mk').read_text()))
    changes=[];unchanged=0
    for path in sorted(original.rglob('*')):
        if not path.is_file():continue
        rel=path.relative_to(original);copy=src/rel
        if sha(path)!=sha(copy):changes.append(str(rel))
        else:unchanged+=1
    assert changes==(['make/Android.mk','src/qualla/dialogs/basic.cpp'] if args.complete_android_recipe else ['src/qualla/dialogs/basic.cpp'])
    assert patched.removeprefix('#include "selected_id_trace.hpp"\n').replace(NEEDLE+OBSERVER,NEEDLE)==source
    result={'classification':'private_observation_source_preparation_only','source_root':str(src),
        'original_basic_sha256':BASIC_SHA,'patched_basic_sha256':sha(target),
        'observer_sha256':sha(target.with_name('selected_id_trace.hpp')),
        'changed_existing_files':changes,'unchanged_existing_files':unchanged,
        'android_recipe_completed':args.complete_android_recipe,
        'original_android_recipe_sha256':ANDROID_MK_SHA,
        'android_recipe_sha256':sha(src/'make/Android.mk'),
        'sampler_stop_or_input_logic_changed':False,'SDK_originals_modified':False,
        'neural_model_loaded':False,'phone_access':False,
        'API_shortcut_rejected':'Stock Dialog::tokenQuery LUT branch passes an empty per-layer vector and null per-layer callback; cannot assert parity with the used Gemma text-query path.',
        'trace_boundary':'Actual ID after sampler return, before stop/text filtering. Configured EOS membership is an observation, not an internal stop-decision enum. Later selected-ID records prove subsequent sampling; absence of later records is not a guessed stop reason.',
        'build_boundary':'Instrumented source-built runtime is a new runtime artifact. Model/context, policy and text-query semantics stay fixed; binary/output equivalence to the supplied commercial runtime is not assumed.'}
    (root/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    shutil.copyfile(Path(__file__),root/'prepare-source.py')
    print(json.dumps(result))


if __name__=='__main__':main()

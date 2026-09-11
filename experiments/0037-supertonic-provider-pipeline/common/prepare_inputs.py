#!/usr/bin/env python3
"""Pin and run official v1.3.1 frontend only; no model/session/inference calls.

Run with exp0007's installed supertonic v1.3.1 Python environment. All content
and stochastic arrays are private. Public manifest contains only identities.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

ROOT=Path(__file__).resolve().parents[3]
EXP=ROOT/'experiments/0037-supertonic-provider-pipeline'
ASSETS=ROOT/'experiments/0007-mobile-podcast-preview-bakeoff/artifacts/supertonic-3/snapshot'
REFERENCE=ROOT/'podcast-app/.local/long-tts-reference/sandyford-chapter-5-cbfd5bbef581/narration.txt'
REF_SHA='cbfd5bbef581f0e793b86a568f8d4aa87fe857f413e5c2ea4780b558fc71600b'
HF_REV='724fb5abbf5502583fb520898d45929e62f02c0b'


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    import numpy as np
    import supertonic
    from supertonic import config,core,utils,pipeline,loader
    origin=EXP/'.local/upstream/source-manifest.json';source=json.loads(origin.read_text())
    for record in source['files']:
        path=Path(supertonic.__file__).parent/record['file']
        if sha(path.read_bytes())!=record['sha256']:raise ValueError('official source drift')
    if config.MODEL_CONFIGS['supertonic-3']['revision']!=HF_REV:raise ValueError('weight-revision mismatch')
    raw=REFERENCE.read_bytes()
    if sha(raw)!=REF_SHA or len(raw)!=3190:raise ValueError('reference changed')
    text=raw.decode('utf-8')
    processor=core.UnicodeProcessor(str(ASSETS/'onnx/unicode_indexer.json'))
    valid,unsupported=processor.validate_text(text)
    if not valid:raise ValueError('official frontend rejects reference')
    # Exact ordering from TTS.synthesize: validate only, chunk RAW, preprocess each.
    chunks=utils.chunk_text(text,config.DEFAULT_MAX_CHUNK_LENGTH)
    # Every non-whitespace source character occurs in order exactly once.
    source_chars=[(i,c) for i,c in enumerate(text) if not c.isspace()]
    if ''.join(c for _,c in source_chars)!=''.join(c for chunk in chunks for c in chunk if not c.isspace()):raise ValueError('source content/order changed')
    byte_offsets=[0]
    for c in text:byte_offsets.append(byte_offsets[-1]+len(c.encode('utf-8')))
    out=EXP/'.local/common/bundle';out.mkdir(parents=True,exist_ok=False)
    manifest={'schema_version':1,'status':'prepared_for_peer_freeze','canonical':False,'reference_sha256':REF_SHA,'reference_bytes':len(raw),'reference_whitespace_words':len(text.split()),'upstream':source,'model_hf_revision':HF_REV,'voice':'M1/SID5','language':'en','language_note':'explicit known English as in upstream examples; generic multilingual default would be na','steps':config.DEFAULT_TOTAL_STEPS,'speed':config.DEFAULT_SPEED,'chunk_target_codepoints':config.DEFAULT_MAX_CHUNK_LENGTH,'gap_seconds':config.DEFAULT_SILENCE_DURATION,'gap_frames':int(config.DEFAULT_SILENCE_DURATION*44100),'sample_rate':44100,'latent_channels':144,'latent_hop':3072,'chunk_count':len(chunks),'source_nonwhitespace_characters_preserved_in_order':True,'segmentation_order':'validate original characters; split RAW paragraphs/sentences; per-chunk globalNFKD and official UnicodeProcessor normalization; language tags and IDs','oversized_sentence_policy':'keep entire sentence even above300; no comma/word fallback in this exact pinned Python implementation','wave_assembly':'append full native vocoderL*3072 samples per chunk (no predicted-duration trimming),13230zero frames between chunks, no leading/trailing extra gap','session_lifecycle':'create4 ONNX sessions once; keep and reuse across all chunks','chunks':[],'tensors':{},'numpy_version':np.__version__}
    cursor=0;normalized=[]
    for i,chunk in enumerate(chunks):
        name=f'{i:03d}';folder=out/name;folder.mkdir()
        ids,mask=processor([chunk],'en');processed=processor._preprocess_text(chunk,'en')
        normalized.append(processed[4:-5])
        if ids.shape[1]!=len(processed) or not np.all(mask==1):raise ValueError('unexpected native frontend shape/mask')
        content=[c for c in chunk if not c.isspace()];span=source_chars[cursor:cursor+len(content)];cursor+=len(content)
        ranges=[[byte_offsets[j],byte_offsets[j+1]] for j,_ in span]
        (folder/'raw-chunk.txt').write_text(chunk);(folder/'processed.txt').write_text(processed);(folder/'source-content-byte-ranges.json').write_text(json.dumps(ranges)+'\n')
        ids.astype('<i8').tofile(folder/'text_ids.i64');mask.astype('<f4').tofile(folder/'text_mask.f32')
        record={'index':i,'raw_codepoints':len(chunk),'text_extent':ids.shape[1],'source_content_character_count':len(content),'first_source_byte':ranges[0][0],'last_source_byte_exclusive':ranges[-1][1],'raw_chunk_sha256':sha(chunk.encode()),'processed_sha256':sha(processed.encode()),'ids_sha256':sha((folder/'text_ids.i64').read_bytes()),'mask_sha256':sha((folder/'text_mask.f32').read_bytes()),'oversized_raw_sentence':len(chunk)>300}
        manifest['chunks'].append(record)
    if cursor!=len(source_chars):raise ValueError('unconsumed source content')
    (out/'normalized-reference.txt').write_text(' '.join(normalized))
    voice=json.loads((ASSETS/'voice_styles/M1.json').read_text())
    for name,shape in [('style_dp',[1,8,16]),('style_ttl',[1,50,256])]:
        array=np.asarray(voice[name]['data'],dtype='<f4').reshape(shape)
        array.tofile(out/(name+'.f32'));manifest['tensors'][name+'.f32']={'shape':shape,'sha256':sha(array.tobytes()),'dtype':'float32_le'}
    schedule=np.arange(config.DEFAULT_TOTAL_STEPS,dtype='<f4');schedule.tofile(out/'current_steps.f32');np.array([config.DEFAULT_TOTAL_STEPS],dtype='<f4').tofile(out/'total_steps.f32')
    # Same distribution and continuous MT19937/legacy-Gaussian stream as upstream
    # np.random.randn. Native shape determines each route's OWN stream offset.
    seed=20260911;max_latent=1000;draws=len(chunks)*144*max_latent
    stream=np.random.RandomState(seed).randn(draws).astype('<f4');stream.tofile(out/'noise_stream.f32')
    manifest['rng']={'algorithm':'NumPy legacy RandomState/MT19937 standard_normal ->float32; matches np.random.seed(seed);np.random.randn(...)','seed':seed,'provider_seed_policy':'provider sets no seed; this fixed reproducibility seed is an explicit experiment choice','stream_draws':draws,'max_native_latent_per_chunk':max_latent,'noise_stream_sha256':sha(stream.tobytes()),'shape_policy':'Each route consumes144*its_own_nativeL consecutive values, reshapes[1,144,nativeL], applies own mask; HTP may then zero-pad into staticlayout without consuming extra RNG. If ownL differs, channel alignment and subsequent stream offsets differ; record actual offsets/active hashes, never claim seed implies equality.'}
    for name in ['current_steps.f32','total_steps.f32']:manifest['tensors'][name]={'sha256':sha((out/name).read_bytes()),'bytes':(out/name).stat().st_size}
    # Simple numeric runner ABI (no text); per-chunk exact nativeT.
    (out/'runner-config.txt').write_text(f'{len(chunks)} {config.DEFAULT_TOTAL_STEPS} {config.DEFAULT_SPEED} {manifest["gap_frames"]} {draws}\n'+'\n'.join(str(x['text_extent']) for x in manifest['chunks'])+'\n')
    manifest['runner_config_sha256']=sha((out/'runner-config.txt').read_bytes());manifest['normalized_reference_sha256']=sha((out/'normalized-reference.txt').read_bytes())
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (EXP/'protocol').mkdir(exist_ok=True);(EXP/'protocol/inputs.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'chunks':len(chunks),'raw_lengths':[x['raw_codepoints'] for x in manifest['chunks']],'native_T':[x['text_extent'] for x in manifest['chunks']],'steps':manifest['steps'],'speed':manifest['speed'],'gap_frames':manifest['gap_frames'],'noise_stream_sha256':manifest['rng']['noise_stream_sha256']}))

if __name__=='__main__':main()

#!/usr/bin/env python3
"""Align one already-saved unprompted ASR transcript to CPU's exact reference.

No ASR/model call, text decoding prompt, audio modification or transcript edit.
The initial raw-reference alignment is retained separately; only the arithmetic
coverage comparison is recomputed against the frozen product-normalized text.
"""
import argparse
import importlib.util
import json
from pathlib import Path
from materialize import sha
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--asr-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    common=ROOT.parent/'common/asr_coverage.py'
    spec=importlib.util.spec_from_file_location('common_alignment_only',common);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    initial=json.loads((a.asr_dir/'coverage.json').read_text())
    cpu=json.loads((ROOT.parent/'cpu/results/asr-full-render-01.json').read_text())
    reference=ROOT.parent/'.local/common/input-bundle/normalized.txt';transcript=a.asr_dir/'transcript.txt'
    if sha(reference)!=cpu['reference_sha256'] or sha(transcript)!=initial['transcript_sha256']:raise ValueError('reference/transcript binding differs')
    for key in ('model_sha256','whisper_version','torch_version','settings','threads','logical_asr_passes'):
        if initial[key]!=cpu[key]:raise ValueError('ASR protocol mismatch: '+key)
    metrics=module.alignment(reference.read_text(),transcript.read_text())
    result={**initial,**metrics,'reference_sha256':sha(reference),
            'raw_reference_sha256':initial['reference_sha256'],'original_raw_alignment_reference_words':initial['reference_words'],
            'alignment_only_recomputed_no_new_ASR':True,'ASR_transcript_unchanged':True,
            'original_raw_alignment_sha256':sha(a.asr_dir/'coverage.json'),
            'qualification':'Same local model/settings: canonical CPU control0WER over36 words',
            'control_metadata':'cpu/results/asr-control-01.json',
            'word_count_note':'487 raw whitespace words;495 regex words after frozen product normalization, matching CPU. Initial raw-reference506-word alignment remains private; no ASR retry.',
            'automatic_coverage_pass':False,'scope':'Fallible unprompted ASR strongly argues against complete/intelligible coverage; not a human listening verdict.'}
    if result['reference_words']!=cpu['reference_words']:raise ValueError('comparison word counts differ')
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ('reference_words','hypothesis_words','word_error_rate','substitutions','deletions','insertions','exactly_matched_reference_words','last_30_reference_words_matched','logical_asr_passes')},indent=2))


if __name__=='__main__':main()

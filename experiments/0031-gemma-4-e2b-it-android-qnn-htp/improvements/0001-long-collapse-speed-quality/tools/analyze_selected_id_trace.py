#!/usr/bin/env python3
"""Summarize genuine selected-ID observations; never infer missing token IDs."""
import argparse
import json
import hashlib
from pathlib import Path
import re
import struct

TAG='GEMMA_SELECTED_ID_V1'
PATTERN=re.compile(r'GEMMA_SELECTED_ID_V1 ordinal=(\d+) token=(-?\d+) configured_eos=([01]) n_past=(\d+)')


def summarize(text, expected_generated=None, eos_ids=(1,106), vocab_size=262144):
    records=[];errors=[]
    for line_number,line in enumerate(text.splitlines(),1):
        if TAG not in line:continue
        m=PATTERN.fullmatch(line)
        if m is None:
            errors.append({'line':line_number,'issue':'malformed/ambiguous observation'});continue
        item={'line':line_number,'ordinal':int(m[1]),'token':int(m[2]),
              'configured_eos':m[3]=='1','n_past':int(m[4])}
        records.append(item)
        if not 0<=item['token']<vocab_size:
            errors.append({'line':line_number,'issue':'token outside declared vocabulary'})
        if item['configured_eos']!=(item['token'] in eos_ids):
            errors.append({'line':line_number,'issue':'observed membership differs from bound policy'})
    ordinals=[r['ordinal'] for r in records]
    contiguous=bool(records) and ordinals==list(range(len(records)))
    complete=not errors and contiguous and expected_generated is not None and len(records)==expected_generated
    occurrences=[]
    for index,item in enumerate(records):
        if item['token']!=50:continue
        later=next((r for r in records[index+1:] if r['ordinal']>item['ordinal']),None)
        occurrences.append({'ordinal':item['ordinal'],'configured_eos':item['configured_eos'],
            'subsequent_sampling_observed':True if later is not None else None,
            'next_observed_ordinal':later['ordinal'] if later else None,
            'limitation':None if later else 'No later sampling record; do not invent whether EOS, cap, interruption or missing capture ended it.'})
    return {'records':records,'trace_errors':errors,'records_count':len(records),
        'expected_profile_generated_tokens':expected_generated,'contiguous_from_zero':contiguous,
        'coverage_complete_against_profile':complete,
        'id50_observed':True if occurrences else (False if complete else None),
        'id50_occurrences':occurrences,
        'configured_eos_observations':[r for r in records if r['configured_eos']],
        'internal_stop_decision':None,
        'internal_stop_decision_missing_reason':'This observer records selected IDs and configured membership, not the internal terminal branch/enum. Subsequent sampling is observed separately; membership alone is not a stop event.',
        'absence_boundary':'ID50 absence is asserted only for a contiguous trace matching the bound profile count; decoded/re-tokenized text is never used.',
        'scope_requirement':'Caller must separately bind one actual query, instrumented runtime/source identity, input, policy, profile and raw lifecycle.'}


def input_parity(text, expected_int32le):
    """Real same-runtime post-query tokenization, not a prefill-tensor capture."""
    ids=[int(x) for x in text.split()]
    if not ids or any(not 0<=x<262144 for x in ids):
        raise ValueError('invalid token-ID observation')
    data=struct.pack('<'+'i'*len(ids),*ids)
    return {'tokens':len(ids),'int32le_sha256':hashlib.sha256(data).hexdigest(),
            'exact_frozen_input_ids_equal':data==expected_int32le,
            'basis':'Post-query same-runtime tokenizer encoding; input source/config and actual query profile must also be bound. Not direct prefill-tensor capture.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stderr',type=Path,required=True)
    p.add_argument('--expected-generated',type=int)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--input-ids-text',type=Path)
    p.add_argument('--expected-input-ids',type=Path)
    args=p.parse_args()
    if bool(args.input_ids_text)!=bool(args.expected_input_ids):p.error('both input parity paths are required together')
    result=summarize(args.stderr.read_text(errors='replace'),args.expected_generated)
    result['post_query_input_parity']=input_parity(args.input_ids_text.read_text(),args.expected_input_ids.read_bytes()) if args.input_ids_text else None
    with args.output.open('x') as out:
        json.dump(result,out,indent=2)
        out.write('\n')

#!/usr/bin/env python3
"""Saved-only correlation for the pinned BasicDialog, not speculative decoding.

The source-bound embedding entry hook (original basic.cpp748) follows COMPLETE
prefill and precedes _n_generated++. Its ordinal0 is the first generated token,
not an intermediate prefill logit/proposal. The follow-on hook (153) runs after
one primary decode execution but BEFORE _n_past++/_n_generated++ (190 onward).
Thus ordinal0 and ordinal1 BOTH observe n_past==input_count. No grammar/jump-
forward, speculative/batch, resume or additional query may be assumed away:
caller must bind the actual route/script/config/profile to this exact scope.

This module adds no runtime hook and changes no stage/config/query.
"""
from collections import Counter

BASIC_SOURCE_SHA256='a9a91951e2ad13101291899589d328f61e15e71bde8a6c7cd3314727d9c0e71b'


def correlate(trace, *, input_count, accepted_generated_count, basic_scope_confirmed,
              ar128_status0_count=None, ar1_status0_count=None):
    """Keep every raw observation, separating eligible accepted-generation IDs.

basic_scope_confirmed must derive from the actual bound runtime/config/script:
this single fresh non-batch BasicDialog, per-layer embedding route, no grammar,
proposal/draft/jump-forward/resume calls. It is not inferred from decoded text.
accepted_generated_count is the actual completed generation counter/profile,
not the requested2048 cap. Unavailable counters keep correlation unavailable.
"""
    accepted=[];excluded=[]
    records=trace['records']
    counts=Counter(r['ordinal'] for r in records)
    usable=(basic_scope_confirmed and isinstance(input_count,int) and input_count>0
            and isinstance(accepted_generated_count,int) and accepted_generated_count>=0)
    backend_bound=(usable and ar128_status0_count==(input_count+127)//128
                   and ar1_status0_count==max(0,accepted_generated_count-1)
                   and accepted_generated_count>0)
    for record in records:
        n=record['ordinal'];why=None
        if not usable:why='actual BasicDialog scope or accepted generation count unconfirmed'
        elif counts[n]!=1:why='ambiguous duplicate generation ordinal'
        elif not 0<=n<accepted_generated_count:why='not within actual accepted generation count'
        elif record['n_past']!=input_count+max(0,n-1):
            why='not the source-bound primary generation position; do not promote prefill/proposal/other records'
        if why:
            excluded.append({'observation':record,'reason':why});continue
        item=dict(record,accepted_generation_index=n,
                  phase='first_generated_after_complete_prefill' if n==0 else 'primary_decode',
                  primary_decode_step=None if n==0 else n,
                  producer_execution_index=(ar128_status0_count-1+n) if backend_bound else None)
        accepted.append(item)
    complete=(usable and not trace['trace_errors'] and not excluded
              and [r['ordinal'] for r in accepted]==list(range(accepted_generated_count))
              and accepted_generated_count>0)
    hits=[]
    for i,r in enumerate(accepted):
        if r['token']!=50:continue
        later=next((x for x in accepted[i+1:] if x['ordinal']>r['ordinal']),None)
        hits.append({'accepted_generation_index':r['ordinal'],'configured_eos':r['configured_eos'],
                     'later_accepted_generation_observed':True if later else None,
                     'next_observed_generation_index':later['ordinal'] if later else None})
    return {'basic_scope_confirmed':basic_scope_confirmed,'input_count':input_count,
            'actual_accepted_generated_count':accepted_generated_count,
            'accepted_generation_records':accepted,'excluded_unpromoted_observations':excluded,
            'accepted_generation_coverage_complete':complete,
            'accepted_id50_observed':True if hits else (False if complete else None),
            'id50_continuation_observations':hits,'backend_execution_counts_bound':backend_bound,
            'internal_stop_decision':None,
            'stop_limitation':'Observed membership/continuation are not an internal stop decision. Missing records never identify a terminal reason.',
            'historical_limit':'This actual source-runtime request only; cannot backfill older traces or establish binary equivalence from equal text.'}

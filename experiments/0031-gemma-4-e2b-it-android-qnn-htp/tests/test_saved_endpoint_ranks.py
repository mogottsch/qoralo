import contextlib
import importlib
import io
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
a=importlib.import_module('analyze_saved_endpoint_ranks')


def selections(values,k):
    strict,boundary,slots,_=a.top_partition(values,k)
    fixed=set(np.flatnonzero(strict).tolist())
    return [fixed|set(x) for x in itertools.combinations(np.flatnonzero(boundary).tolist(),slots)]


class SavedEndpointRankTests(unittest.TestCase):
    def test_tie_overlap_range_matches_exhaustive_choices(self):
        rng=np.random.default_rng(3161)
        for _ in range(70):
            x=rng.integers(0,4,8);y=rng.integers(0,4,8)
            for k in [1,3,5,8]:
                r=a.topk_overlap(x,y,k);counts=[len(l&r) for l in selections(x,k) for r in selections(y,k)]
                self.assertEqual(r['admissible_topk_intersection_min'],min(counts))
                self.assertEqual(r['admissible_topk_intersection_max'],max(counts))
                self.assertFalse(r['arbitrary_tie_break_used'])

    def test_rank_intervals_and_average_ties(self):
        x=np.array([5.,5.,3.,1.]);r,t=a.midranks(x)
        np.testing.assert_array_equal(r,[1.5,1.5,3,4]);self.assertEqual(t['largest_tie'],2)
        self.assertEqual(a.rank_interval(x,0),{'min':1,'max':2,'midrank':1.5,'tie_count':2})
        self.assertEqual(a.rank_interval(x,2)['min'],3)
        self.assertEqual(a.compare(np.ones(4),x,ks=(2,))['global_statistic']['null_reason'],'constant rank vector')

    def test_high_tail_correlation_does_not_hide_decision_disagreement(self):
        x=np.arange(1024,dtype=np.float32)[::-1];y=x.copy();y[:128]=y[:128][::-1]
        r=a.compare(x,y)
        self.assertGreater(r['global_statistic']['value'],.9)
        self.assertTrue(r['global_statistic']['high_global_agreement_is_not_small_decision_or_prefill_drift'])
        self.assertEqual(r['topk'][0]['admissible_topk_intersection_max'],0)
        self.assertEqual(r['winners']['native']['winner_IDs_bounded'][0]['other_route_rank']['min'],128)
        self.assertFalse(r['automatic_causal_or_quality_classification'])

    def test_exact_bf16_bits_finiteness_and_mutation_rejection(self):
        raw=np.array([0x3f80,0xbf80,0,0x8000,1],dtype='<u2');f=(raw.astype('<u4')<<16).view('<f4')
        np.testing.assert_array_equal(a.expand_bf16(raw,f).view('<u4'),f.view('<u4'))
        changed=f.copy();changed.view('<u4')[0]+=1
        with self.assertRaises(ValueError):a.expand_bf16(raw,changed)
        for code in [0x7f80,0xff80,0x7fc0]:
            words=np.array([code],dtype='<u2');floats=(words.astype('<u4')<<16).view('<f4')
            with self.assertRaises(ValueError):a.expand_bf16(words,floats)
        with self.assertRaises(ValueError):a.compare(np.array([np.nan,1]),np.array([0,1]),ks=(1,))

    def test_binding_failure_stops_without_comparison_or_retry(self):
        def broken():raise ValueError('synthetic binding failure')
        with tempfile.TemporaryDirectory() as tmp,patch.object(a,'compare') as compute,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp)/'packet';self.assertEqual(a.execute(root,broken),2);compute.assert_not_called()
            r=json.loads((root/'status.json').read_text());self.assertFalse(r['comparison_performed']);self.assertFalse(r['automatic_retry'])
            self.assertFalse((root/'ranks.json').exists())

    def test_packet_size_and_overwrite_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            w=a.PacketWriter(Path(tmp)/'p')
            with self.assertRaises(ValueError):w.write('huge.json',{'x':'a'*65537})
            with self.assertRaises(ValueError):w.write('../outside.json',{})
            w.write('once.json',{'ok':True})
            with self.assertRaises(FileExistsError):w.write('once.json',{})


if __name__=='__main__':unittest.main()

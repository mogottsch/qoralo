#!/usr/bin/env python3
"""Synthetic-only differential fixtures from the pinned provider. No neural sessions/calls or user text."""
from pathlib import Path
import hashlib,json,random,unicodedata
ROOT=Path(__file__).resolve().parents[3]


def main():
    import supertonic
    from supertonic import core,utils
    manifest=json.loads((ROOT/'experiments/0037-supertonic-provider-pipeline/.local/upstream/source-manifest.json').read_text())
    for item in manifest['files']:
        p=Path(supertonic.__file__).parent/item['file']
        if hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Provider source drift')
    if unicodedata.unidata_version!='14.0.0':raise ValueError('Unicode drift')
    proc=core.UnicodeProcessor(str(ROOT/'experiments/0007-mobile-podcast-preview-bakeoff/artifacts/supertonic-3/snapshot/onnx/unicode_indexer.json'))
    cases=['',' ', 'Hello world', 'Hello.', 'Hello>', 'Dr. Smith arrived. Then left!', 'X. Y. Z. Done?',
        'Prof. A. B. said this. Next sentence.', 'a\\b © ♥ ★ ☆ ♡', 'café\u0301\u0327', '¯´‑–—_`',
        '😀☺🇮🇪🀄', '"""quotes\'\'\' and ``backticks', 'e.g., i.e., @  ,  !', 'one\n\n two\n \nthree',
        '\u001c\u0085\u00a0\u202fwhitespace\u3000', '\U00010781A. After Unicode14 modifier letter.',
        'éA. After Latin letter.', '١A. After digit.', '\u0301A. After combining mark.',
        'a'*301+'.', 'word '*90, 'First.\r\nSecond.\r\n\r\nThird.', '東方', '\x00', 'a\u0315\u0300z',
        ('First sentence. Second sentence? Third sentence! '*40).strip()]
    rng=random.Random(173)
    words=['hello','world','Dr.','Mr.','Mrs.','Prof.','St.','Ph.D.','e.g.','i.e.,','A.','AB.','café','ﬁ','é\u0327','@','–','😀','\U00010781A.']
    separators=[' ','  ','\n','\n\n','\u00a0','\t','\u0085','\r\n']
    for _ in range(240):cases.append(''.join(rng.choice(words)+rng.choice(['','.','?','!'])+rng.choice(separators) for _ in range(rng.randrange(1,90))))
    records=[];needed=set()
    for text in cases:
        chunks=utils.chunk_text(text,300);valid,unsupported=proc.validate_text(text)
        normalized=proc._preprocess_text(text,'en')
        for ch in text:
            needed.update(ord(c) for c in proc._preprocess_text(ch))
        prepared=[proc._preprocess_text(c,'en') for c in chunks]
        for value in [normalized,*prepared]:needed.update(map(ord,value))
        records.append({'raw':text,'chunks':chunks,'normalized':normalized,'validOriginal':valid,
            'processedChunks':prepared,'chunkIds':[[proc.indexer[ord(c)] for c in s] for s in prepared] if valid else None})
    # Include only mapping entries needed by synthetic fixtures, not a model asset export.
    mapping={str(cp):proc.indexer[cp] if cp<len(proc.indexer) else -1 for cp in sorted(needed)}
    out=ROOT/'podcast-app/app/src/test/resources/provider-frontend';out.mkdir(parents=True,exist_ok=True)
    (out/'golden.json').write_text(json.dumps({'authority':manifest,'unicodeVersion':'14.0.0','syntheticOnly':True,
        'indexerEntriesForFixtures':mapping,'cases':records},ensure_ascii=True,indent=2)+'\n')
    print(json.dumps({'syntheticCases':len(records),'fixtureIndexerEntries':len(mapping),'newModelCalls':0}))

if __name__=='__main__':main()

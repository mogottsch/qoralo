#!/usr/bin/env python3
"""Generate non-neural Unicode14 NFKD/CCC/word data from the pinned provider Python3.11 runtime.

Unicode data is covered by app/src/main/resources/provider-frontend/UNICODE-LICENSE.txt.
No model, source text, ONNX session or inference is involved.
"""
from pathlib import Path
import hashlib,json,struct,unicodedata as u


def main():
    if u.unidata_version!='14.0.0':raise ValueError('Use the pinned provider Python3.11 Unicode14 runtime')
    mappings=[];classes=[];ranges=[];start=None
    for cp in range(0x110000):
        ch=chr(cp);n=u.normalize('NFKD',ch)
        if n!=ch:mappings.append((cp,[ord(c) for c in n]))
        c=u.combining(ch)
        if c:classes.append((cp,c))
        word=ch.isalnum() or ch=='_'
        if word and start is None:start=cp
        if not word and start is not None:ranges.append((start,cp-1));start=None
    if start is not None:ranges.append((start,0x10ffff))
    b=bytearray(b'PU14');b+=struct.pack('>I',len(mappings))
    for cp,values in mappings:b+=struct.pack('>II',cp,len(values))+struct.pack('>'+str(len(values))+'I',*values)
    b+=struct.pack('>I',len(classes))
    for cp,c in classes:b+=struct.pack('>II',cp,c)
    b+=struct.pack('>I',len(ranges))
    for low,high in ranges:b+=struct.pack('>II',low,high)
    root=Path(__file__).resolve().parents[2]/'app/src/main/resources/provider-frontend'
    root.mkdir(parents=True,exist_ok=True);(root/'unicode14-nfkd.bin').write_bytes(b)
    record={'unicodeVersion':u.unidata_version,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),
        'decompositions':len(mappings),'combiningClasses':len(classes),'wordRanges':len(ranges),
        'semantics':'per-codepoint fully decomposed NFKD plus stable GLOBAL canonical combining-class ordering; Python Unicode alnum+underscore word boundaries',
        'modelData':False,'upstream':'supertonic-py1.3.1 Python3.11 unicodedata14.0.0; Unicode data license in adjacent file'}
    (root/'unicode14-data.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))

if __name__=='__main__':main()

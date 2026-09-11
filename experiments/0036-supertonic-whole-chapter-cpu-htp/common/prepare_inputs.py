#!/usr/bin/env python3
"""Prepare PRIVATE exact product-reference tensors; never print text or IDs."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import unicodedata

REFERENCE_SHA = 'cbfd5bbef581f0e793b86a568f8d4aa87fe857f413e5c2ea4780b558fc71600b'
REPLACEMENTS = [('–','-'),('‑','-'),('—','-'),('_',' '),('“','"'),('”','"'),('‘',"'"),('’',"'"),('´',"'"),('`',"'"),('[',' '),(']',' '),('|',' '),('/',' '),('#',' '),('→',' '),('←',' '),('♥',''),('☆',''),('♡',''),('©',''),('\\',''),('@',' at '),('e.g.,','for example, '),('i.e.,','that is, ')]
TERMINAL = set('.!?;:,\'\")]}>…。」』】〉》›»“”‘’')


def normalize(text):
    # Mirrors app SupertonicTextNormalizer.kt, including per-codepoint NFKD.
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    text = ''.join(c for c in text if not 0x1F000 <= ord(c) <= 0x1FFFF and ord(c) != 0 and (not (ord(c) < 32 or 127 <= ord(c) <= 159) or c.isspace()))
    text = re.sub(r" ([,.!?;:'])", r'\1', text).replace('`','').replace('""','"').replace("''", "'")
    text = re.sub(r'\s+', ' ', text).strip()
    if text and text[-1] not in TERMINAL:
        text += '.'
    text = ''.join(d for c in text for d in unicodedata.normalize('NFKD', c) if ord(d) <= 65535 and not 0xD800 <= ord(d) <= 0xDFFF)
    if not text.strip():
        raise ValueError('empty normalized input')
    return text


def sha(data):
    return hashlib.sha256(data).hexdigest()


def flatten(values):
    if isinstance(values, list):
        for value in values:
            yield from flatten(value)
    else:
        yield values


def noise(length, seed=20260813):
    """Raw unmasked C-layout Box-Muller; saved bytes, NOT seed, are binding."""
    state = seed
    mask = (1 << 64) - 1
    def uniform():
        nonlocal state
        state ^= state >> 12
        state ^= (state << 25) & mask
        state ^= state >> 27
        value = (state * 2685821657736338717) & mask
        return ((value >> 11) + 1.0) / 9007199254740993.0
    values = []
    for _ in range(144 * length // 2):
        radius = math.sqrt(-2 * math.log(uniform()))
        angle = 6.283185307179586 * uniform()
        values.extend((radius * math.cos(angle), radius * math.sin(angle)))
    return struct.pack(f'<{len(values)}f', *values)


def prepare(reference, assets, output, text_extent=3200):
    raw = reference.read_bytes()
    if sha(raw) != REFERENCE_SHA or len(raw) != 3190:
        raise ValueError('wrong reference bytes')
    normalized = normalize(raw.decode('utf-8'))
    processed = '<en>' + normalized + '</en>'
    if len(normalized) != 3158 or len(processed) != 3167 or len(processed) > text_extent:
        raise ValueError('normalization/capacity mismatch')
    indexer_path = assets / 'onnx/unicode_indexer.json'
    voice_path = assets / 'voice_styles/M1.json'
    if sha(indexer_path.read_bytes()) != '9bf7346e43883a81f8645c81224f786d43c5b57f3641f6e7671a7d6c493cb24f':
        raise ValueError('indexer binding mismatch')
    if sha(voice_path.read_bytes()) != 'e35604687f5d23694b8e91593a93eec0e4eca6c0b02bb8ed69139ab2ea6b0a5b':
        raise ValueError('voice binding mismatch')
    indexer = json.loads(indexer_path.read_text())
    ids = [indexer[ord(c)] for c in processed]
    if any(x < 0 for x in ids):
        raise ValueError('unmapped input')
    ids += [0] * (text_extent - len(ids))
    mask = [1.] * len(processed) + [0.] * (text_extent - len(processed))
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'reference_sha256': sha(raw), 'reference_bytes': len(raw), 'canonical': False, 'text_extent': text_extent, 'active_text_positions': len(processed), 'normalized_codepoints': len(normalized), 'normalized_sha256': sha(normalized.encode()), 'processed_sha256': sha(processed.encode()), 'voice': 'M1/SID5', 'speed': 1.0, 'steps': 5, 'sample_rate': 44100, 'latent_channels': 144, 'latent_hop_samples': 3072, 'latent_extent': None, 'tensors': {}}
    def save(name, data, dtype, shape):
        (output / name).write_bytes(data)
        manifest['tensors'][name] = {'sha256': sha(data), 'bytes': len(data), 'dtype': dtype, 'shape': shape}
    save('text_ids.i64', struct.pack(f'<{text_extent}q', *ids), 'int64_le', [1,text_extent])
    save('text_mask.f32', struct.pack(f'<{text_extent}f', *mask), 'float32_le', [1,1,text_extent])
    voice = json.loads(voice_path.read_text())
    for name, shape in [('style_dp',[1,8,16]),('style_ttl',[1,50,256])]:
        item = voice[name]
        values = list(flatten(item['data']))
        if item['dims'] != shape or item['type'] != 'float32' or len(values) != math.prod(shape):
            raise ValueError('voice shape mismatch')
        save(name+'.f32', struct.pack(f'<{len(values)}f', *values), 'float32_le', shape)
    save('current_step.f32', struct.pack('<5f', 0,1,2,3,4), 'float32_le', [5])
    save('total_step.f32', struct.pack('<f', 5), 'float32_le', [1])
    (output/'normalized.txt').write_text(normalized)
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


def bind_noise(output, length):
    manifest = json.loads((output/'manifest.json').read_text())
    if manifest['latent_extent'] is not None or not 1 <= length <= 10000:
        raise ValueError('already bound or invalid length')
    data = noise(length)
    (output/'noise.f32').write_bytes(data)
    manifest['latent_extent'] = length
    manifest['tensors']['noise.f32'] = {'sha256':sha(data), 'bytes':len(data), 'dtype':'float32_le', 'shape':[1,144,length]}
    manifest['noise_contract'] = 'Raw unmasked C-layout [1,144,L], saved bytes binding; seed20260813 xorshift64* Box-Muller. Each route zeros positions >= its own ceil(floor(FP32(duration*44100))/3072), uses its own latent mask. Not app chapter-id seed; no CPU model outputs shared.'
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--reference',type=Path)
    p.add_argument('--assets',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--bind-noise',type=int)
    a = p.parse_args()
    if '.local' not in a.output.parts:
        p.error('output must be private .local')
    if a.bind_noise:
        bind_noise(a.output,a.bind_noise)
    else:
        prepare(a.reference,a.assets,a.output)

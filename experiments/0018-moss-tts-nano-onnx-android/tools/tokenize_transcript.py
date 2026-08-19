#!/usr/bin/env python3
"""Tokenize the frozen UTF-8 benchmark transcript with the pinned SentencePiece model."""
import argparse, hashlib, json
from pathlib import Path
import sentencepiece as spm

p = argparse.ArgumentParser()
p.add_argument('--transcript', type=Path, required=True)
p.add_argument('--model', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
raw = a.transcript.read_bytes()
text = raw.decode('utf-8')
# The Android API accepts token IDs and the official example prescribes direct
# SentencePiece encoding. Remove only the repository text-file line ending.
effective = text[:-1] if text.endswith('\n') else text
processor = spm.SentencePieceProcessor(model_file=str(a.model))
ids = [int(x) for x in processor.encode(effective, out_type=int)]
pieces = [str(x) for x in processor.encode(effective, out_type=str)]
assert processor.decode(ids) == effective
out = {
    'schema_version': 1,
    'transcript_path': 'protocol/transcript.txt',
    'transcript_utf8_bytes': len(raw),
    'transcript_sha256': hashlib.sha256(raw).hexdigest(),
    'line_ending_policy': 'If present, remove exactly one final LF before SentencePiece encoding; no other normalization.',
    'effective_text': effective,
    'effective_text_utf8_bytes': len(effective.encode()),
    'effective_text_sha256': hashlib.sha256(effective.encode()).hexdigest(),
    'tokenizer': {
        'implementation': 'sentencepiece Python wheel',
        'version': spm.__version__,
        'model_sha256': hashlib.sha256(a.model.read_bytes()).hexdigest(),
        'encode_options': {'out_type': 'int', 'add_bos': False, 'add_eos': False},
    },
    'token_count': len(ids),
    'token_ids': ids,
    'pieces': pieces,
    'round_trip_exact': True,
}
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True) + '\n')

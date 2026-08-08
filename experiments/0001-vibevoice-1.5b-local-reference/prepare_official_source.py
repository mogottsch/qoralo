#!/usr/bin/env python3
"""Apply the three minimal changes used for the deterministic local reference."""

from pathlib import Path
import sys

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "artifacts/source/microsoft-vibevoice/demo/inference_from_file.py"
)
text = path.read_text()

replacements = [
    (
        '    return parser.parse_args()\n',
        '    parser.add_argument(\n'
        '        "--seed",\n'
        '        type=int,\n'
        '        default=42,\n'
        '        help="Random seed for deterministic reference generation (default: 42)",\n'
        '    )\n\n'
        '    return parser.parse_args()\n',
    ),
    (
        '    print(f"Using device: {args.device}")\n',
        '    print(f"Using device: {args.device}")\n'
        '    torch.manual_seed(args.seed)\n'
        '    if torch.cuda.is_available():\n'
        '        torch.cuda.manual_seed_all(args.seed)\n'
        '    print(f"Random seed: {args.seed}")\n',
    ),
    (
        '        attn_impl_primary = "flash_attention_2"\n',
        '        attn_impl_primary = "sdpa"\n',
    ),
]

for old, new in replacements:
    if text.count(old) != 1:
        raise SystemExit(f"Expected exactly one match for: {old!r}")
    text = text.replace(old, new)

path.write_text(text)

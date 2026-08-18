#!/usr/bin/env python3
"""Narrow fixed-batch/full-length RNN wrappers for the ExecuTorch screen.

Kokoro uses pack_padded_sequence even though this experiment has batch size 1
and its only sequence has no padding. torch.export intentionally skips that
Python helper. These replacements remove only the no-op pack/pad round trip;
all loaded LSTMs, masks, normalization, and dropout(training=False) remain.
They are eligible only after full-output source-equivalence testing.
"""
from __future__ import annotations

import types
import torch
import torch.nn.functional as F


def _duration_forward(self, x, style, text_lengths, m):
    del text_lengths
    masks = m
    x = x.permute(2, 0, 1)
    s = style.expand(x.shape[0], x.shape[1], -1)
    x = torch.cat([x, s], axis=-1)
    x.masked_fill_(masks.unsqueeze(-1).transpose(0, 1), 0.0)
    x = x.transpose(0, 1)
    x = x.transpose(-1, -2)
    for block in self.lstms:
        # Avoid importing/checking the concrete class during export. The
        # alternating list has adaptive norms at odd indices.
        if hasattr(block, "fc") and not isinstance(block, torch.nn.LSTM):
            x = block(x.transpose(-1, -2), style).transpose(-1, -2)
            x = torch.cat([x, s.permute(1, 2, 0)], axis=1)
            x.masked_fill_(masks.unsqueeze(-1).transpose(-1, -2), 0.0)
        else:
            x = x.transpose(-1, -2)
            x, _ = block(x)
            x = F.dropout(x, p=self.dropout, training=False)
            x = x.transpose(-1, -2)
    return x.transpose(-1, -2)


def _text_forward(self, x, input_lengths, m):
    del input_lengths
    x = self.embedding(x)
    x = x.transpose(1, 2)
    m = m.unsqueeze(1)
    x.masked_fill_(m, 0.0)
    for convolution in self.cnn:
        x = convolution(x)
        x.masked_fill_(m, 0.0)
    x = x.transpose(1, 2)
    x, _ = self.lstm(x)
    x = x.transpose(-1, -2)
    x.masked_fill_(m, 0.0)
    return x


def apply_fixed_full_length_rnn_wrappers(model: torch.nn.Module) -> None:
    model.predictor.text_encoder.forward = types.MethodType(
        _duration_forward, model.predictor.text_encoder
    )
    model.text_encoder.forward = types.MethodType(_text_forward, model.text_encoder)

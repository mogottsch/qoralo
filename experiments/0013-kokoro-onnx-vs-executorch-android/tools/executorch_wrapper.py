#!/usr/bin/env python3
"""Fixed-contract wrapper used only by the bounded ExecuTorch export screen."""
from __future__ import annotations

import torch
import torch.nn as nn

from export_safe_rnn import apply_fixed_full_length_rnn_wrappers


class FixedContractKokoro(nn.Module):
    """Source-equivalent batch-1/no-padding forward for the frozen token shape.

    The official path constructs an all-ones BERT attention mask because every
    one of the 125 positions is real input. Constructing that known mask
    directly avoids a torch.export data-dependent SDPA guard while retaining
    the same SDPA implementation and mask semantics. The two pack/pad no-ops are removed by
    apply_fixed_full_length_rnn_wrappers().
    """

    def __init__(self, kmodel: nn.Module, token_length: int = 125) -> None:
        super().__init__()
        self.kmodel = kmodel
        self.token_length = token_length
        apply_fixed_full_length_rnn_wrappers(self.kmodel)

    def forward(
        self,
        input_ids: torch.Tensor,
        ref_s: torch.Tensor,
        speed: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if input_ids.shape[0] != 1 or input_ids.shape[1] != self.token_length:
            raise ValueError("fixed ExecuTorch screen token shape drift")
        input_lengths = torch.full(
            (1,), self.token_length, device=input_ids.device, dtype=torch.long
        )
        text_mask = torch.zeros(
            (1, self.token_length), device=input_ids.device, dtype=torch.bool
        )
        attention_mask = torch.ones(
            (1, self.token_length), device=input_ids.device, dtype=torch.int32
        )
        bert_dur = self.kmodel.bert(input_ids, attention_mask=attention_mask)
        d_en = self.kmodel.bert_encoder(bert_dur).transpose(-1, -2)
        style_dur = ref_s[:, 128:]
        duration_encoded = self.kmodel.predictor.text_encoder(
            d_en, style_dur, input_lengths, text_mask
        )
        duration_hidden, _ = self.kmodel.predictor.lstm(duration_encoded)
        duration = self.kmodel.predictor.duration_proj(duration_hidden)
        duration = torch.sigmoid(duration).sum(axis=-1) / speed
        pred_dur = torch.round(duration).clamp(min=1).long().squeeze()
        indices = torch.repeat_interleave(
            torch.arange(self.token_length, device=input_ids.device), pred_dur
        )
        alignment = torch.zeros(
            (self.token_length, indices.shape[0]), device=input_ids.device
        )
        alignment[indices, torch.arange(indices.shape[0])] = 1
        alignment = alignment.unsqueeze(0)
        encoded = duration_encoded.transpose(-1, -2) @ alignment
        torch._check(encoded.shape[2] > 0)
        torch._check(encoded.shape[2] <= 4096)
        f0_pred, noise_pred = self.kmodel.predictor.F0Ntrain(encoded, style_dur)
        text_encoded = self.kmodel.text_encoder(
            input_ids, input_lengths, text_mask
        )
        asr = text_encoded @ alignment
        audio = self.kmodel.decoder(
            asr, f0_pred, noise_pred, ref_s[:, :128]
        ).squeeze()
        return audio, pred_dur

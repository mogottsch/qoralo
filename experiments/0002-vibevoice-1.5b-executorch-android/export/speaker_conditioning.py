#!/usr/bin/env python3
"""Validated tensor boundary for VibeVoice speaker-prompt conditioning."""

from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass
class SpeakerTransitionState:
    """Controller-owned speaker selection; model calls never mutate this state."""

    active_speaker_id: int | None = None
    transitions: int = 0

    def select(self, speaker_id: int, valid_speaker_ids: tuple[int, ...]) -> bool:
        if isinstance(speaker_id, bool) or not isinstance(speaker_id, int):
            raise ValueError("speaker_id must be an integer")
        if speaker_id not in valid_speaker_ids:
            raise ValueError(f"Unknown speaker_id {speaker_id}; expected one of {valid_speaker_ids}")
        changed = self.active_speaker_id is not None and self.active_speaker_id != speaker_id
        if changed:
            self.transitions += 1
        self.active_speaker_id = speaker_id
        return changed

    def reset(self) -> None:
        """Start a new utterance; prompt tensors remain immutable and reusable."""
        self.active_speaker_id = None
        self.transitions = 0


class SpeakerConditioner(torch.nn.Module):
    """Replace selected token positions with prompt connector outputs.

    ``speaker_ids`` names each prompt row. ``sequence_speaker_ids`` is ``-1``
    at ordinary token positions and contains a speaker ID at replacement
    positions. For each speaker, valid connector frames are consumed in prompt
    order. The operation is stateless: transition and utterance reset ownership
    belongs to the native generation controller via :class:`SpeakerTransitionState`.
    """

    @staticmethod
    def validate(
        token_embeddings: torch.Tensor,
        connector_outputs: torch.Tensor,
        prompt_mask: torch.Tensor,
        speaker_ids: torch.Tensor,
        sequence_speaker_ids: torch.Tensor,
    ) -> None:
        if token_embeddings.dtype != torch.float32 or token_embeddings.ndim != 3:
            raise ValueError("token_embeddings must be rank-3 float32 [B,S,H]")
        if connector_outputs.dtype != torch.float32 or connector_outputs.ndim != 3:
            raise ValueError("connector_outputs must be rank-3 float32 [N,T,H]")
        if prompt_mask.dtype != torch.bool or prompt_mask.ndim != 2:
            raise ValueError("prompt_mask must be rank-2 bool [N,T]")
        if speaker_ids.dtype != torch.int64 or speaker_ids.ndim != 1:
            raise ValueError("speaker_ids must be rank-1 int64 [N]")
        if sequence_speaker_ids.dtype != torch.int64 or sequence_speaker_ids.ndim != 2:
            raise ValueError("sequence_speaker_ids must be rank-2 int64 [B,S]")
        batch, sequence, hidden = token_embeddings.shape
        prompts, frames, connector_hidden = connector_outputs.shape
        if connector_hidden != hidden:
            raise ValueError(f"connector hidden size {connector_hidden} != token hidden size {hidden}")
        if tuple(prompt_mask.shape) != (prompts, frames):
            raise ValueError("prompt_mask shape must equal connector_outputs [N,T]")
        if speaker_ids.numel() != prompts:
            raise ValueError("speaker_ids length must equal prompt row count")
        if tuple(sequence_speaker_ids.shape) != (batch, sequence):
            raise ValueError("sequence_speaker_ids shape must equal token_embeddings [B,S]")
        if not all(value.is_contiguous() for value in (
            token_embeddings, connector_outputs, prompt_mask, speaker_ids, sequence_speaker_ids
        )):
            raise ValueError("all speaker-conditioning tensors must be contiguous")
        if not torch.isfinite(token_embeddings).all() or not torch.isfinite(connector_outputs).all():
            raise ValueError("speaker-conditioning floating tensors must be finite")
        ids = speaker_ids.tolist()
        if any(value < 0 for value in ids) or len(ids) != len(set(ids)):
            raise ValueError("speaker_ids must be unique non-negative values")
        if bool((sequence_speaker_ids < -1).any()):
            raise ValueError("sequence_speaker_ids may only use -1 or a declared speaker ID")
        selected = sequence_speaker_ids[sequence_speaker_ids != -1]
        unknown = sorted(set(selected.tolist()) - set(ids))
        if unknown:
            raise ValueError(f"sequence_speaker_ids contains unknown IDs: {unknown}")
        for row, speaker_id in enumerate(ids):
            expected = int(prompt_mask[row].sum())
            actual = int((sequence_speaker_ids == speaker_id).sum())
            if actual != expected:
                raise ValueError(
                    f"speaker {speaker_id} selects {actual} sequence positions but has {expected} valid prompt frames"
                )

    def forward(
        self,
        token_embeddings: torch.Tensor,
        connector_outputs: torch.Tensor,
        prompt_mask: torch.Tensor,
        speaker_ids: torch.Tensor,
        sequence_speaker_ids: torch.Tensor,
    ) -> torch.Tensor:
        self.validate(
            token_embeddings, connector_outputs, prompt_mask, speaker_ids, sequence_speaker_ids
        )
        conditioned = token_embeddings.clone()
        # Loop count is fixed by the number of captured prompts (two for the
        # locked Carter/Maya fixture); assignment order follows sequence order.
        for row, speaker_id in enumerate(speaker_ids.tolist()):
            conditioned[sequence_speaker_ids == speaker_id] = connector_outputs[row][prompt_mask[row]]
        return conditioned


def sequence_speaker_ids_from_masks(
    sequence_mask: torch.Tensor, prompt_mask: torch.Tensor, speaker_ids: torch.Tensor
) -> torch.Tensor:
    """Expand the processor's bool mask into the explicit native speaker-ID ABI."""
    if sequence_mask.dtype != torch.bool or sequence_mask.ndim != 2:
        raise ValueError("sequence_mask must be rank-2 bool [B,S]")
    if sequence_mask.shape[0] != 1:
        raise ValueError("speaker conditioning currently requires batch size 1")
    if prompt_mask.dtype != torch.bool or prompt_mask.ndim != 2:
        raise ValueError("prompt_mask must be rank-2 bool [N,T]")
    if speaker_ids.dtype != torch.int64 or speaker_ids.ndim != 1:
        raise ValueError("speaker_ids must be rank-1 int64 [N]")
    if prompt_mask.shape[0] != speaker_ids.numel():
        raise ValueError("prompt rows and speaker IDs differ")
    ids = speaker_ids.tolist()
    if any(value < 0 for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("speaker_ids must be unique non-negative values")
    total = int(prompt_mask.sum())
    if int(sequence_mask.sum()) != total:
        raise ValueError(f"sequence mask selects {int(sequence_mask.sum())} positions, expected {total}")
    result = torch.full(sequence_mask.shape, -1, dtype=torch.int64, device=sequence_mask.device)
    positions = sequence_mask[0].nonzero(as_tuple=False).flatten()
    cursor = 0
    for row, speaker_id in enumerate(speaker_ids.tolist()):
        count = int(prompt_mask[row].sum())
        result[0, positions[cursor : cursor + count]] = speaker_id
        cursor += count
    return result.contiguous()

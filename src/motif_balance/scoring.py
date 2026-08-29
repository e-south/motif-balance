from __future__ import annotations

import math
from typing import Literal

from motif_balance.compile import CompiledMotif, CompiledProblem
from motif_balance.constants import DNA_ALPHABET, DNA_COMPLEMENT
from motif_balance.errors import InvalidSequence
from motif_balance.model import Evaluation, MotifMatch

_BASE_INDEX: dict[str, int] = {base: index for index, base in enumerate(DNA_ALPHABET)}
_TIE_EPSILON = 1.0e-12
_ATTAINMENT_TOLERANCE = 1.0e-12


def reverse_complement(sequence: str) -> str:
    return sequence.translate(DNA_COMPLEMENT)[::-1]


def _window_score(window: str, motif: CompiledMotif) -> float:
    return sum(
        float(motif.log_odds[position, _BASE_INDEX[base]]) for position, base in enumerate(window)
    )


def _best_match(sequence: str, motif: CompiledMotif, *, both_strands: bool) -> MotifMatch:
    width = motif.model.width
    best: tuple[float, int, int, Literal["+", "-"], str] | None = None
    for start in range(len(sequence) - width + 1):
        window = sequence[start : start + width]
        orientations: tuple[tuple[int, Literal["+", "-"], str], ...] = ((0, "+", window),)
        if both_strands:
            orientations += ((1, "-", reverse_complement(window)),)
        for strand_order, strand, motif_oriented in orientations:
            raw_score = _window_score(motif_oriented, motif)
            candidate: tuple[float, int, int, Literal["+", "-"], str] = (
                raw_score,
                start,
                strand_order,
                strand,
                motif_oriented,
            )
            is_better = best is None or raw_score > best[0] + _TIE_EPSILON
            is_preferred_tie = best is not None and (
                abs(raw_score - best[0]) <= _TIE_EPSILON
                and (start < best[1] or (start == best[1] and strand_order < best[2]))
            )
            if is_better or is_preferred_tie:
                best = candidate
    if best is None:  # compile_design prevents this path
        raise ValueError(f"Sequence is shorter than motif '{motif.model.motif_id}'.")
    raw_score, start, _, strand, motif_oriented = best
    if motif.model.schema_version == "motif-model/v1":
        normalized = max(
            0.0,
            (raw_score - motif.null_mean) / motif.normalization_denominator,
        )
    else:
        normalized = (raw_score - motif.score_min) / (motif.score_max - motif.score_min)
        if normalized < -_ATTAINMENT_TOLERANCE or normalized > 1.0 + _ATTAINMENT_TOLERANCE:
            raise ValueError(
                f"relative PWM attainment for motif '{motif.model.motif_id}' is outside "
                "the attainable range"
            )
        if normalized < 0.0 or normalized > 1.0:
            raise ValueError(
                f"relative PWM attainment for motif '{motif.model.motif_id}' crossed "
                "an endpoint within numerical tolerance"
            )
    return MotifMatch(
        motif_id=motif.model.motif_id,
        start=start,
        end=start + width,
        strand=strand,
        matched_sequence=motif_oriented,
        raw_score=raw_score,
        normalized_score=normalized,
    )


def evaluate(sequence: str, problem: CompiledProblem) -> Evaluation:
    normalized = sequence.upper()
    if len(normalized) != problem.spec.length:
        raise InvalidSequence(
            f"sequence must contain exactly {problem.spec.length} nucleotides",
            field="sequence",
        )
    if set(normalized) - set(DNA_ALPHABET):
        raise InvalidSequence(
            "sequence must contain only A, C, G, and T",
            field="sequence",
        )
    matches = tuple(
        _best_match(
            normalized,
            motif,
            both_strands=problem.spec.strands == "both",
        )
        for motif in problem.motifs
    )
    balance_score = min(match.normalized_score for match in matches)
    if not math.isfinite(balance_score):
        raise ValueError("evaluation produced a nonfinite balance score")
    return Evaluation(sequence=normalized, balance_score=balance_score, matches=matches)

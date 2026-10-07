"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/scoring.py

Scan permitted DNA strands and score the weakest desired or avoidance requirement.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import math
from collections import OrderedDict
from typing import Literal

from motif_balance.compile import CompiledMotif, CompiledProblem
from motif_balance.constants import DNA_ALPHABET, DNA_COMPLEMENT
from motif_balance.errors import InvalidSequence
from motif_balance.model import Evaluation, MotifMatch

_BASE_INDEX: dict[str, int] = {base: index for index, base in enumerate(DNA_ALPHABET)}
_ENCODE = bytes.maketrans(b"ACGT", bytes(range(4)))
_ENCODED_COMPLEMENT = bytes.maketrans(bytes(range(4)), bytes((3, 2, 1, 0)))
_TIE_EPSILON = 1.0e-12
_ATTAINMENT_TOLERANCE = 1.0e-12


def reverse_complement(sequence: str) -> str:
    return sequence.translate(DNA_COMPLEMENT)[::-1]


def _window_score(window: str, motif: CompiledMotif) -> float:
    return sum(
        float(motif.log_odds[position, _BASE_INDEX[base]]) for position, base in enumerate(window)
    )


def _best_match(
    sequence: str, motif: CompiledMotif, *, both_strands: bool, direction: Literal["seek", "avoid"]
) -> MotifMatch:
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
    normalized = (raw_score - motif.score_min) / (motif.score_max - motif.score_min)
    if normalized < -_ATTAINMENT_TOLERANCE or normalized > 1.0 + _ATTAINMENT_TOLERANCE:
        raise ValueError(
            f"relative PWM attainment for motif '{motif.model.motif_id}' is outside "
            "the attainable range"
        )
    if normalized < 0.0:
        normalized = 0.0
    elif normalized > 1.0:
        normalized = 1.0
    return MotifMatch(
        motif_id=motif.model.motif_id,
        start=start,
        end=start + width,
        strand=strand,
        matched_sequence=motif_oriented,
        raw_score=raw_score,
        normalized_score=normalized,
        spec_direction=direction,
        spec_satisfaction=normalized if direction == "seek" else 1.0 - normalized,
    )


def _normalize_sequence(sequence: str, problem: CompiledProblem) -> str:
    if not isinstance(sequence, str):
        raise InvalidSequence(
            "sequence must be a DNA string",
            field="sequence",
            hint="Pass nucleotide letters as text, for example 'ACGT'.",
        )
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
    return normalized


def evaluate(sequence: str, problem: CompiledProblem) -> Evaluation:
    normalized = _normalize_sequence(sequence, problem)
    matches = tuple(
        _best_match(
            normalized, motif, both_strands=problem.spec.strands == "both", direction=direction
        )
        for motif, direction in zip(
            problem.motifs, problem.spec.specification_directions, strict=True
        )
    )
    balance_score = min(match.spec_satisfaction for match in matches)
    if not math.isfinite(balance_score):
        raise ValueError("evaluation produced a nonfinite balance score")
    return Evaluation(
        sequence=normalized,
        balance_score=balance_score,
        matches=matches,
    )


class _PreparedScorer:
    """Score one compiled request with a bounded cache of immutable results.

    Preparing Python floats avoids repeated array indexing and conversion. Window
    sums retain the reference's column order, and sites retain its sequential tie
    rule. The FIFO caches share a conservative entry allowance of 4 MiB; that is
    separate from total process memory. Their lifetime is one search.
    """

    def __init__(self, problem: CompiledProblem, *, cache_bytes: int = 4 * 1024 * 1024):
        if type(cache_bytes) is not int or cache_bytes < 0:
            raise ValueError("cache allowance must be a nonnegative integer")
        self.problem = problem
        self.rows = tuple(
            tuple(tuple(float(x) for x in row) for row in motif.log_odds)
            for motif in problem.motifs
        )
        self.cache: OrderedDict[tuple[int, bytes], float] = OrderedDict()
        self.cache_limit = cache_bytes // 2
        self.window_bytes = 0
        self.evaluation_cache: OrderedDict[str, Evaluation] = OrderedDict()
        self.evaluation_cache_limit = cache_bytes - self.cache_limit
        self.evaluation_bytes = 0
        self.evaluation_cache_hits = 0
        self.evaluation_size = (
            768
            + problem.spec.length
            + sum(1536 + m.model.width + len(m.model.motif_id) for m in problem.motifs)
        )
        self.cache_hits = 0
        self.window_evaluations = 0

    @property
    def cache_bytes_used(self) -> int:
        return self.window_bytes + self.evaluation_bytes

    def _score(self, index: int, rows: tuple[tuple[float, ...], ...], word: bytes) -> float:
        key = (index, word)
        result = self.cache.get(key)
        if result is not None:
            self.cache_hits += 1
            return result
        result = sum(row[base] for row, base in zip(rows, word, strict=True))
        self.window_evaluations += 1
        cost = 320 + len(word)
        if cost <= self.cache_limit:
            while self.window_bytes + cost > self.cache_limit:
                old, _ = self.cache.popitem(last=False)
                self.window_bytes -= 320 + len(old[1])
            self.cache[key] = result
            self.window_bytes += cost
        return result

    def __call__(self, sequence: str) -> Evaluation:
        normalized = _normalize_sequence(sequence, self.problem)
        cached = self.evaluation_cache.get(normalized)
        if cached is not None:
            self.evaluation_cache_hits += 1
            return cached
        forward = normalized.encode("ascii").translate(_ENCODE)
        backward = forward.translate(_ENCODED_COMPLEMENT)[::-1]
        both = self.problem.spec.strands == "both"
        length = len(forward)
        matches = []
        for index, (motif, rows, direction) in enumerate(
            zip(
                self.problem.motifs,
                self.rows,
                self.problem.spec.specification_directions,
                strict=True,
            )
        ):
            width = motif.model.width
            best_raw = -math.inf
            best_start = 0
            best_strand: Literal["+", "-"] = "+"
            # Increasing start, then forward before reverse, is the tie preference.
            # Updating only on a strict improvement preserves the sequential rule.
            for start in range(length - width + 1):
                raw = self._score(index, rows, forward[start : start + width])
                if raw > best_raw + _TIE_EPSILON:
                    best_raw, best_start, best_strand = raw, start, "+"
                if both:
                    offset = length - start - width
                    raw = self._score(index, rows, backward[offset : offset + width])
                    if raw > best_raw + _TIE_EPSILON:
                        best_raw, best_start, best_strand = raw, start, "-"
            q = (best_raw - motif.score_min) / (motif.score_max - motif.score_min)
            if not -_ATTAINMENT_TOLERANCE <= q <= 1 + _ATTAINMENT_TOLERANCE:
                raise ValueError(
                    f"relative PWM attainment for motif '{motif.model.motif_id}' is outside "
                    "the attainable range"
                )
            q = min(1.0, max(0.0, q))
            word = normalized[best_start : best_start + width]
            if best_strand == "-":
                word = reverse_complement(word)
            matches.append(
                MotifMatch(
                    motif_id=motif.model.motif_id,
                    start=best_start,
                    end=best_start + width,
                    strand=best_strand,
                    matched_sequence=word,
                    raw_score=best_raw,
                    normalized_score=q,
                    spec_direction=direction,
                    spec_satisfaction=q if direction == "seek" else 1 - q,
                )
            )
        result = Evaluation(
            sequence=normalized,
            balance_score=min(m.spec_satisfaction for m in matches),
            matches=tuple(matches),
        )
        if self.evaluation_size <= self.evaluation_cache_limit:
            while self.evaluation_bytes + self.evaluation_size > self.evaluation_cache_limit:
                self.evaluation_cache.popitem(last=False)
                self.evaluation_bytes -= self.evaluation_size
            self.evaluation_cache[normalized] = result
            self.evaluation_bytes += self.evaluation_size
        return result

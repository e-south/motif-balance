from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

import numpy as np

from motif_balance.constants import OBJECTIVE_SEMANTICS, SCORING_SEMANTICS, TIE_BREAK_SEMANTICS
from motif_balance.errors import IncompatibleDesign
from motif_balance.model import DesignSpec, MotifModel

_LOGODDS_SCALE = 1000.0 / math.log(2.0)


@dataclass(frozen=True, slots=True)
class CompiledMotif:
    model: MotifModel
    log_odds: np.ndarray
    null_mean: float
    consensus_score: float

    @property
    def normalization_denominator(self) -> float:
        return self.consensus_score - self.null_mean


@dataclass(frozen=True, slots=True)
class CompiledProblem:
    spec: DesignSpec
    motifs: tuple[CompiledMotif, ...]
    problem_id: str


def _null_mean(log_odds: np.ndarray, background: np.ndarray) -> float:
    discretized = np.round(log_odds * _LOGODDS_SCALE).astype(np.int64)
    distribution: dict[int, float] = {0: 1.0}
    for row in discretized:
        updated: dict[int, float] = {}
        for accumulated, probability in distribution.items():
            for value, base_probability in zip(row, background, strict=True):
                score = accumulated + int(value)
                updated[score] = updated.get(score, 0.0) + probability * float(base_probability)
        distribution = updated
    return sum(
        (score / _LOGODDS_SCALE) * probability for score, probability in distribution.items()
    )


def _compile_motif(model: MotifModel) -> CompiledMotif:
    probabilities = np.asarray(model.probabilities, dtype=np.float64)
    background = np.asarray(model.background, dtype=np.float64)
    log_odds = np.log2(probabilities / background)
    log_odds.setflags(write=False)
    consensus_score = float(np.max(log_odds, axis=1).sum())
    null_mean = _null_mean(log_odds, background)
    compiled = CompiledMotif(
        model=model,
        log_odds=log_odds,
        null_mean=null_mean,
        consensus_score=consensus_score,
    )
    if not math.isfinite(compiled.normalization_denominator) or (
        compiled.normalization_denominator <= 0.0
    ):
        raise IncompatibleDesign(
            f"Motif '{model.motif_id}' has a nonpositive normalization denominator.",
            motif_id=model.motif_id,
            hint="Use an informative motif whose consensus differs from its null expectation.",
        )
    return compiled


def _problem_id(spec: DesignSpec) -> str:
    payload = {
        "motifs": [motif.model_digest for motif in spec.motifs],
        "length": spec.length,
        "strands": spec.strands,
        "scoring_semantics": SCORING_SEMANTICS,
        "objective_semantics": OBJECTIVE_SEMANTICS,
        "tie_break_semantics": TIE_BREAK_SEMANTICS,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return f"problem-{digest[:24]}"


def compile_design(spec: DesignSpec) -> CompiledProblem:
    if any(motif.width > spec.length for motif in spec.motifs):
        widest = max(spec.motifs, key=lambda motif: motif.width)
        raise IncompatibleDesign(
            f"Motif '{widest.motif_id}' is wider than the requested sequence length.",
            field="length",
            motif_id=widest.motif_id,
            hint="Increase length or supply a narrower canonical motif model.",
        )
    digests = [motif.model_digest for motif in spec.motifs]
    if len(digests) != len(set(digests)):
        raise IncompatibleDesign(
            "The design contains duplicate canonical motif models.",
            field="motifs",
            hint="Remove the duplicate model or provide scientifically distinct models.",
        )
    sequence_space = 4**spec.length
    if spec.count > sequence_space:
        raise IncompatibleDesign(
            "The requested candidate count exceeds the complete sequence space.",
            field="count",
            hint="Reduce count or increase sequence length.",
        )
    compiled = tuple(_compile_motif(motif) for motif in spec.motifs)
    return CompiledProblem(spec=spec, motifs=compiled, problem_id=_problem_id(spec))

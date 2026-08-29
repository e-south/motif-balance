from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

import numpy as np

from motif_balance.errors import IncompatibleDesign
from motif_balance.model import DesignSpec, MotifModel

_LOGODDS_SCALE = 1000.0 / math.log(2.0)


@dataclass(frozen=True, slots=True)
class CompiledMotif:
    model: MotifModel
    log_odds: np.ndarray
    null_mean: float
    consensus_score: float
    score_min: float
    score_max: float
    probability_consensus: str
    score_maximizing_sequence: str

    @property
    def normalization_denominator(self) -> float:
        if self.model.schema_version == "motif-model/v1":
            return self.consensus_score - self.null_mean
        return self.score_max - self.score_min


@dataclass(frozen=True, slots=True)
class CompiledProblem:
    spec: DesignSpec
    motifs: tuple[CompiledMotif, ...]
    problem_id: str


def sequence_space_at_most(length: int, limit: int) -> int | None:
    """Return 4**length only when it is no greater than a trusted bound."""

    if limit < 1:
        return None
    sequence_space = 1
    for _ in range(length):
        if sequence_space > limit // 4:
            return None
        sequence_space *= 4
    return sequence_space


def planned_search_kind(spec: DesignSpec) -> str:
    """Return the bounded search classification used by preflight surfaces."""

    return (
        "exhaustive"
        if sequence_space_at_most(spec.length, spec.evaluations) is not None
        else "annealed"
    )


def build_run_id(
    spec: DesignSpec,
    problem_id: str,
    engine: str,
    engine_version: str,
    *,
    package_version: str,
) -> str:
    """Bind the complete run contract without coupling it to publication code."""

    payload = {
        "problem_id": problem_id,
        "count": spec.count,
        "min_distance": spec.min_distance,
        "evaluations": spec.evaluations,
        "seed": spec.seed,
        "search_engine": engine,
        "search_engine_version": engine_version,
        "package_version": package_version,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return f"run-{digest[:24]}"


def _null_mean(log_odds: np.ndarray, background: np.ndarray) -> float:
    discretized = np.round(log_odds * _LOGODDS_SCALE).astype(np.int64)
    return float(
        np.sum(
            discretized * background[np.newaxis, :],
            dtype=np.float64,
        )
        / _LOGODDS_SCALE
    )


def _compile_motif(model: MotifModel) -> CompiledMotif:
    probabilities = np.asarray(model.probabilities, dtype=np.float64)
    background = np.asarray(model.background, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        log_odds = np.log2(probabilities / background)
    if not np.all(np.isfinite(log_odds)):
        raise IncompatibleDesign(
            f"Motif '{model.motif_id}' produces non-finite log-odds values.",
            motif_id=model.motif_id,
            hint="Use finite probabilities and background values with a numerically stable ratio.",
        )
    log_odds.setflags(write=False)
    consensus_score = float(np.max(log_odds, axis=1).sum())
    score_min = math.fsum(float(np.min(row)) for row in log_odds)
    score_max = math.fsum(float(np.max(row)) for row in log_odds)
    probability_consensus = "".join(
        "ACGT"[int(index)] for index in np.argmax(probabilities, axis=1)
    )
    score_maximizing_sequence = "".join("ACGT"[int(index)] for index in np.argmax(log_odds, axis=1))
    null_mean = _null_mean(log_odds, background)
    compiled = CompiledMotif(
        model=model,
        log_odds=log_odds,
        null_mean=null_mean,
        consensus_score=consensus_score,
        score_min=score_min,
        score_max=score_max,
        probability_consensus=probability_consensus,
        score_maximizing_sequence=score_maximizing_sequence,
    )
    if not math.isfinite(compiled.normalization_denominator) or (
        compiled.normalization_denominator <= 0.0
    ):
        raise IncompatibleDesign(
            f"Motif '{model.motif_id}' has a nonpositive normalization denominator.",
            motif_id=model.motif_id,
            hint="Use an informative motif whose attainable raw LLR range is positive.",
        )
    return compiled


def _problem_id(spec: DesignSpec) -> str:
    payload = {
        "motifs": [
            {"motif_id": motif.motif_id, "model_digest": motif.model_digest}
            for motif in spec.motifs
        ],
        "length": spec.length,
        "strands": spec.strands,
        "scoring_semantics": spec.scoring_semantics,
        "objective_semantics": spec.objective_semantics,
        "tie_break_semantics": spec.tie_break_semantics,
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
    if sequence_space_at_most(spec.length, spec.count - 1) is not None:
        raise IncompatibleDesign(
            "The requested candidate count exceeds the complete sequence space.",
            field="count",
            hint="Reduce count or increase sequence length.",
        )
    compiled = tuple(_compile_motif(motif) for motif in spec.motifs)
    return CompiledProblem(spec=spec, motifs=compiled, problem_id=_problem_id(spec))

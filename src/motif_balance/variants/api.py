"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/variants/api.py

Diversify a selected DNA sequence without changing its selected desired sites.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import math
from itertools import product
from typing import Any, Literal, cast

from motif_balance.compile import compile_scoring
from motif_balance.constants import BUILD_LOCK_SHA256, PACKAGE_VERSION, RUNTIME_CONTRACT
from motif_balance.formats.structured import load_json_unique
from motif_balance.model import DesignSpec, Evaluation
from motif_balance.model.variants import IUPAC, Substitution, VariantLibrary, VariantVerification
from motif_balance.scoring import evaluate

# Admission bounds account for all attempted product expansions, separately from search.
_MAX_SCORE_OPERATIONS = 1_000_000_000
_MAX_CACHE_BASES = 32_000_000
_MAX_DIAGNOSTIC_MATCHES = 50_000
_MAX_HANDOFF_BYTES = 64_000_000


def _changes(parent: Evaluation, variant: Evaluation) -> tuple[tuple[float, ...], tuple[str, ...]]:
    changes = tuple(
        m.spec_satisfaction - p.spec_satisfaction
        for p, m in zip(parent.matches, variant.matches, strict=True)
    )
    moved = tuple(
        p.motif_id
        for p, m in zip(parent.matches, variant.matches, strict=True)
        if p.spec_direction == "seek" and (p.start, p.end, p.strand) != (m.start, m.end, m.strand)
    )
    return changes, moved


def _status(
    changes: tuple[float, ...], moved: tuple[str, ...], loss: float
) -> Literal["passes_alone", "site_changed", "score_loss"]:
    if moved:
        return "site_changed"
    return "score_loss" if min(changes) < -loss - 1e-12 else "passes_alone"


def diversify(
    sequence: str,
    spec: DesignSpec,
    *,
    max_score_loss: float = 0.02,
    max_variants: int = 256,
    editable_mask: tuple[bool, ...] | None = None,
) -> VariantLibrary:
    """Return a deterministic Cartesian library, checking every encoded sequence.

    Desired sites must retain their selected coordinates and strand. Each desired
    score may fall by at most ``max_score_loss``; each unwanted model's strongest
    score may rise by at most that amount. Comparisons allow 1e-12 roundoff.
    The parent counts toward the cap. The default editable mask covers desired
    selected sites; an explicit boolean tuple can include other positions.
    """
    if type(max_variants) is not int or not 1 <= max_variants <= 256:
        raise ValueError("max_variants must be an integer from 1 through 256")
    if (
        isinstance(max_score_loss, bool)
        or not isinstance(max_score_loss, (int, float))
        or not (math.isfinite(max_score_loss) and 0 <= max_score_loss <= 1)
    ):
        raise ValueError("max_score_loss must be finite and between zero and one")
    if editable_mask is not None and (
        not isinstance(editable_mask, tuple)
        or len(editable_mask) != spec.length
        or any(type(value) is not bool for value in editable_mask)
    ):
        raise ValueError("editable_mask must be a boolean tuple with one entry per DNA position")
    problem = compile_scoring(spec)
    if not any(direction == "seek" for direction in spec.specification_directions):
        raise ValueError("diversification requires at least one desired motif")
    parent = evaluate(sequence, problem)
    sequence = parent.sequence
    positions = tuple(
        i
        for i in range(spec.length)
        if (
            editable_mask[i]
            if editable_mask is not None
            else any(m.spec_direction == "seek" and m.start <= i < m.end for m in parent.matches)
        )
    )
    operation_cost = sum(m.model.width * (spec.length - m.model.width + 1) for m in problem.motifs)
    operation_cost *= 2 if spec.strands == "both" else 1
    upper_evaluations = 1 + 3 * len(positions) * max_variants
    if (
        upper_evaluations * operation_cost > _MAX_SCORE_OPERATIONS
        or upper_evaluations * spec.length > _MAX_CACHE_BASES
        or (3 * len(positions) + max_variants) * len(parent.matches) > _MAX_DIAGNOSTIC_MATCHES
    ):
        raise ValueError(
            "diversification exceeds bounded work or record limits; reduce "
            "max_variants or the editable mask"
        )
    substitutions = []
    # Retain full records only for diagnostics and the small accepted library.
    # Rejected combination results need only a boolean for subsequent cache hits.
    passing = {sequence: True}
    evaluations_used = 1
    for position in positions:
        for base in "ACGT":
            if base == sequence[position]:
                continue
            changed = sequence[:position] + base + sequence[position + 1 :]
            evaluation = evaluate(changed, problem)
            evaluations_used += 1
            changes, moved = _changes(parent, evaluation)
            status = _status(changes, moved, float(max_score_loss))
            passing[changed] = status == "passes_alone"
            substitutions.append(
                Substitution(
                    position=position,
                    parent_base=cast(Literal["A", "C", "G", "T"], sequence[position]),
                    base=cast(Literal["A", "C", "G", "T"], base),
                    evaluation=evaluation,
                    component_changes=changes,
                    changed_desired_sites=moved,
                    status=status,
                )
            )
    candidates = sorted(
        (s for s in substitutions if s.status == "passes_alone"),
        key=lambda s: (max(0.0, -min(s.component_changes)), s.position, s.base),
    )
    diagnostic_records = {s.evaluation.sequence: s.evaluation for s in substitutions}
    accepted = {sequence: parent}
    allowed = list(sequence)
    size_rejected = score_rejected = 0
    for substitution in candidates:
        position, base = substitution.position, substitution.base
        new_size = len(accepted) // len(allowed[position]) * (len(allowed[position]) + 1)
        if new_size > max_variants:
            size_rejected += 1
            continue
        choices = list(allowed)
        choices[position] = base  # Only newly introduced combinations need checking.
        introduced: dict[str, Evaluation] = {}
        for bases in product(*choices):
            variant = "".join(bases)
            if variant in passing and not passing[variant]:
                break
            record = diagnostic_records.get(variant)
            if record is None:
                record = evaluate(variant, problem)
                evaluations_used += 1
                changes, moved = _changes(parent, record)
                passing[variant] = _status(changes, moved, float(max_score_loss)) == "passes_alone"
            if not passing[variant]:
                break
            introduced[variant] = record
        else:
            accepted.update(introduced)
            allowed[position] = "".join(sorted(allowed[position] + base))
            continue
        score_rejected += 1
    variants = (parent, *(accepted[s] for s in sorted(accepted) if s != sequence))
    return VariantLibrary(
        package_version=PACKAGE_VERSION,
        runtime_contract=RUNTIME_CONTRACT,
        build_lock_sha256=BUILD_LOCK_SHA256,
        problem_id=problem.problem_id,
        spec=problem.spec,
        parent=parent,
        max_score_loss=float(max_score_loss),
        max_variants=max_variants,
        editable_positions=positions,
        allowed_bases=tuple(allowed),
        template="".join(IUPAC[b] for b in allowed),
        variants=variants,
        substitutions=tuple(substitutions),
        verification=VariantVerification(
            encoded_sequence_count=len(variants),
            maximum_component_loss=max(
                0.0,
                *(
                    p.spec_satisfaction - m.spec_satisfaction
                    for v in variants
                    for p, m in zip(parent.matches, v.matches, strict=True)
                ),
            ),
            minimum_balance=min(v.balance_score for v in variants),
            outcome="parent_only" if len(variants) == 1 else "diversified",
        ),
        evaluations_used=evaluations_used,
        score_operations=evaluations_used * operation_cost,
        size_rejected_expansions=size_rejected,
        score_rejected_expansions=score_rejected,
        stop_reason="size_cap" if size_rejected else "no_further_passing_expansion",
    )


def _replay_equal(recorded: Any, replayed: Any) -> bool:
    if isinstance(recorded, float) and isinstance(replayed, float):
        return math.isclose(recorded, replayed, rel_tol=0.0, abs_tol=1e-12)
    if isinstance(recorded, dict) and isinstance(replayed, dict):
        return recorded.keys() == replayed.keys() and all(
            _replay_equal(value, replayed[key]) for key, value in recorded.items()
        )
    if isinstance(recorded, list) and isinstance(replayed, list):
        return len(recorded) == len(replayed) and all(
            _replay_equal(a, b) for a, b in zip(recorded, replayed, strict=True)
        )
    return bool(recorded == replayed)


def verify_library(library: VariantLibrary) -> VariantLibrary:
    """Replay construction and check scores, selected sites, decisions, and effort.

    Producer version and lock are retained as declarations, not authenticated
    provenance. Numerical fields permit 1e-12 absolute roundoff; structural
    fields and all counters must match exactly. Replay has the same admission
    bounds as construction and does not rerun the original design search.
    """
    replay = diversify(
        library.parent.sequence,
        library.spec,
        max_score_loss=library.max_score_loss,
        max_variants=library.max_variants,
        editable_mask=tuple(i in library.editable_positions for i in range(library.spec.length)),
    )
    declarations = {"package_version", "build_lock_sha256"}
    recorded = library.model_dump(mode="json", exclude=declarations)
    expected = replay.model_dump(mode="json", exclude=declarations)
    if not _replay_equal(recorded, expected):
        raise ValueError("library records disagree with deterministic diversification replay")
    return library


def load_library(raw: str | bytes) -> VariantLibrary:
    """Load a bounded JSON handoff and verify it against the authoritative scorer."""
    if not isinstance(raw, (str, bytes)):
        raise TypeError("library JSON must be text or bytes")
    if len(raw) > _MAX_HANDOFF_BYTES:
        raise ValueError("library JSON exceeds the byte limit")
    encoded = raw.encode("utf-8") if isinstance(raw, str) else raw
    if len(encoded) > _MAX_HANDOFF_BYTES:
        raise ValueError("library JSON exceeds the byte limit")
    return verify_library(VariantLibrary.model_validate(load_json_unique(encoded)))

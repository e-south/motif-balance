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

import hashlib
import json
import math
from itertools import product
from typing import Any, Literal, cast

from motif_balance.compile import CompiledProblem, compile_scoring
from motif_balance.constants import BUILD_LOCK_SHA256, PACKAGE_VERSION, RUNTIME_CONTRACT
from motif_balance.formats.structured import load_json_unique
from motif_balance.model import DesignSpec, Evaluation
from motif_balance.model.variants import (
    IUPAC,
    ExpansionRejections,
    Substitution,
    VariantLibrary,
    VariantVerification,
    quality_status,
)
from motif_balance.scoring import evaluate

from .bounds import fixed_site_quality_failure

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


def _prepare(
    sequence: str,
    spec: DesignSpec,
    *,
    max_score_loss: float | None,
    min_balance: float | None,
    max_variants: int,
    editable_mask: tuple[bool, ...] | None,
    construction_order: str,
) -> tuple[CompiledProblem, Evaluation, tuple[int, ...], int, int, float | None]:
    if type(max_variants) is not int or not 1 <= max_variants <= 1024:
        raise ValueError("max_variants must be an integer from 1 through 1024")
    if max_score_loss is not None and min_balance is not None:
        raise ValueError("specify either max_score_loss or min_balance, not both")
    if max_score_loss is None and min_balance is None:
        max_score_loss = 0.02
    for name, value in (("max_score_loss", max_score_loss), ("min_balance", min_balance)):
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not (math.isfinite(value) and 0 <= value <= 1)
        ):
            raise ValueError(f"{name} must be finite and between zero and one")
    if construction_order not in ("least_loss", "greatest_loss", "hashed"):
        raise ValueError("construction_order must be least_loss, greatest_loss, or hashed")
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
    if min_balance is not None and parent.balance_score < min_balance - 1e-12:
        raise ValueError(
            f"parent balance {parent.balance_score:.6g} is below floor {min_balance:g}"
        )
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
    return problem, parent, positions, operation_cost, upper_evaluations, max_score_loss


def diversify(
    sequence: str,
    spec: DesignSpec,
    *,
    max_score_loss: float | None = None,
    min_balance: float | None = None,
    construction_order: Literal["least_loss", "greatest_loss", "hashed"] = "least_loss",
    max_variants: int = 256,
    editable_mask: tuple[bool, ...] | None = None,
) -> VariantLibrary:
    """Return a deterministic Cartesian library, checking every encoded sequence.

    Desired sites must retain their selected coordinates and strand. Each desired
    score may fall by at most ``max_score_loss`` (default 0.02); each unwanted model's strongest
    score may rise by at most that amount. Comparisons allow 1e-12 roundoff.
    Alternatively, ``min_balance`` requires an absolute objective floor, without
    a parental-loss restriction. These controls are mutually exclusive. The
    construction order affects the greedy product and does not guarantee its maximum size.
    The parent counts toward the cap. The default editable mask covers desired
    selected sites; an explicit boolean tuple can include other positions.
    """
    return _construct(
        sequence,
        spec,
        max_score_loss=max_score_loss,
        min_balance=min_balance,
        construction_order=construction_order,
        max_variants=max_variants,
        editable_mask=editable_mask,
    )


def _construct(
    sequence: str,
    spec: DesignSpec,
    *,
    max_score_loss: float | None = None,
    min_balance: float | None = None,
    construction_order: Literal["least_loss", "greatest_loss", "hashed"] = "least_loss",
    max_variants: int = 256,
    editable_mask: tuple[bool, ...] | None = None,
    _use_precheck: bool = True,
) -> VariantLibrary:
    """Return a deterministic Cartesian library, checking every encoded sequence.

    Desired sites must retain their selected coordinates and strand. Each desired
    score may fall by at most ``max_score_loss`` (default 0.02); each unwanted model's strongest
    score may rise by at most that amount. Comparisons allow 1e-12 roundoff.
    Alternatively, ``min_balance`` requires an absolute objective floor, without
    a parental-loss restriction. These controls are mutually exclusive. The
    construction order affects the greedy product and does not guarantee its maximum size.
    The parent counts toward the cap. The default editable mask covers desired
    selected sites; an explicit boolean tuple can include other positions.
    """
    problem, parent, positions, operation_cost, _, max_score_loss = _prepare(
        sequence,
        spec,
        max_score_loss=max_score_loss,
        min_balance=min_balance,
        max_variants=max_variants,
        editable_mask=editable_mask,
        construction_order=construction_order,
    )
    sequence = parent.sequence
    substitutions = []
    # Retain full records only for diagnostics and the small accepted library.
    # Rejected combination results need only a boolean for subsequent cache hits.
    passing = {sequence: "passes_alone"}
    evaluations_used = 1
    for position in positions:
        for base in "ACGT":
            if base == sequence[position]:
                continue
            changed = sequence[:position] + base + sequence[position + 1 :]
            evaluation = evaluate(changed, problem)
            evaluations_used += 1
            changes, moved = _changes(parent, evaluation)
            status = quality_status(
                changes, moved, evaluation.balance_score, max_score_loss, min_balance
            )
            passing[changed] = status
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
    if construction_order == "greatest_loss":
        candidates.reverse()
    elif construction_order == "hashed":
        common = {
            "policy": "motif-expansion-order/v1",
            "sequence": sequence,
            "models": [
                (hashlib.sha256(s.motif.model_dump_json().encode()).hexdigest(), s.direction)
                for s in spec.specifications
            ],
            "strands": spec.strands,
            "editable_positions": positions,
        }
        candidates.sort(
            key=lambda s: (
                hashlib.sha256(
                    json.dumps(
                        {**common, "position": s.position, "base": s.base},
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest(),
                s.position,
                s.base,
            )
        )
    diagnostic_records = {s.evaluation.sequence: s.evaluation for s in substitutions}
    accepted = {sequence: parent}
    allowed = list(sequence)
    size_rejected = score_rejected = 0
    quality_rejected = site_rejected = prechecked = 0
    for substitution in candidates:
        position, base = substitution.position, substitution.base
        new_size = len(accepted) // len(allowed[position]) * (len(allowed[position]) + 1)
        if new_size > max_variants:
            size_rejected += 1
            continue
        choices = list(allowed)
        choices[position] = base  # Only newly introduced combinations need checking.
        if _use_precheck and fixed_site_quality_failure(
            choices, parent, problem, max_score_loss, min_balance
        ):
            score_rejected += 1
            quality_rejected += 1
            prechecked += 1
            continue
        introduced: dict[str, Evaluation] = {}
        for bases in product(*choices):
            variant = "".join(bases)
            if variant in passing and passing[variant] != "passes_alone":
                break
            record = diagnostic_records.get(variant)
            if record is None:
                record = evaluate(variant, problem)
                evaluations_used += 1
                changes, moved = _changes(parent, record)
                passing[variant] = quality_status(
                    changes, moved, record.balance_score, max_score_loss, min_balance
                )
            if passing[variant] != "passes_alone":
                break
            introduced[variant] = record
        else:
            accepted.update(introduced)
            allowed[position] = "".join(sorted(allowed[position] + base))
            continue
        score_rejected += 1
        if passing[variant] == "site_changed":
            site_rejected += 1
        else:
            quality_rejected += 1
    variants = (parent, *(accepted[s] for s in sorted(accepted) if s != sequence))
    return VariantLibrary(
        schema_version="variant-library/v3" if _use_precheck else "variant-library/v2",
        algorithm="greedy_product_checked_v3" if _use_precheck else "greedy_product_checked_v2",
        rejections=ExpansionRejections(
            size_limit=size_rejected,
            quality=quality_rejected,
            selected_site=site_rejected,
            quality_precheck=prechecked,
        )
        if _use_precheck
        else None,
        package_version=PACKAGE_VERSION,
        runtime_contract=RUNTIME_CONTRACT,
        build_lock_sha256=BUILD_LOCK_SHA256,
        problem_id=problem.problem_id,
        spec=problem.spec,
        parent=parent,
        max_score_loss=None if max_score_loss is None else float(max_score_loss),
        min_balance=None if min_balance is None else float(min_balance),
        construction_order=construction_order,
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
    # Parsed models can be copied without validation; admit the full record before replay.
    library = VariantLibrary.model_validate(library.model_dump(mode="python", warnings=False))
    replay = _construct(
        library.parent.sequence,
        library.spec,
        _use_precheck=library.algorithm == "greedy_product_checked_v3",
        max_score_loss=library.max_score_loss,
        min_balance=library.min_balance,
        construction_order=library.construction_order,
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

"""Exact local-regret assessment for two to four desired motifs.

Maintainer(s): Eric J. South, Dunlop Lab
"""

from __future__ import annotations

from itertools import product
from typing import Literal

import numpy as np

from motif_balance.constants import (
    MAX_JOINT_ASSESSMENT_ARRANGEMENTS,
    MAX_JOINT_ASSESSMENT_BASE_OPERATIONS,
    MAX_JOINT_ASSESSMENT_MOTIFS,
    MAX_SEQUENCE_LENGTH,
)
from motif_balance.errors import IncompatibleDesign
from motif_balance.model import MotifModel
from motif_balance.model.assessment import (
    JointArrangement,
    JointAssessment,
    joint_assessment_work_bound,
)

from .terms import column_regret


def assess_motifs(
    models: tuple[MotifModel, ...],
    *,
    length: int,
    strands: Literal["forward", "both"] = "both",
) -> JointAssessment:
    """Exactly minimize local conflict for two to four labeled desired motifs.

    Enumerates each legal translation class once, fixing the first model forward
    only when whole-duplex reversal is permitted. Returns one deterministic best
    arrangement, not a sequence, whole-motif optimum, or collection prediction.
    Work exceeding either public bound is refused before matrix compilation.
    """
    if not isinstance(models, tuple) or not 2 <= len(models) <= MAX_JOINT_ASSESSMENT_MOTIFS:
        raise IncompatibleDesign(
            "joint assessment requires a tuple of two to four MotifModel values"
        )
    if any(not isinstance(m, MotifModel) or m.schema_version != "motif-model/v2" for m in models):
        raise IncompatibleDesign("joint assessment requires validated motif-model/v2 inputs")
    if len({m.motif_id for m in models}) != len(models):
        raise IncompatibleDesign("joint assessment requires distinct motif identities")
    widths = tuple(m.width for m in models)
    if type(length) is not int or not max(widths) <= length <= MAX_SEQUENCE_LENGTH:
        raise IncompatibleDesign(
            "joint assessment length must contain every complete motif window", field="length"
        )
    if strands not in ("forward", "both"):
        raise IncompatibleDesign("strands must be forward or both", field="strands")
    count, operations = joint_assessment_work_bound(widths, length, strands)
    if (
        count > MAX_JOINT_ASSESSMENT_ARRANGEMENTS
        or operations > MAX_JOINT_ASSESSMENT_BASE_OPERATIONS
    ):
        raise IncompatibleDesign(
            "joint assessment exceeds its arrangement or base-operation limit",
            hint="Use fewer motifs or a smaller length; no arrangements have been calculated.",
        )
    terms = tuple(column_regret(m) for m in models)
    weight = sum(t[1] for t in terms)
    if weight <= 0:
        raise IncompatibleDesign("joint assessment requires positive effective information")
    orientation_choices: tuple[Literal["+", "-"], ...] = (
        ("+",) if strands == "forward" else ("+", "-")
    )
    best: tuple[float, tuple[int, ...], tuple[Literal["+", "-"], ...]] | None = None
    visited = 0
    for tail in product(orientation_choices, repeat=len(models) - 1):
        orientation: tuple[Literal["+", "-"], ...] = ("+", *tail)
        regrets = tuple(
            t[0] if s == "+" else t[0][::-1, ::-1] for t, s in zip(terms, orientation, strict=True)
        )
        # The first zero start partitions normalized translations without walking
        # the much larger unnormalized Cartesian placement space.
        for anchor in range(len(models)):
            ranges = tuple(
                range(1) if i == anchor else range(1 if i < anchor else 0, length - width + 1)
                for i, width in enumerate(widths)
            )
            for starts in product(*ranges):
                shared = np.zeros((length, 4))
                for start, width, regret in zip(starts, widths, regrets, strict=True):
                    shared[start : start + width] += regret
                # One physical base must serve every motif covering this coordinate.
                loss = float(shared.min(axis=1).sum())
                key = (loss, starts, orientation)
                if best is None or key < best:
                    best = key
                visited += 1
    if best is None or visited != count:
        raise RuntimeError("joint enumeration differs from its admitted arrangement count")
    return JointAssessment(
        length=length,
        strands=strands,
        motifs=tuple(t[2] for t in terms),
        equivalence="translation" if strands == "forward" else "translation_and_reverse_complement",
        effective_information_bits=2 * weight,
        base_operation_upper_bound=operations,
        arrangement_count=count,
        structural_score=float(np.clip(1 - best[0] / weight, 0, 1)),
        best_arrangement=JointArrangement(starts=best[1], strands=best[2]),
    )

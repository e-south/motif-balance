"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/variants/bounds.py

Necessary quality checks for a product whose desired sites must stay selected.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from motif_balance.compile import CompiledProblem
from motif_balance.model import Evaluation

_COMPLEMENT = str.maketrans("ACGT", "TGCA")


def fixed_site_quality_failure(
    choices: list[str],
    parent: Evaluation,
    problem: CompiledProblem,
    max_score_loss: float | None,
    min_balance: float | None,
) -> bool:
    """Reject only when a desired fixed site necessarily fails in some member.

    This is not a certificate that the site remains the best match. Avoidance
    and competing windows still require full rescanning. A small guard beyond
    the scorer's acceptance tolerance leaves boundary decisions to that scan.
    """
    for match, motif in zip(parent.matches, problem.motifs, strict=True):
        if match.spec_direction != "seek":
            continue
        if min_balance is not None:
            threshold = min_balance
        else:
            assert max_score_loss is not None
            threshold = match.spec_satisfaction - max_score_loss
        contributions = []
        for j in range(motif.model.width):
            p = match.start + j if match.strand == "+" else match.end - 1 - j
            bases = choices[p] if match.strand == "+" else choices[p].translate(_COMPLEMENT)
            contributions.append(min(float(motif.log_odds[j, "ACGT".index(b)]) for b in bases))
        minimum = (sum(contributions) - motif.score_min) / motif.normalization_denominator
        if minimum < threshold - 2e-12:
            return True
    return False

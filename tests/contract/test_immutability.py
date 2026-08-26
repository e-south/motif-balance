from __future__ import annotations

import pytest
from pydantic import ValidationError

from motif_balance import DesignSpec, design


def test_evaluated_candidates_cannot_be_mutated_without_reevaluation(
    pairwise_spec: DesignSpec,
) -> None:
    candidate = design(pairwise_spec).best

    with pytest.raises(ValidationError):
        candidate.sequence = "AAAA"
    with pytest.raises(ValidationError):
        candidate.balance_score = 1.0
    with pytest.raises(ValidationError):
        candidate.matches[0].start = 1

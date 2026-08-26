from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from motif_balance import DesignSpec, MotifModel, design
from motif_balance.api import Portfolio
from motif_balance.model import Evaluation, MotifMatch, _normalized_hamming_distance


def _motif(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "motif_id": "fixture",
        "probabilities": ((0.7, 0.1, 0.1, 0.1),),
        "background": (0.25, 0.25, 0.25, 0.25),
    }
    payload.update(updates)
    return payload


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"alphabet": ("T", "G", "C", "A")}, "alphabet"),
        ({"probabilities": ()}, "at least one"),
        ({"background": (0.0, 0.3, 0.3, 0.4)}, "positive"),
        ({"background": (0.2, 0.2, 0.2, 0.2)}, "sum to one"),
        ({"source_digest": "ABC"}, "SHA-256"),
    ],
)
def test_motif_validation_boundaries(updates: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        MotifModel.model_validate(_motif(**updates))


def test_design_validation_boundaries() -> None:
    motif = MotifModel.model_validate(_motif())
    base = {
        "motifs": (motif,),
        "length": 1,
        "count": 1,
        "evaluations": 1,
        "seed": 0,
    }

    with pytest.raises(ValidationError):
        DesignSpec.model_validate("not-a-mapping")
    with pytest.raises(ValidationError, match="keys must be strings"):
        DesignSpec.model_validate({**base, "motifs": {1: motif}})
    with pytest.raises(ValidationError, match="motif key"):
        DesignSpec.model_validate({**base, "motifs": {"fixture": "not-a-model"}})
    with pytest.raises(ValidationError, match="at least one"):
        DesignSpec.model_validate({**base, "motifs": ()})
    with pytest.raises(ValidationError, match="unique"):
        DesignSpec.model_validate({**base, "motifs": (motif, motif)})
    with pytest.raises(ValidationError, match="at least count"):
        DesignSpec.model_validate({**base, "count": 2})


def test_match_and_evaluation_validation_boundaries() -> None:
    base_match = {
        "motif_id": "fixture",
        "start": 0,
        "end": 1,
        "strand": "+",
        "matched_sequence": "A",
        "raw_score": 1.0,
        "normalized_score": 0.5,
    }
    with pytest.raises(ValidationError, match="greater than start"):
        MotifMatch.model_validate({**base_match, "start": 1, "end": 1})
    with pytest.raises(ValidationError, match="width"):
        MotifMatch.model_validate({**base_match, "end": 2})
    with pytest.raises(ValidationError, match="only A, C, G, and T"):
        MotifMatch.model_validate({**base_match, "matched_sequence": "N"})
    with pytest.raises(ValidationError, match="finite"):
        MotifMatch.model_validate({**base_match, "raw_score": math.inf})

    match = MotifMatch.model_validate(base_match)
    with pytest.raises(ValidationError, match="only A, C, G, and T"):
        Evaluation(sequence="N", balance_score=0.5, matches=(match,))
    with pytest.raises(ValidationError, match="at least one"):
        Evaluation(sequence="A", balance_score=0.5, matches=())
    with pytest.raises(ValidationError, match="weakest"):
        Evaluation(sequence="A", balance_score=0.4, matches=(match,))


def test_portfolio_validation_boundaries(pairwise_spec: DesignSpec) -> None:
    valid = design(pairwise_spec)
    payload = valid.model_dump(mode="python")

    bad_identity = {**payload, "problem_id": "problem-000000000000000000000000"}
    with pytest.raises(ValidationError, match="identities"):
        Portfolio.model_validate(bad_identity)

    with pytest.raises(ValidationError, match=r"exactly spec\.count"):
        Portfolio.model_validate({**payload, "candidates": payload["candidates"][:-1]})

    candidates = [dict(candidate) for candidate in payload["candidates"]]
    candidates[0]["rank"] = 2
    with pytest.raises(ValidationError, match="ranks"):
        Portfolio.model_validate({**payload, "candidates": candidates})

    candidates = [dict(candidate) for candidate in payload["candidates"]]
    candidates[0]["sequence"] = candidates[0]["sequence"] + "A"
    with pytest.raises(ValidationError, match="sequence length"):
        Portfolio.model_validate({**payload, "candidates": candidates})

    candidates = [dict(candidate) for candidate in payload["candidates"]]
    first_matches = [dict(match) for match in candidates[0]["matches"]]
    first_matches[0]["motif_id"] = "unknown"
    candidates[0]["matches"] = first_matches
    with pytest.raises(ValidationError, match="one match per motif"):
        Portfolio.model_validate({**payload, "candidates": candidates})

    candidates = [dict(candidate) for candidate in payload["candidates"]]
    candidates[0]["matches"] = (*candidates[0]["matches"], candidates[0]["matches"][0])
    with pytest.raises(ValidationError, match="duplicate motif"):
        Portfolio.model_validate({**payload, "candidates": candidates})

    candidates = [dict(candidate) for candidate in payload["candidates"]]
    candidates[1]["sequence"] = candidates[0]["sequence"]
    with pytest.raises(ValidationError, match="unique"):
        Portfolio.model_validate({**payload, "candidates": candidates})

    candidates = [dict(candidate) for candidate in reversed(payload["candidates"])]
    for rank, candidate in enumerate(candidates, start=1):
        candidate["rank"] = rank
    with pytest.raises(ValidationError, match="sorted"):
        Portfolio.model_validate({**payload, "candidates": candidates})

    candidates = [dict(candidate) for candidate in payload["candidates"]]
    overrun_match = dict(candidates[0]["matches"][0])
    overrun_match.update(start=0, end=pairwise_spec.length + 1, matched_sequence="A" * 5)
    candidates[0]["matches"] = (overrun_match, *candidates[0]["matches"][1:])
    with pytest.raises(ValidationError, match="coordinates exceed"):
        Portfolio.model_validate({**payload, "candidates": candidates})

    strict_spec = pairwise_spec.model_copy(update={"min_distance": 1.0})
    with pytest.raises(ValidationError, match="min_distance"):
        Portfolio.model_validate({**payload, "spec": strict_spec})

    assert len(valid.matches) == len(valid.candidates) * len(pairwise_spec.motifs)
    with pytest.raises(ValueError, match="equal, nonzero"):
        _normalized_hamming_distance("A", "AA")

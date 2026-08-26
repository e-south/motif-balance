from __future__ import annotations

import json
from pathlib import Path

import pytest

from motif_balance import DesignSpec, MotifModel, score


def test_sanitized_cruncher_sample_scoring_snapshot_is_classified() -> None:
    root = Path(__file__).resolve().parents[2]
    fixture = json.loads((root / "benchmarks/technical-note/scoring-parity-v1.json").read_text())
    input_record = fixture["input"]
    motifs = tuple(
        MotifModel(
            motif_id=motif_id,
            probabilities=tuple(tuple(row) for row in rows),
            background=tuple(input_record["background"]),
        )
        for motif_id, rows in sorted(input_record["motifs"].items())
    )
    spec = DesignSpec(
        motifs=motifs,
        length=len(input_record["sequence"]),
        count=1,
        strands=input_record["strands"],
        evaluations=1,
        seed=0,
    )

    actual = score(input_record["sequence"], spec)
    expected = fixture["legacy_output"]
    raw_tolerance = fixture["comparison"]["raw_score_tolerance"]
    normalized_tolerance = fixture["comparison"]["normalized_score_tolerance"]
    for match in actual.matches:
        legacy = expected[match.motif_id]
        assert (match.start, match.end, match.strand, match.matched_sequence) == (
            legacy["start"],
            legacy["end"],
            legacy["strand"],
            legacy["matched_sequence"],
        )
        assert match.raw_score == pytest.approx(legacy["raw_score"], abs=raw_tolerance)
        assert match.normalized_score == pytest.approx(
            legacy["normalized_score"], abs=normalized_tolerance
        )
    assert actual.balance_score == pytest.approx(
        expected["balance_score"], abs=normalized_tolerance
    )
    corrected = fixture["motif_balance_output"]
    for match in actual.matches:
        expected_match = corrected[match.motif_id]
        assert match.raw_score == pytest.approx(expected_match["raw_score"], abs=1.0e-14)
        assert match.normalized_score == pytest.approx(
            expected_match["normalized_score"], abs=1.0e-14
        )
    assert actual.balance_score == pytest.approx(corrected["balance_score"], abs=1.0e-14)
    assert actual.balance_score != expected["balance_score"]
    assert (
        fixture["comparison"]["score_difference_classification"]
        == "intentional_semantic_correction"
    )

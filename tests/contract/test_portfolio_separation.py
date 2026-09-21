"""Footprint separation is independently minimized over allowed orientations."""

from itertools import combinations, product

import pytest

from motif_balance import DesignSpec, MotifModel, MotifSpecification
from motif_balance.alternatives.geometry import pair_distances, pair_separation, prepare_distances
from motif_balance.compile import compile_scoring
from motif_balance.scoring import evaluate


def test_every_short_pair_agrees_with_a_literal_orientation_and_footprint_oracle():
    spec = DesignSpec(
        schema_version="design-spec/v3",
        length=4,
        strands="both",
        count=1,
        seed=7,
        evaluations=1,
        specifications=tuple(
            MotifSpecification(
                direction="seek",
                motif=MotifModel(
                    motif_id=name,
                    background=(0.25,) * 4,
                    probabilities=(tuple(0.7 if b == target else 0.1 for b in "ACGT"),),
                ),
            )
            for name, target in (("first", "A"), ("second", "C"))
        ),
    )
    complement = str.maketrans("ACGT", "TGCA")
    words = sorted(
        {
            min(w, w.translate(complement)[::-1])
            for parts in product("ACGT", repeat=4)
            for w in ("".join(parts),)
        }
    )
    problem = compile_scoring(spec)
    rows = [evaluate(w, problem) for w in words]
    prepared = [prepare_distances(row) for row in rows]
    changed_orientation_rule = 0
    for i, j in combinations(range(len(rows)), 2):
        a, b = rows[i], rows[j]
        a_sites = {k for m in a.matches for k in range(m.start, m.end)}
        b_sites = {k for m in b.matches for k in range(m.start, m.end)}
        reverse = b.sequence.translate(complement)[::-1]
        choices = [
            (b.sequence, b_sites, "forward"),
            (reverse, {3 - k for k in b_sites}, "reverse_complement"),
        ]
        for kind in ("selected_footprint", "hamming"):
            expected = min(
                (sum(a.sequence[k] != word[k] for k in mask) / len(mask), direction)
                for word, sites, direction in choices
                for mask in (a_sites | sites if kind == "selected_footprint" else set(range(4)),)
            )
            assert pair_separation(prepared[i], prepared[j], both=True, kind=kind) == expected
        if (
            pair_separation(prepared[i], prepared[j], both=True, kind="selected_footprint")[0]
            != (pair_distances(prepared[i], prepared[j], both=True)[1])
        ):
            changed_orientation_rule += 1
    assert changed_orientation_rule > 0  # This is intentionally not the old diagnostic policy.


def test_separation_rejects_mismatched_prepared_context():
    from motif_balance.model import Evaluation, MotifMatch

    def row(length):
        return Evaluation(
            sequence="A" * length,
            balance_score=1.0,
            matches=tuple(
                MotifMatch(
                    motif_id=name,
                    start=0,
                    end=1,
                    strand="+",
                    matched_sequence="A",
                    raw_score=1.0,
                    spec_direction="seek",
                    spec_satisfaction=1.0,
                    normalized_score=1.0,
                )
                for name in ("a", "b")
            ),
        )

    with pytest.raises(ValueError, match="context"):
        pair_separation(
            prepare_distances(row(2)),
            prepare_distances(row(3)),
            both=True,
            kind="selected_footprint",
        )

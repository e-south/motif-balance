"""Prepared distance arithmetic must agree with a literal, independent oracle."""

from itertools import combinations, product

import pytest

from motif_balance import DesignSpec, MotifModel, MotifSpecification, score


def distance_spec(length, *, count=2):
    return DesignSpec(
        schema_version="design-spec/v3",
        specifications=tuple(
            MotifSpecification(
                motif=MotifModel(
                    motif_id=f"m{i:02d}",
                    probabilities=tuple(
                        tuple(0.7 if base == (i + position) % 4 else 0.1 for base in range(4))
                        for position in range(1 + i % min(3, length))
                    ),
                    background=(0.25,) * 4,
                ),
                direction="seek",
            )
            for i in range(count)
        ),
        length=length,
        count=1,
        strands="both",
        seed=7,
        evaluations=1,
    )


def literal_distances(left, right, both):
    length = len(left.sequence)
    alternatives = []
    for reverse in range(2 if both else 1):
        word = (
            right.sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]
            if reverse
            else right.sequence
        )
        mismatches = [a != b for a, b in zip(left.sequence, word, strict=True)]
        covered = [
            any(m.start <= p < m.end for m in left.matches)
            or any(m.start <= (length - 1 - p if reverse else p) < m.end for m in right.matches)
            for p in range(length)
        ]
        alternatives.append(
            (
                sum(mismatches) / length,
                sum(a and b for a, b in zip(mismatches, covered, strict=True)) / sum(covered),
            )
        )
    geometry = []
    for i, j in combinations(range(len(left.matches)), 2):
        a, b = left.matches[i], left.matches[j]
        c, d = right.matches[i], right.matches[j]
        separation = abs(
            abs((a.start + a.end) / 2 - (b.start + b.end) / 2)
            - abs((c.start + c.end) / 2 - (d.start + d.end) / 2)
        )
        geometry.append((separation, (a.strand == b.strand) != (c.strand == d.strand)))
    return (
        *min(alternatives),
        *(sum(row[i] for row in geometry) / len(geometry) for i in range(2)),
    )


@pytest.mark.parametrize("both", [False, True])
def test_prepared_distances_match_every_pair_in_a_complete_three_base_space(both):
    from motif_balance.alternatives.geometry import pair_distances, prepare_distances

    spec = distance_spec(3)
    evaluations = [score("".join(word), spec) for word in product("ACGT", repeat=3)]
    prepared = [prepare_distances(evaluation) for evaluation in evaluations]
    for i, j in combinations(range(len(evaluations)), 2):
        assert pair_distances(prepared[i], prepared[j], both=both) == literal_distances(
            evaluations[i], evaluations[j], both
        )


def test_prepared_masks_span_multiple_integer_words_and_keep_odd_width_centers():
    from motif_balance.alternatives.geometry import pair_distances, prepare_distances

    spec = distance_spec(245, count=12)
    left = score(("ACGT" * 62)[:245], spec)
    right = score(("TGCA" * 62)[:245], spec)
    assert pair_distances(
        prepare_distances(left), prepare_distances(right), both=True
    ) == literal_distances(left, right, True)


def test_prepared_distance_context_mismatch_is_refused():
    from motif_balance.alternatives.geometry import pair_distances, prepare_distances

    left = prepare_distances(score("AAC", distance_spec(3)))
    for right in (score("AACC", distance_spec(4)), score("AAC", distance_spec(3, count=3))):
        with pytest.raises(ValueError, match="context"):
            pair_distances(left, prepare_distances(right), both=True)

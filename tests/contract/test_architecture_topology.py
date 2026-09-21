"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_architecture_topology.py

Interval relationships are distinct from exact spacing and literal identity.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import pytest

from motif_balance.model import Evaluation, MotifMatch


def placed(*sites):
    """Declared geometry fixture, not a purported score replay."""
    return Evaluation(
        sequence="A" * 20,
        balance_score=1.0,
        matches=tuple(
            MotifMatch(
                motif_id=name,
                start=start,
                end=end,
                strand=strand,
                matched_sequence=("A" if strand == "+" else "T") * (end - start),
                raw_score=1.0,
                normalized_score=1.0,
                spec_direction="seek",
                spec_satisfaction=1.0,
            )
            for name, start, end, strand in sites
        ),
    )


def key(*sites, both=True):
    from motif_balance.model.architecture import topology_key

    return topology_key(placed(*sites), both=both)


def test_translation_spacing_jitter_and_request_order_do_not_inflate_topology():
    a = ("a", 0, 3, "+")
    b = ("b", 5, 8, "-")
    expected = (("a", 0, 1, "+"), ("b", 2, 3, "-"))
    assert key(a, b) == expected
    assert key(b, a) == expected
    assert key(("a", 4, 7, "+"), ("b", 10, 13, "-")) == expected


def test_whole_duplex_reversal_respects_allowed_strands():
    forward = (("a", 0, 3, "+"), ("b", 5, 8, "-"))
    reverse = (("a", 17, 20, "-"), ("b", 12, 15, "+"))
    assert key(*forward) == key(*reverse)
    assert key(*forward, both=False) != key(*reverse, both=False)


def test_order_orientation_and_all_interval_boundaries_remain_distinct():
    # One-base movement across an endpoint changes the relationship explicitly;
    # movement within the same relationship does not create a spacing class.
    a = ("a", 4, 8, "+")
    cases = [
        ("b", 0, 2, "+"),  # before
        ("b", 0, 4, "+"),  # touches before
        ("b", 2, 6, "+"),  # crossing from left
        ("b", 4, 6, "+"),  # shared start, contained
        ("b", 5, 7, "+"),  # strict containment
        ("b", 6, 8, "+"),  # shared end, contained
        ("b", 4, 8, "+"),  # coincidence
        ("b", 2, 10, "+"),  # contains
        ("b", 6, 10, "+"),  # crossing from right
        ("b", 8, 12, "+"),  # touches after
        ("b", 9, 13, "+"),  # gap after
        ("b", 9, 13, "-"),  # opposite orientation
    ]
    assert len({key(a, b) for b in cases}) == len(cases)
    assert key(a, ("b", 6, 10, "+")) == key(a, ("b", 7, 11, "+"))


def test_multi_motif_relationships_and_model_labels_are_preserved():
    a, b = ("a", 0, 5, "+"), ("b", 3, 8, "+")
    inside_overlap = key(a, b, ("c", 3, 5, "+"))
    outside_overlap = key(a, b, ("c", 1, 3, "+"))
    assert inside_overlap != outside_overlap
    assert key(a, b) != key(("b", 0, 5, "+"), ("a", 3, 8, "+"))


def test_topology_requires_at_least_two_selected_matches():
    with pytest.raises(ValueError, match="two"):
        key(("a", 0, 3, "+"))

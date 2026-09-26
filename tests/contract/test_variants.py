"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_variants.py

Diversification must verify the full Cartesian library and preserve selected sites.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from itertools import product

import pytest

from motif_balance import DesignSpec, MotifModel, MotifSpecification, score
from motif_balance.variants import diversify


def request(length=2, *, both=False, unwanted=False):
    models = [
        MotifSpecification(
            motif=MotifModel(
                motif_id="wanted",
                probabilities=((0.4, 0.35, 0.2, 0.05),) * 2,
                background=(0.25,) * 4,
            ),
            direction="seek",
        )
    ]
    if unwanted:
        models.append(
            MotifSpecification(
                motif=MotifModel(
                    motif_id="unwanted",
                    probabilities=((0.1, 0.7, 0.1, 0.1),),
                    background=(0.25,) * 4,
                ),
                direction="avoid",
            )
        )
    return DesignSpec(
        specifications=tuple(models),
        length=length,
        count=1,
        evaluations=1,
        seed=7,
        strands="both" if both else "forward",
    )


def test_singly_tolerated_substitutions_are_not_combined_unchecked():
    spec = request()
    lib = diversify("AA", spec, max_score_loss=0.04)
    assert {v.sequence for v in lib.variants} == {"AA", "CA"}
    assert lib.template == "MA"
    assert lib.encoded_sequence_count == 2
    assert score("AC", spec).balance_score > 0.96
    assert score("CC", spec).balance_score < 0.96
    assert (
        next(s for s in lib.substitutions if s.position == 1 and s.base == "C").status
        == "passes_alone"
    )
    assert lib.maximum_component_loss <= 0.04
    assert lib.stop_reason == "no_further_passing_expansion"


def test_default_mask_freezes_flanks_and_each_encoded_sequence_is_scored():
    spec = request(4, both=True, unwanted=True)
    parent = "TAAC"
    lib = diversify(parent, spec, max_score_loss=0.1, max_variants=16)
    baseline = score(parent, spec)
    positions = {
        i for m in baseline.matches if m.spec_direction == "seek" for i in range(m.start, m.end)
    }
    assert set(lib.editable_positions) == positions
    encoded = {"".join(b) for b in product(*lib.allowed_bases)}
    assert encoded == {v.sequence for v in lib.variants}
    assert lib.variants[0] == baseline
    for v in lib.variants:
        assert v == score(v.sequence, spec)
        assert all(v.sequence[i] == parent[i] for i in range(4) if i not in positions)
        for p, m in zip(baseline.matches, v.matches, strict=True):
            assert p.spec_satisfaction - m.spec_satisfaction <= 0.1 + 1e-12
            if p.spec_direction == "seek":
                assert (p.start, p.end, p.strand) == (m.start, m.end, m.strand)


def test_highest_site_must_stay_even_when_score_does_not_drop():
    motif = MotifModel(
        motif_id="A", probabilities=((0.4, 0.35, 0.2, 0.05),), background=(0.25,) * 4
    )
    spec = DesignSpec(
        specifications=(MotifSpecification(motif=motif, direction="seek"),),
        length=2,
        count=1,
        evaluations=1,
        seed=1,
        strands="forward",
    )
    lib = diversify("AA", spec, max_score_loss=1.0)
    assert lib.encoded_sequence_count == 1
    assert lib.status == "parent_only"
    assert all(s.status == "site_changed" for s in lib.substitutions)


def test_reverse_sites_and_avoidance_are_protected():
    spec = request(3, both=True, unwanted=True)
    lib = diversify("TTT", spec, max_score_loss=0.1, editable_mask=(True, True, True))
    assert next(m for m in lib.parent.matches if m.spec_direction == "seek").strand == "-"
    assert any(s.status == "score_loss" for s in lib.substitutions)
    for v in lib.variants:
        for p, m in zip(lib.parent.matches, v.matches, strict=True):
            assert p.spec_satisfaction - m.spec_satisfaction <= 0.1 + 1e-12


def test_empty_mask_cap_and_determinism():
    spec = request()
    lib = diversify("AA", spec, max_score_loss=0.04, max_variants=1)
    assert lib.encoded_sequence_count == 1
    assert lib.stop_reason == "size_cap"
    assert diversify("aa", spec, max_score_loss=0.04) == diversify("AA", spec, max_score_loss=0.04)
    assert diversify("AA", spec, editable_mask=(False, False)).editable_positions == ()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_variants": 0},
        {"max_variants": 257},
        {"max_variants": True},
        {"max_variants": 2.5},
        {"max_score_loss": -1},
        {"max_score_loss": float("nan")},
        {"max_score_loss": float("inf")},
        {"max_score_loss": True},
        {"max_score_loss": 1.1},
        {"editable_mask": (1, 1)},
        {"editable_mask": (True,)},
    ],
)
def test_invalid_controls_fail(kwargs):
    with pytest.raises(ValueError):
        diversify("AA", request(), **kwargs)


def test_explicit_mask_can_allow_flanks_but_ambiguous_input_is_still_rejected():
    spec = request(3)
    lib = diversify("AAA", spec, max_score_loss=0.0, editable_mask=(False, False, True))
    assert lib.encoded_sequence_count == 4
    assert lib.template == "AAN"
    with pytest.raises(Exception, match="only A, C, G, and T"):
        score(lib.template, spec)
    with pytest.raises(Exception, match="only A, C, G, and T"):
        diversify(lib.template, spec)


def test_each_component_is_protected_even_when_balance_improves():
    desired = request().specifications[0]
    other = MotifSpecification(
        motif=MotifModel(
            motif_id="weak", probabilities=((0.05, 0.4, 0.35, 0.2),) * 2, background=(0.25,) * 4
        ),
        direction="seek",
    )
    spec = DesignSpec(
        specifications=(desired, other), length=2, count=1, evaluations=1, seed=1, strands="forward"
    )
    assert score("CA", spec).balance_score > score("AA", spec).balance_score
    assert diversify("AA", spec, max_score_loss=0.02).encoded_sequence_count == 1


def test_resource_limits_and_unwanted_only_request_are_explicit():
    spec = request()
    avoid = DesignSpec.model_validate(
        {
            **spec.model_dump(),
            "specifications": (MotifSpecification(motif=spec.scored_motifs[0], direction="avoid"),),
        }
    )
    with pytest.raises(ValueError, match="at least one desired"):
        diversify("AA", avoid)
    long = DesignSpec.model_validate({**spec.model_dump(), "length": 2000})
    with pytest.raises(ValueError, match="bounded work"):
        diversify("A" * 2000, long, editable_mask=(True,) * 2000)


def test_no_sequence_is_rescored_within_one_diversification(monkeypatch):
    from motif_balance.variants import api

    original = api.evaluate
    seen = set()

    def checked(sequence, problem):
        assert sequence not in seen
        seen.add(sequence)
        return original(sequence, problem)

    monkeypatch.setattr(api, "evaluate", checked)
    library = diversify(
        "AAAT", request(4), max_score_loss=0.2, editable_mask=(True,) * 4, max_variants=32
    )
    assert library.evaluations_used == len(seen)


@pytest.mark.parametrize("parent", ("AAAT", "TATT", "AGCT", "TTTT", "CACC"))
def test_small_libraries_agree_with_independent_rescoring(parent):
    spec = request(4, both=True, unwanted=True)
    lib = diversify(parent, spec, max_score_loss=0.3, max_variants=16, editable_mask=(True,) * 4)
    assert len(lib.variants) <= 16
    for bases in product(*lib.allowed_bases):
        result = score("".join(bases), spec)
        for p, m in zip(lib.parent.matches, result.matches, strict=True):
            assert p.spec_satisfaction - m.spec_satisfaction <= 0.3 + 1e-12
            if p.spec_direction == "seek":
                assert (p.start, p.end, p.strand) == (m.start, m.end, m.strand)
    assert lib.minimum_balance >= lib.parent.balance_score - 0.3 - 1e-12


@pytest.mark.parametrize(
    "mutation",
    [
        "changes",
        "position",
        "parent_base",
        "evaluation",
        "status",
        "sites",
        "missing",
        "duplicate",
        "model",
    ],
)
def test_serialized_library_rejects_inconsistent_substitution_diagnostics(mutation):
    from motif_balance.model.variants import VariantLibrary

    value = diversify("AA", request(), max_score_loss=0.04).model_dump(mode="json")
    row = value["substitutions"][0]
    if mutation == "changes":
        row["component_changes"] = []
    elif mutation == "position":
        row["position"] = 20
    elif mutation == "parent_base":
        row["parent_base"] = "T"
    elif mutation == "evaluation":
        row["evaluation"] = value["parent"]
    elif mutation == "status":
        row["status"] = "score_loss"
    elif mutation == "sites":
        row["changed_desired_sites"] = ["wanted"]
    elif mutation == "missing":
        value["substitutions"].pop()
    elif mutation == "duplicate":
        value["substitutions"].append(row)
    else:
        row["evaluation"]["matches"][0]["motif_id"] = "unrequested"
    with pytest.raises(ValueError):
        VariantLibrary.model_validate(value)


def test_library_handoff_replays_scores_and_accounting():
    from motif_balance.variants import load_library

    library = diversify("AA", request(), max_score_loss=0.04)
    assert load_library(library.model_dump_json()) == library


@pytest.mark.parametrize(
    "field", ["raw_score", "evaluations_used", "score_operations", "stop_reason", "problem_id"]
)
def test_library_handoff_rejects_fabricated_records(field):
    import json

    from motif_balance.variants import load_library

    library = diversify("AA", request(), max_score_loss=0.04)
    payload = library.model_dump(mode="json")
    if field == "raw_score":
        payload["substitutions"][0]["evaluation"]["matches"][0][field] += 0.1
    elif field == "stop_reason":
        payload[field] = "size_cap"
    elif field == "problem_id":
        payload[field] = "f" * 64
    else:
        payload[field] = 1
    with pytest.raises(ValueError):
        load_library(json.dumps(payload))


def test_library_handoff_refuses_duplicate_keys_and_oversize_before_parsing(monkeypatch):
    import motif_balance.variants.api as api
    from motif_balance.variants import load_library

    with pytest.raises(ValueError):
        load_library('{"x":1,"x":2}')
    monkeypatch.setattr(api, "_MAX_HANDOFF_BYTES", 10)
    with pytest.raises(ValueError, match="byte limit"):
        load_library(" " * 11)

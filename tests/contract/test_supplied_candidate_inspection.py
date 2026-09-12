"""Caller-selected candidates are replayed without inventing search provenance."""

import importlib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from pydantic import ValidationError

from motif_balance import Candidate, DesignSpec, score
from motif_balance.errors import ArtifactError
from motif_balance.formats.design import load_design_spec
from motif_balance.inspection.render import render_candidate_svg
from motif_balance.model import candidate_id_for_sequence

EXAMPLE = Path(__file__).resolve().parents[2] / "examples/synthetic-pairwise/design.yaml"


def _spec():
    return load_design_spec(EXAMPLE)


def _candidate(spec, sequence="AT", rank=6):
    value = score(sequence, spec)
    return Candidate(
        candidate_id=candidate_id_for_sequence(value.sequence), rank=rank, **value.model_dump()
    )


def _inspect(candidate, spec):
    return importlib.import_module("motif_balance.inspection").inspect_candidate(candidate, spec)


def test_supplied_candidate_keeps_its_rank_without_search_or_artifact_state(monkeypatch):
    spec = _spec()
    candidate = _candidate(spec)
    from motif_balance.inspection import project

    original = project.evaluate
    calls = []

    def counted(sequence, problem):
        calls.append(sequence)
        return original(sequence, problem)

    monkeypatch.setattr(project, "evaluate", counted)
    inspection = _inspect(candidate, spec)
    assert calls == ["AT"]
    assert inspection.subject_kind == "caller_supplied_candidate"
    assert inspection.rank_scope == "caller_supplied_order"
    assert inspection.candidate.rank == 6
    assert inspection.candidate.sequence == "AT"
    assert inspection.candidate.balance_score == 0.5
    assert [(m.start, m.end) for m in inspection.candidate.matches] == [(0, 2), (0, 2)]
    assert (
        not {"run", "bundle_id", "execution", "search", "portfolio", "integrity"}
        & inspection.model_dump().keys()
    )
    with pytest.raises(ValidationError):
        inspection.rank_scope = "selected_portfolio"
    raw = render_candidate_svg(inspection)
    assert calls == ["AT"], "rendering must not rescore"
    root = ET.fromstring(raw)
    ns = "{http://www.w3.org/2000/svg}"
    assert "Caller-supplied rank 6" in root.find(ns + "desc").text
    assert b"score replay" in raw
    assert {n.attrib["font-family"] for n in root.iter(ns + "text")} == {"Arial"}
    assert render_candidate_svg(inspection, candidate_rank=6) == raw
    with pytest.raises(ArtifactError, match="rank 1"):
        render_candidate_svg(inspection, candidate_rank=1)


def test_scored_candidate_is_inspectable_even_if_requested_portfolio_cannot_fit():
    spec = _spec()
    spec = DesignSpec.model_validate({**spec.model_dump(), "count": 17, "evaluations": 17})
    inspection = _inspect(_candidate(spec), spec)
    assert inspection.problem.length == 2
    assert inspection.candidate.balance_score == 0.5


@pytest.mark.parametrize("change", ["sequence", "score", "identity", "model", "constraint"])
def test_supplied_claims_must_match_full_authoritative_replay(change):
    spec = _spec()
    candidate = _candidate(spec)
    if change == "sequence":
        candidate = candidate.model_copy(update={"sequence": "AA"})
    elif change == "score":
        candidate = candidate.model_copy(update={"balance_score": 0.9})
    elif change == "identity":
        candidate = candidate.model_copy(update={"candidate_id": "candidate-0000000000000000"})
    elif change == "constraint":
        candidate = candidate.model_copy(
            update={"constraint_status": "infeasible", "max_avoidance_excess": 0.2}
        )
    else:
        values = spec.model_dump()
        values["specifications"][0]["motif"]["probabilities"] = (
            (0.6, 0.2, 0.1, 0.1),
            (0.1, 0.6, 0.2, 0.1),
        )
        spec = DesignSpec.model_validate(values)
    with pytest.raises((ArtifactError, ValueError)):
        _inspect(candidate, spec)


def test_support_limits_are_checked_before_evaluating(monkeypatch):
    from motif_balance.inspection import project

    spec = _spec()
    candidate = _candidate(spec)
    monkeypatch.setattr(project, "MAX_INSPECTION_SUPPORT_ROWS", 1)
    monkeypatch.setattr(
        project, "evaluate", lambda *args: pytest.fail("evaluated before admission")
    )
    with pytest.raises(ArtifactError, match="projection limit"):
        _inspect(candidate, spec)


def test_untyped_inputs_and_mismatched_projection_bindings_are_rejected():
    spec = _spec()
    candidate = _candidate(spec)
    for value, request in ((candidate.model_dump(), spec), (candidate, spec.model_dump())):
        with pytest.raises(ArtifactError, match="a Candidate and a DesignSpec"):
            _inspect(value, request)
    inspection = _inspect(candidate, spec)
    for change in ("identity", "direction", "neighbors"):
        data = inspection.model_dump(mode="python")
        if change == "identity":
            data["candidate"]["candidate_id"] = "candidate-0000000000000000"
        elif change == "neighbors":
            data["candidate"]["nearest_neighbor_distance"] = 0.5
        else:
            data["problem"]["motifs"][0]["direction"] = "avoid"
        with pytest.raises(ValidationError, match="supplied candidate"):
            type(inspection).model_validate(data)


@pytest.mark.parametrize("rank", [True, 0, -1, "6", 6.0])
def test_render_rank_is_a_positive_integer_not_a_coerced_selector(rank):
    spec = _spec()
    inspection = _inspect(_candidate(spec), spec)
    with pytest.raises(ArtifactError, match="positive integer"):
        render_candidate_svg(inspection, candidate_rank=rank)


def test_supplied_candidate_cannot_receive_a_bundle_custody_receipt():
    from motif_balance.inspection.candidate_svg_receipt import render_candidate_svg_receipt

    spec = _spec()
    inspection = _inspect(_candidate(spec), spec)
    svg = render_candidate_svg(inspection)
    with pytest.raises(ArtifactError, match="verified result inspection"):
        render_candidate_svg_receipt(inspection, candidate_rank=6, svg=svg)


def test_no_legacy_request_conversion_or_extra_provenance_fields():
    spec = _spec()
    legacy = DesignSpec(motifs=spec.scored_motifs, length=2, count=1, evaluations=16, seed=7)
    with pytest.raises(ArtifactError, match="current directional"):
        _inspect(_candidate(legacy), legacy)
    inspection = _inspect(_candidate(spec), spec)
    for field in ("run", "search", "integrity", "source_path"):
        with pytest.raises(ValidationError):
            type(inspection).model_validate({**inspection.model_dump(), field: "invented"})


def test_nonuniform_candidate_is_inspectable_but_keeps_the_existing_logo_refusal():
    spec = _spec()
    data = spec.model_dump()
    for requirement in data["specifications"]:
        requirement["motif"]["background"] = (0.4, 0.3, 0.2, 0.1)
    spec = DesignSpec.model_validate(data)
    inspection = _inspect(_candidate(spec), spec)
    assert inspection.model_dump_json()
    with pytest.raises(ArtifactError, match="uniform"):
        render_candidate_svg(inspection)


@pytest.mark.parametrize("direction, balance", [("seek", 1.0), ("avoid", 0.0)])
def test_supplied_reverse_match_and_direction_survive_the_single_renderer(direction, balance):
    from motif_balance import MotifModel, MotifSpecification

    motifs = tuple(
        MotifModel(
            motif_id=name,
            probabilities=tuple(
                tuple(0.7 if base == observed else 0.1 for base in "ACGT") for observed in word
            ),
            background=(0.25,) * 4,
        )
        for name, word in (("first", "AC"), ("second", "GT"))
    )
    spec = DesignSpec(
        schema_version="design-spec/v3",
        specifications=(
            MotifSpecification(motif=motifs[0], direction="seek"),
            MotifSpecification(motif=motifs[1], direction=direction),
        ),
        length=2,
        count=1,
        evaluations=1,
        strands="both",
        seed=7,
    )
    inspection = _inspect(_candidate(spec, sequence="GT", rank=3), spec)
    assert inspection.candidate.balance_score == balance
    first, second = inspection.candidate.matches
    assert (first.strand, first.matched_sequence) == ("-", "AC")
    assert [(p.candidate_position, p.observed_base) for p in first.position_support] == [
        (1, "A"),
        (0, "C"),
    ]
    assert (second.strand, second.spec_direction) == ("+", direction)
    root = ET.fromstring(render_candidate_svg(inspection))
    ns = "{http://www.w3.org/2000/svg}"
    lanes = root.findall(f".//{ns}g[@class='motif-match']")
    assert {(g.get("data-motif-id"), g.get("data-strand")) for g in lanes} == {
        ("first", "-"),
        ("second", "+"),
    }

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from motif_balance import DesignSpec, MotifModel, design, score
from motif_balance.admissibility import assert_evaluation_status, assess, is_preferred
from motif_balance.artifacts import read_verified_portfolio
from motif_balance.cli import app
from motif_balance.compile import compile_design
from motif_balance.errors import (
    ArtifactError,
    ConstraintFeasibilityExhausted,
    ExactConstraintInfeasible,
    PortfolioInfeasible,
)
from motif_balance.inspection import inspect_result
from motif_balance.inspection.render import (
    render_candidate_svg,
    render_html,
    render_portfolio_svg,
    render_text,
)


def _base_motif(motif_id: str, base: str) -> MotifModel:
    preferred = {"A": 0, "C": 1, "G": 2, "T": 3}[base]
    row = [0.1, 0.1, 0.1, 0.1]
    row[preferred] = 0.7
    return MotifModel(
        motif_id=motif_id,
        probabilities=(tuple(row),),
        background=(0.25, 0.25, 0.25, 0.25),
    )


def _spec(
    *,
    length: int = 1,
    count: int = 1,
    evaluations: int = 4,
    avoider_bases: tuple[str, ...] = ("A",),
) -> DesignSpec:
    target = _base_motif("target_a", "A")
    avoiders = {
        f"avoid_{base.lower()}": {
            "motif": _base_motif(f"avoid_{base.lower()}", base),
            "score_ceiling": 0.0,
        }
        for base in avoider_bases
    }
    return DesignSpec(
        motifs={target.motif_id: target},
        avoiders=avoiders,
        length=length,
        count=count,
        strands="forward",
        evaluations=evaluations,
        seed=11,
    )


def test_design_spec_canonicalizes_hard_avoider_constraints() -> None:
    spec = _spec()

    assert spec.schema_version == "design-spec/v2"
    assert tuple(item.motif.motif_id for item in spec.avoiders) == ("avoid_a",)
    assert spec.avoiders[0].score_ceiling == 0.0


def test_design_spec_rejects_invalid_or_ambiguous_avoider_contracts() -> None:
    target = _base_motif("shared", "A")

    with pytest.raises(ValidationError, match="target and avoider motif identifiers"):
        DesignSpec(
            motifs={"shared": target},
            avoiders={
                "shared": {"motif": target, "score_ceiling": 0.2},
            },
            length=1,
            count=1,
            evaluations=4,
            seed=1,
        )

    with pytest.raises(ValidationError):
        DesignSpec.model_validate(
            {
                **_spec().model_dump(mode="python"),
                "avoiders": ({"motif": _base_motif("bad", "A"), "score_ceiling": "0.2"},),
            }
        )


def test_score_reports_target_and_avoider_evidence_without_changing_target_score() -> None:
    spec = _spec()

    infeasible = score("A", spec)
    feasible = score("C", spec)

    assert infeasible.balance_score == 1.0
    assert infeasible.constraint_feasible is False
    assert infeasible.max_avoidance_excess == pytest.approx(1.0)
    assert infeasible.total_avoidance_excess == pytest.approx(1.0)
    assert tuple(match.motif_id for match in infeasible.avoidance_matches) == ("avoid_a",)
    assert feasible.constraint_feasible is True
    assert feasible.max_avoidance_excess == 0.0
    assert feasible.total_avoidance_excess == 0.0

    unconstrained = DesignSpec(
        motifs={"target_a": _base_motif("target_a", "A")},
        length=1,
        count=1,
        strands="forward",
        evaluations=4,
        seed=11,
    )
    unconstrained_evaluation = score("A", unconstrained)
    assert assess(unconstrained_evaluation, compile_design(unconstrained)).feasible is True
    assert is_preferred(feasible, infeasible) is True
    assert is_preferred(feasible, None) is True


def test_infeasible_preference_uses_total_violation_before_target_score() -> None:
    base = score("A", _spec())
    lower_total = base.model_copy(
        update={
            "max_avoidance_excess": 0.5,
            "total_avoidance_excess": 0.5,
            "balance_score": 0.0,
        }
    )
    higher_total = base.model_copy(
        update={
            "max_avoidance_excess": 0.5,
            "total_avoidance_excess": 0.75,
            "balance_score": 1.0,
        }
    )

    assert is_preferred(lower_total, higher_total) is True
    assert is_preferred(higher_total, lower_total) is False


def test_avoidance_status_is_replayed_against_declared_ceilings() -> None:
    spec = _spec()
    problem = compile_design(spec)
    evaluation = score("A", spec)
    forged = evaluation.model_copy(
        update={
            "constraint_status": "feasible",
            "max_avoidance_excess": 0.0,
            "total_avoidance_excess": 0.0,
        }
    )

    with pytest.raises(ValueError, match="avoidance status"):
        assert_evaluation_status(forged, problem)


@pytest.mark.parametrize(
    "avoiders, message",
    [
        ({1: {"motif": _base_motif("bad", "A"), "score_ceiling": 0.0}}, "keys"),
        ({"bad": "not-a-constraint"}, "constraint mapping"),
        ({"bad": {"motif": 1, "score_ceiling": 0.0}}, "does not match"),
    ],
)
def test_avoidance_mapping_rejects_malformed_shapes(avoiders: object, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        DesignSpec.model_validate(
            {
                "schema_version": "design-spec/v2",
                "motifs": {"target_a": _base_motif("target_a", "A")},
                "avoiders": avoiders,
                "length": 1,
                "count": 1,
                "evaluations": 4,
                "seed": 1,
            }
        )


def test_v1_explicitly_rejects_avoidance_constraints() -> None:
    with pytest.raises(ValidationError, match="design-spec/v1 cannot declare avoiders"):
        DesignSpec(
            schema_version="design-spec/v1",
            motifs={"target_a": _base_motif("target_a", "A")},
            avoiders={"avoid_a": {"motif": _base_motif("avoid_a", "A"), "score_ceiling": 0.0}},
            length=1,
            count=1,
            evaluations=4,
            seed=1,
        )


def test_exhaustive_design_prioritizes_feasibility_before_target_score() -> None:
    portfolio = design(_spec())

    assert portfolio.best.sequence == "C"
    assert portfolio.best.constraint_feasible is True
    assert portfolio.best.balance_score == 0.0


def test_exhaustive_search_proves_when_no_sequence_satisfies_avoidance() -> None:
    with pytest.raises(ExactConstraintInfeasible) as captured:
        design(_spec(avoider_bases=("A", "C", "G", "T")))

    assert captured.value.sequence_space_size == 4
    assert captured.value.feasible_count == 0


def test_bounded_search_reports_unresolved_constraint_feasibility() -> None:
    with pytest.raises(ConstraintFeasibilityExhausted) as captured:
        design(
            _spec(
                length=2,
                evaluations=1,
                avoider_bases=("A", "C", "G", "T"),
            )
        )

    assert captured.value.evaluations_used == 1
    assert captured.value.feasible_count == 0
    assert "does not establish" in str(captured.value)


def test_exhaustive_feasible_pool_shortfall_is_portfolio_infeasible() -> None:
    with pytest.raises(PortfolioInfeasible) as captured:
        design(_spec(count=2, avoider_bases=("A", "G", "T")))

    assert captured.value.candidate_pool_size == 1
    assert captured.value.requested_count == 2
    assert captured.value.design_space_exhausted is True


def test_v2_constraint_bundle_round_trips_separate_target_and_avoider_evidence(
    tmp_path: Path,
) -> None:
    portfolio = design(_spec())
    output = tmp_path / "result"

    portfolio.write(output)
    replay = read_verified_portfolio(output)
    design_payload = json.loads((output / "design.json").read_text())
    motif_payload = json.loads((output / "motifs.json").read_text())
    match_rows = list(
        csv.DictReader(io.StringIO((output / "matches.tsv").read_text()), delimiter="\t")
    )

    assert replay.model_dump(mode="python") == portfolio.model_dump(mode="python")
    assert portfolio.manifest.schema_version == "run-manifest/v5"
    assert design_payload["schema_version"] == "design-spec/v2"
    assert design_payload["avoiders"] == [
        {
            "model_digest": _base_motif("avoid_a", "A").model_digest,
            "motif_id": "avoid_a",
            "score_ceiling": 0.0,
        }
    ]
    assert {item["motif_id"] for item in motif_payload["motifs"]} == {
        "avoid_a",
        "target_a",
    }
    assert {(row["role"], row["motif_id"]) for row in match_rows} == {
        ("target", "target_a"),
        ("avoider", "avoid_a"),
    }
    assert next(row for row in match_rows if row["role"] == "avoider")["score_ceiling"] == "0"


def test_inspection_discloses_hard_avoidance_without_recasting_it_as_target_score(
    tmp_path: Path,
) -> None:
    output = tmp_path / "result"
    design(_spec()).write(output)

    inspection = inspect_result(output, kind="bundle")
    text = render_text(inspection)

    assert inspection.problem.avoiders[0].motif_id == "avoid_a"
    assert inspection.problem.avoiders[0].score_ceiling == 0.0
    assert inspection.portfolio.candidates[0].constraint_status == "feasible"
    assert inspection.portfolio.candidates[0].avoidance_matches[0].motif_id == "avoid_a"
    assert "Hard avoidance: avoid_a <= 0" in text
    html = render_html(inspection).decode()
    candidate_svg = render_candidate_svg(inspection).decode()
    portfolio_svg = render_portfolio_svg(inspection).decode()
    assert "Hard avoidance constraints" in html
    assert "Exact motif probability matrices" in html
    assert "avoider" in html
    assert 'data-role="avoider"' in candidate_svg
    assert 'data-score-ceiling="0"' in candidate_svg
    assert 'class="motif-information-logo"' in candidate_svg
    assert 'stroke-dasharray="6 4"' in candidate_svg
    assert "ceiling 0" in candidate_svg
    assert 'data-constraint-status="feasible"' in portfolio_svg


def test_constraint_bundle_rejects_semantic_ceiling_tampering(tmp_path: Path) -> None:
    output = tmp_path / "result"
    design(_spec()).write(output)
    design_path = output / "design.json"
    payload = json.loads(design_path.read_text())
    payload["avoiders"][0]["score_ceiling"] = 0.5
    design_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    with pytest.raises(ArtifactError, match="digest"):
        read_verified_portfolio(output)


def test_cli_preserves_design_and_score_journey_while_disclosing_avoidance(
    tmp_path: Path,
) -> None:
    (tmp_path / "target.json").write_text(_base_motif("target_a", "A").model_dump_json())
    (tmp_path / "avoid.json").write_text(_base_motif("avoid_a", "A").model_dump_json())
    specification = tmp_path / "design.yaml"
    specification.write_text(
        "schema_version: design-spec/v2\n"
        "motifs:\n  target_a: target.json\n"
        "avoiders:\n"
        "  avoid_a:\n"
        "    motif: avoid.json\n"
        "    score_ceiling: 0\n"
        "length: 1\ncount: 1\nstrands: forward\nevaluations: 4\nseed: 11\n"
    )
    runner = CliRunner()

    checked = runner.invoke(app, ["design", str(specification), "--check"])
    scored = runner.invoke(app, ["score", str(specification), "A"])

    assert checked.exit_code == 0
    assert "avoiders=1" in checked.stdout
    assert scored.exit_code == 0
    assert "constraint_status=infeasible" in scored.stdout
    assert "avoid_a: avoidance" in scored.stdout

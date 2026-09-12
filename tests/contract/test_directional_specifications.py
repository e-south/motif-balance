from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from motif_balance import DesignSpec, MotifMatch, MotifModel, MotifSpecification, design, score
from motif_balance.artifacts import read_verified_portfolio, verify_portfolio_record
from motif_balance.cli import app
from motif_balance.compile import compile_design
from motif_balance.errors import ArtifactError, InvalidDesign
from motif_balance.execution import _resolved_spec_bytes
from motif_balance.formats.design import load_design_spec
from motif_balance.inspection import inspect_result
from motif_balance.inspection.render import (
    render_candidate_svg,
    render_html,
    render_portfolio_svg,
    render_text,
)
from motif_balance.model import Evaluation, RunManifest, SearchDiagnostics
from motif_balance.observation import observe_evaluated_pool
from motif_balance.search.moves import _motif_insertion_word


def _base_motif(motif_id: str, preferred: str) -> MotifModel:
    probabilities = {
        base: tuple(0.7 if base == preferred else 0.1 for base in "ACGT") for base in "ACGT"
    }
    return MotifModel(
        motif_id=motif_id,
        probabilities=(probabilities[preferred],),
        background=(0.25, 0.25, 0.25, 0.25),
    )


def _directional_spec(*specifications: MotifSpecification) -> DesignSpec:
    return DesignSpec(
        schema_version="design-spec/v3",
        specifications=specifications,
        length=1,
        count=1,
        strands="forward",
        evaluations=4,
        seed=7,
    )


def test_twelve_specification_full_elite_reservoir_round_trips(tmp_path: Path) -> None:
    specifications = tuple(
        MotifSpecification(
            motif=_base_motif(f"synthetic_{index:02d}", "ACGT"[index % 4]), direction="seek"
        )
        for index in range(12)
    )
    result = design(
        DesignSpec(
            schema_version="design-spec/v3",
            specifications=specifications,
            length=4,
            count=1,
            evaluations=256,
            seed=7,
        )
    )
    assert len(result.manifest.elites) == 256
    output = tmp_path / "full-reservoir"

    result.write(output)

    assert (output / "manifest.json").stat().st_size > 1_000_000
    replay = read_verified_portfolio(output)
    assert replay.manifest.elites == result.manifest.elites
    assert replay.candidates == result.candidates


def test_directional_manifest_still_has_a_pre_read_byte_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import motif_balance.artifacts.snapshot as artifacts

    result = design(
        _directional_spec(
            MotifSpecification(motif=_base_motif("synthetic_a", "A"), direction="seek")
        )
    )
    output = tmp_path / "bounded"
    result.write(output)
    monkeypatch.setattr(artifacts, "MAX_RUN_MANIFEST_BYTES", 16)
    with pytest.raises(ArtifactError, match="16-byte limit"):
        read_verified_portfolio(output)


def test_large_directional_reservoir_is_refused_before_search() -> None:
    specifications = tuple(
        MotifSpecification(motif=_base_motif(f"synthetic_{index:04d}", "A"), direction="seek")
        for index in range(1_200)
    )
    with pytest.raises(ValidationError, match="manifest-byte"):
        DesignSpec(
            schema_version="design-spec/v3",
            specifications=specifications,
            length=4,
            count=1,
            evaluations=256,
            seed=7,
        )


def test_directional_satisfaction_is_computed_after_one_model_scan() -> None:
    seek_a = _base_motif("seek_a", "A")
    avoid_a = _base_motif("avoid_a", "A")
    spec = _directional_spec(
        MotifSpecification(motif=seek_a, direction="seek"),
        MotifSpecification(motif=avoid_a, direction="avoid"),
    )

    on_a = score("A", spec)
    on_c = score("C", spec)

    assert tuple(
        (match.motif_id, match.spec_direction, match.normalized_score, match.spec_satisfaction)
        for match in on_a.matches
    ) == (
        ("avoid_a", "avoid", 1.0, 0.0),
        ("seek_a", "seek", 1.0, 1.0),
    )
    assert on_a.balance_score == 0.0
    assert on_a.limiting_specification_ids == ("avoid_a",)
    assert on_c.balance_score == 0.0
    assert on_c.limiting_specification_ids == ("seek_a",)
    assert all(
        0.0 <= match.spec_satisfaction <= 1.0
        for evaluation in (on_a, on_c)
        for match in evaluation.matches
        if match.spec_satisfaction is not None
    )


def test_all_seek_directional_contract_preserves_target_only_scientific_results() -> None:
    motifs = (_base_motif("prefer_a", "A"), _base_motif("prefer_c", "C"))
    legacy = DesignSpec(
        motifs=motifs,
        length=1,
        count=1,
        strands="forward",
        evaluations=4,
        seed=11,
    )
    directional = _directional_spec(
        *(MotifSpecification(motif=motif, direction="seek") for motif in motifs)
    )

    for sequence in "ACGT":
        old = score(sequence, legacy)
        new = score(sequence, directional)
        assert new.balance_score == old.balance_score
        assert tuple(match.normalized_score for match in new.matches) == tuple(
            match.normalized_score for match in old.matches
        )

    old_result = design(legacy)
    new_result = design(directional)
    assert new_result.best.sequence == old_result.best.sequence
    assert new_result.best.balance_score == old_result.best.balance_score
    assert new_result.manifest.evaluation_count == old_result.manifest.evaluation_count


def test_adding_directional_specification_cannot_raise_exact_optimum() -> None:
    seek_a = _base_motif("seek_a", "A")
    seek_only = _directional_spec(MotifSpecification(motif=seek_a, direction="seek"))
    with_avoid = _directional_spec(
        MotifSpecification(motif=seek_a, direction="seek"),
        MotifSpecification(motif=_base_motif("avoid_a", "A"), direction="avoid"),
    )

    assert design(with_avoid).best.balance_score <= design(seek_only).best.balance_score


def test_directional_schema_is_canonical_and_rejects_legacy_thresholds() -> None:
    motif = _base_motif("seek_a", "A")
    spec = _directional_spec(MotifSpecification(motif=motif, direction="seek"))

    assert spec.model_dump(mode="json", exclude_none=True)["specifications"] == [
        {"motif": motif.model_dump(mode="json", exclude_none=True), "direction": "seek"}
    ]
    assert spec.objective_semantics == "weakest_directional_satisfaction_v1"

    with pytest.raises(ValidationError, match="legacy hard avoidance"):
        DesignSpec(
            schema_version="design-spec/v3",
            specifications=(MotifSpecification(motif=motif, direction="seek"),),
            avoiders=({"motif": _base_motif("avoid_c", "C"), "score_ceiling": 0.2},),
            length=1,
            count=1,
            strands="forward",
            evaluations=4,
            seed=7,
        )


def test_directional_schema_rejects_duplicate_motif_identity_across_directions() -> None:
    motif = _base_motif("duplicate", "A")

    with pytest.raises(ValidationError, match="specification motif identifiers must be unique"):
        _directional_spec(
            MotifSpecification(motif=motif, direction="seek"),
            MotifSpecification(motif=motif, direction="avoid"),
        )


@pytest.mark.parametrize(
    ("updates", "message"),
    (
        ({"specifications": ()}, "requires at least one motif specification"),
        ({"motifs": (_base_motif("legacy", "C"),)}, "uses specifications"),
        ({"objective_semantics": "weakest_score_v1"}, "requires objective_semantics"),
        (
            {
                "specifications": (
                    MotifSpecification(
                        motif=_base_motif("legacy_schema", "G").model_copy(
                            update={"schema_version": "motif-model/v1"}
                        ),
                        direction="seek",
                    ),
                )
            },
            "requires motifs using 'motif-model/v2'",
        ),
    ),
)
def test_directional_schema_fails_closed_on_incompatible_contracts(
    updates: dict[str, object], message: str
) -> None:
    payload: dict[str, object] = {
        "schema_version": "design-spec/v3",
        "specifications": (MotifSpecification(motif=_base_motif("seek_a", "A"), direction="seek"),),
        "length": 1,
        "count": 1,
        "strands": "forward",
        "evaluations": 4,
        "seed": 7,
    }

    with pytest.raises(ValidationError, match=message):
        DesignSpec.model_validate({**payload, **updates})


def test_legacy_schema_refuses_directional_specifications() -> None:
    motif = _base_motif("seek_a", "A")

    with pytest.raises(ValidationError, match="directional specifications require design-spec/v3"):
        DesignSpec(
            schema_version="design-spec/v2",
            motifs=(motif,),
            specifications=(MotifSpecification(motif=motif, direction="seek"),),
            length=1,
            count=1,
            strands="forward",
            evaluations=4,
            seed=7,
        )


def test_directional_match_and_evaluation_consistency_fail_closed() -> None:
    evaluation = score(
        "A",
        _directional_spec(MotifSpecification(motif=_base_motif("seek_a", "A"), direction="seek")),
    )
    match_payload = evaluation.matches[0].model_dump(mode="python")

    with pytest.raises(ValidationError, match="declared together"):
        MotifMatch.model_validate({**match_payload, "spec_direction": None})
    with pytest.raises(ValidationError, match="does not match direction"):
        MotifMatch.model_validate({**match_payload, "spec_satisfaction": 0.5})

    legacy_match = MotifMatch.model_validate(
        {
            **match_payload,
            "motif_id": "legacy",
            "spec_direction": None,
            "spec_satisfaction": None,
        }
    )
    with pytest.raises(ValidationError, match="satisfaction for every specification"):
        Evaluation(
            sequence="A",
            balance_score=evaluation.balance_score,
            matches=(*evaluation.matches, legacy_match),
        )
    with pytest.raises(ValidationError, match="weakest specification satisfaction"):
        Evaluation(
            sequence="A",
            balance_score=evaluation.balance_score / 2.0,
            matches=evaluation.matches,
        )


def test_directional_exact_run_records_completion_checkpoints_and_complete_small_elites() -> None:
    spec = _directional_spec(
        MotifSpecification(motif=_base_motif("seek_a", "A"), direction="seek"),
        MotifSpecification(motif=_base_motif("avoid_a", "A"), direction="avoid"),
    )

    manifest = design(spec).manifest

    assert manifest.schema_version == "run-manifest/v6"
    assert manifest.exact_completion_status == "complete"
    assert manifest.state_space_size == 4
    assert manifest.expected_candidate_count == 4
    assert manifest.completed_candidate_count == 4
    assert manifest.score_operation_count == 8
    assert manifest.elite_capacity == 256
    assert manifest.elite_fill_count == 4
    assert len(manifest.elites) == 4
    assert tuple(item.sequence for item in manifest.elites) == tuple(
        item.sequence
        for item in sorted(
            manifest.elites,
            key=lambda item: (-item.balance_score, item.sequence),
        )
    )
    checkpoint_evaluations = tuple(
        checkpoint.evaluations for checkpoint in manifest.search_diagnostics.checkpoints
    )
    assert checkpoint_evaluations == (1, 2, 4)
    for checkpoint in manifest.search_diagnostics.checkpoints:
        assert checkpoint.specification_satisfactions
        assert checkpoint.limiting_specification_ids
        assert checkpoint.best_score == min(
            item.satisfaction for item in checkpoint.specification_satisfactions
        )


def test_directional_search_diagnostics_reject_incomplete_or_incoherent_traces() -> None:
    manifest = design(
        _directional_spec(
            MotifSpecification(motif=_base_motif("seek_a", "A"), direction="seek"),
            MotifSpecification(motif=_base_motif("avoid_a", "A"), direction="avoid"),
        )
    ).manifest
    payload = manifest.search_diagnostics.model_dump(mode="python")
    first = payload["checkpoints"][0]

    with pytest.raises(ValidationError, match="require specification satisfactions"):
        SearchDiagnostics.model_validate(
            {
                **payload,
                "checkpoints": ({**first, "specification_satisfactions": ()},),
                "best_score": first["best_score"],
            }
        )
    with pytest.raises(ValidationError, match="require limiting specifications"):
        SearchDiagnostics.model_validate(
            {
                **payload,
                "checkpoints": ({**first, "limiting_specification_ids": ()},),
                "best_score": first["best_score"],
            }
        )
    with pytest.raises(ValidationError, match="must be unique and sorted"):
        SearchDiagnostics.model_validate(
            {
                **payload,
                "checkpoints": (
                    {
                        **first,
                        "specification_satisfactions": tuple(
                            reversed(first["specification_satisfactions"])
                        ),
                    },
                ),
                "best_score": first["best_score"],
            }
        )
    with pytest.raises(ValidationError, match="must equal its weakest"):
        SearchDiagnostics.model_validate(
            {
                **payload,
                "checkpoints": ({**first, "best_score": 0.25},),
                "best_score": 0.25,
            }
        )
    with pytest.raises(ValidationError, match="limiting specifications must exactly match"):
        SearchDiagnostics.model_validate(
            {
                **payload,
                "checkpoints": ({**first, "limiting_specification_ids": ("seek_a",)},),
                "best_score": first["best_score"],
            }
        )


def test_directional_manifest_rejects_false_exactness_and_invalid_elites() -> None:
    manifest = design(
        _directional_spec(
            MotifSpecification(motif=_base_motif("seek_a", "A"), direction="seek"),
            MotifSpecification(motif=_base_motif("avoid_a", "A"), direction="avoid"),
        )
    ).manifest
    payload = manifest.model_dump(mode="python")

    invalid_updates = (
        ({"elite_capacity": None}, "requires exact, operation, and elite metadata"),
        ({"elite_fill_count": len(manifest.elites) - 1}, "must equal retained elite rows"),
        ({"elite_capacity": len(manifest.elites) - 1}, "cannot exceed elite_capacity"),
        (
            {"elites": (manifest.elites[0], manifest.elites[0]), "elite_fill_count": 2},
            "elite sequences must be unique",
        ),
        ({"elites": tuple(reversed(manifest.elites))}, "must be sorted by score then sequence"),
        ({"state_space_size": None}, "requires complete candidate-count proof"),
        ({"completed_candidate_count": 3}, "proof does not match evaluation counts"),
        ({"exact_completion_status": "not_exact"}, "bounded runs cannot claim exact"),
    )

    for updates, message in invalid_updates:
        with pytest.raises(ValidationError, match=message):
            RunManifest.model_validate({**payload, **updates})


@pytest.mark.parametrize(
    "field",
    ("state_space_size", "expected_candidate_count", "completed_candidate_count"),
)
def test_legacy_manifest_rejects_v6_exact_count_claims(field: str) -> None:
    legacy_manifest = design(
        DesignSpec(
            motifs=(_base_motif("seek_a", "A"),),
            length=1,
            count=1,
            strands="forward",
            evaluations=4,
            seed=7,
        )
    ).manifest

    with pytest.raises(ValidationError, match="prospective run metadata requires run-manifest/v6"):
        RunManifest.model_validate(
            {**legacy_manifest.model_dump(mode="python"), field: legacy_manifest.evaluation_count}
        )


def test_directional_bounded_elite_reservoir_is_capacity_limited_and_deterministic() -> None:
    motifs = tuple(
        MotifSpecification(motif=_base_motif(f"seek_{base.lower()}", base), direction="seek")
        for base in "ACGT"
    )
    spec = DesignSpec(
        schema_version="design-spec/v3",
        specifications=motifs,
        length=5,
        count=1,
        strands="forward",
        evaluations=300,
        seed=17,
    )

    first = design(spec).manifest
    second = design(spec).manifest

    assert first == second
    assert first.exact_completion_status == "not_exact"
    assert first.state_space_size is None
    assert first.elite_fill_count == len(first.elites) <= first.elite_capacity == 256
    assert len({item.sequence for item in first.elites}) == len(first.elites)
    assert first.search_diagnostics.checkpoints[-1].evaluations == 300


def test_directional_bundle_round_trips_and_inspection_discloses_model_relative_avoidance(
    tmp_path,
) -> None:
    spec = _directional_spec(
        MotifSpecification(motif=_base_motif("seek_a", "A"), direction="seek"),
        MotifSpecification(motif=_base_motif("avoid_a", "A"), direction="avoid"),
    )
    output = tmp_path / "directional-result"
    portfolio = design(spec)

    portfolio.write(output)
    reread = read_verified_portfolio(output)
    inspection = inspect_result(output, kind="bundle")
    text = render_text(inspection)
    html = render_html(inspection).decode()
    candidate_svg = render_candidate_svg(inspection).decode()
    portfolio_svg = render_portfolio_svg(inspection).decode()

    assert reread.model_dump(mode="python") == portfolio.model_dump(mode="python")
    assert "seek_a: seek" in text
    assert "avoid_a: avoid" in text
    assert "1 - attainment" in text
    assert "model-relative" in text
    assert "Directional motif specifications" in html
    assert "does not establish biological absence" in html
    assert '<th scope="row">seek_a</th><td>seek</td>' in html
    assert '<th scope="row">avoid_a</th><td>avoid</td>' in html
    assert '<th scope="row">avoid_a</th><td>target</td>' not in html
    assert 'data-direction="avoid"' in candidate_svg
    assert 'data-spec-satisfaction="0"' in candidate_svg
    assert 'data-direction="avoid"' in portfolio_svg
    assert 'data-spec-satisfaction="0"' in portfolio_svg


def test_directional_yaml_resolves_one_canonical_specification_list(tmp_path) -> None:
    motif = _base_motif("seek_a", "A")
    (tmp_path / "seek-a.json").write_text(motif.model_dump_json())
    design_path = tmp_path / "design.yaml"
    design_path.write_text(
        "schema_version: design-spec/v3\n"
        "specifications:\n"
        "  - motif: seek-a.json\n"
        "    direction: seek\n"
        "length: 1\n"
        "count: 1\n"
        "strands: forward\n"
        "evaluations: 4\n"
        "seed: 5\n"
    )

    spec = load_design_spec(design_path)

    assert tuple((item.motif.motif_id, item.direction) for item in spec.specifications) == (
        ("seek_a", "seek"),
    )
    assert not spec.motifs
    assert not spec.avoiders


@pytest.mark.parametrize(
    ("body", "message"),
    (
        ("schema_version: design-spec/v3\n", "must be a nonempty list"),
        ("schema_version: design-spec/v3\nspecifications: {}\n", "must be a nonempty list"),
        (
            "schema_version: design-spec/v3\nspecifications:\n  - seek_a\n",
            "must be a mapping",
        ),
        (
            "schema_version: design-spec/v3\nspecifications:\n  - direction: seek\n",
            "must declare a motif",
        ),
        (
            "schema_version: design-spec/v3\n"
            "specifications:\n"
            "  - motif_id: 3\n"
            "    motif: {}\n"
            "    direction: seek\n",
            "motif_id must be a string",
        ),
    ),
)
def test_directional_yaml_rejects_ambiguous_specification_shapes(
    tmp_path: Path, body: str, message: str
) -> None:
    design_path = tmp_path / "invalid-design.yaml"
    design_path.write_text(body)

    with pytest.raises(InvalidDesign, match=message):
        load_design_spec(design_path)


def test_directional_runs_refuse_legacy_complete_pool_export() -> None:
    spec = _directional_spec(MotifSpecification(motif=_base_motif("seek_a", "A"), direction="seek"))

    with pytest.raises(ArtifactError, match="bounded elite snapshot"):
        observe_evaluated_pool(spec)


def test_directional_cli_discloses_specification_directions(tmp_path: Path) -> None:
    design_path = tmp_path / "design.yaml"
    design_path.write_text(
        "schema_version: design-spec/v3\n"
        "specifications:\n"
        "  - motif:\n"
        "      motif_id: seek_a\n"
        "      schema_version: motif-model/v2\n"
        "      probabilities: [[0.7, 0.1, 0.1, 0.1]]\n"
        "      background: [0.25, 0.25, 0.25, 0.25]\n"
        "    direction: seek\n"
        "  - motif:\n"
        "      motif_id: avoid_a\n"
        "      schema_version: motif-model/v2\n"
        "      probabilities: [[0.7, 0.1, 0.1, 0.1]]\n"
        "      background: [0.25, 0.25, 0.25, 0.25]\n"
        "    direction: avoid\n"
        "length: 1\n"
        "count: 1\n"
        "strands: forward\n"
        "evaluations: 4\n"
        "seed: 5\n"
    )
    runner = CliRunner()

    checked = runner.invoke(app, ["design", str(design_path), "--check"])
    scored = runner.invoke(app, ["score", str(design_path), "A"])

    assert checked.exit_code == 0
    assert "specifications=2" in checked.stdout
    assert "seek_a:seek" in checked.stdout
    assert "avoid_a:avoid" in checked.stdout
    assert scored.exit_code == 0
    assert "avoid_a: direction=avoid" in scored.stdout
    assert "attainment=1" in scored.stdout
    assert "satisfaction=0" in scored.stdout


def test_directional_execution_spec_serialization_stays_canonical() -> None:
    spec = _directional_spec(MotifSpecification(motif=_base_motif("seek_a", "A"), direction="seek"))

    payload = json.loads(_resolved_spec_bytes(spec))

    assert "motifs" not in payload
    assert payload["specifications"][0]["direction"] == "seek"
    assert payload["specifications"][0]["motif"]["motif_id"] == "seek_a"

    public_payload = spec.model_dump(mode="json")
    assert "motifs" not in public_payload
    assert "avoiders" not in public_payload


def test_directional_scientific_replay_checks_every_retained_elite() -> None:
    portfolio = design(
        _directional_spec(MotifSpecification(motif=_base_motif("seek_a", "A"), direction="seek"))
    )
    first = portfolio.manifest.elites[0]
    tampered = first.model_copy(update={"balance_score": first.balance_score / 2.0})
    manifest = portfolio.manifest.model_copy(
        update={"elites": (tampered, *portfolio.manifest.elites[1:])}
    )
    record = portfolio.model_copy(update={"manifest": manifest})

    with pytest.raises(ArtifactError, match="retained elite"):
        verify_portfolio_record(record)


def test_directional_guided_insertion_opposes_an_avoided_model() -> None:
    motif = _base_motif("prefer_a", "A")
    compiled = compile_design(
        _directional_spec(MotifSpecification(motif=motif, direction="avoid"))
    ).motifs[0]

    avoided_word = _motif_insertion_word(
        compiled,
        direction="avoid",
        rng=np.random.Generator(np.random.PCG64(0)),
    )
    sought_word = _motif_insertion_word(
        compiled,
        direction="seek",
        rng=np.random.Generator(np.random.PCG64(0)),
    )

    assert avoided_word == "C"
    assert sought_word == "A"


def test_search_terminology_never_labels_the_annealed_engine_as_a_sampler() -> None:
    root = Path(__file__).resolve().parents[2]
    surfaces = (
        *(root / "src" / "motif_balance").rglob("*.py"),
        root / "DESIGN.md",
        root / "docs" / "methods.md",
    )

    for surface in surfaces:
        content = surface.read_text().lower()
        assert "gibbs" not in content, surface
        assert "metropolis" not in content, surface
        assert "mcmc" not in content, surface

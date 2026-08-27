from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from motif_balance import DesignSpec, design, inspect_result, render_inspection_html
from motif_balance.errors import ArtifactError
from motif_balance.model import Candidate, MotifMatch, SearchCheckpoint, SearchDiagnostics
from motif_balance.visualization import (
    render_candidate_match_map,
    render_portfolio_balance_profile,
    render_search_progress,
)


def test_candidate_map_is_deterministic_accessible_and_coordinate_bound(
    pairwise_spec: DesignSpec,
) -> None:
    portfolio = design(pairwise_spec)
    candidate = portfolio.best

    first = render_candidate_match_map(candidate)
    second = render_candidate_match_map(candidate)
    root = ET.fromstring(first)

    assert first == second
    assert root.tag.endswith("svg")
    assert root.attrib["role"] == "img"
    assert root.find("{http://www.w3.org/2000/svg}title") is not None
    assert root.find("{http://www.w3.org/2000/svg}desc") is not None
    assert candidate.candidate_id.encode() in first
    for match in candidate.matches:
        assert f'data-motif-id="{match.motif_id}"'.encode() in first
        assert f'data-start="{match.start}"'.encode() in first
        assert f'data-end="{match.end}"'.encode() in first
        assert f'data-strand="{match.strand}"'.encode() in first
    assert b"<script" not in first
    assert b"<foreignObject" not in first
    assert b"href=" not in first
    assert b"url(" not in first

    reordered = candidate.model_copy(update={"matches": tuple(reversed(candidate.matches))})
    assert render_candidate_match_map(reordered) == first


def test_search_progress_is_an_honest_checkpoint_step_plot(pairwise_spec: DesignSpec) -> None:
    portfolio = design(pairwise_spec)

    payload = render_search_progress(portfolio.manifest.search_diagnostics)
    root = ET.fromstring(payload)

    assert root.tag.endswith("svg")
    assert b"Best-so-far score at recorded checkpoints" in payload
    assert b"Evaluator calls" in payload
    assert b"data-checkpoint-count" in payload
    assert b"posterior" not in payload.lower()


def test_search_progress_preserves_scores_above_one_and_discloses_sampling(
    pairwise_spec: DesignSpec,
) -> None:
    proposals = design(pairwise_spec).manifest.search_diagnostics.proposals
    diagnostics = SearchDiagnostics(
        restarts=1,
        best_score=3.0,
        checkpoints=tuple(
            SearchCheckpoint(evaluations=index, best_score=2.0 + index / 300)
            for index in range(1, 301)
        ),
        restart_final_scores=(3.0,),
        proposals=proposals,
    )

    payload = render_search_progress(diagnostics)

    assert b'data-checkpoint-count="300"' in payload
    assert b'data-displayed-checkpoints="256"' in payload
    assert b'data-render-mode="sampled_markers"' in payload
    assert b"final best 3" in payload
    assert b"probability" not in payload.lower()


def test_search_progress_preserves_the_recorded_improvement_evaluation(
    pairwise_spec: DesignSpec,
) -> None:
    proposals = design(pairwise_spec).manifest.search_diagnostics.proposals
    diagnostics = SearchDiagnostics(
        restarts=1,
        best_score=1.0,
        checkpoints=tuple(
            SearchCheckpoint(evaluations=index, best_score=1.0 if index >= 701 else 0.0)
            for index in range(1, 1_001)
        ),
        restart_final_scores=(1.0,),
        proposals=proposals,
    )

    payload = render_search_progress(diagnostics)

    assert b'data-render-mode="change_preserving_step"' in payload
    assert b'data-improvement-evaluations="701"' in payload
    assert b'data-improvement-evaluations="702"' not in payload


def test_portfolio_profile_is_bounded_and_names_every_motif(pairwise_spec: DesignSpec) -> None:
    portfolio = design(pairwise_spec)

    payload = render_portfolio_balance_profile(portfolio.candidates)
    root = ET.fromstring(payload)

    assert root.tag.endswith("svg")
    assert b'data-displayed-candidates="3"' in payload
    assert b'data-total-candidates="3"' in payload
    assert b"motif_a" in payload
    assert b"motif_b" in payload
    assert b"Probability" not in payload

    bounded = render_portfolio_balance_profile(portfolio.candidates * 10)
    assert b'data-displayed-candidates="24"' in bounded
    assert b'data-total-candidates="30"' in bounded
    assert b"Bounded view: 24/30 candidates" in bounded


def test_candidate_map_rejects_incoherent_geometry(pairwise_spec: DesignSpec) -> None:
    candidate = design(pairwise_spec).best
    bad_match = candidate.matches[0].model_copy(update={"end": len(candidate.sequence) + 1})
    invalid = candidate.model_copy(update={"matches": (bad_match, *candidate.matches[1:])})

    with pytest.raises(ArtifactError, match="coordinates exceed"):
        render_candidate_match_map(invalid)


def test_bounded_views_prioritize_and_disclose_limiting_motifs() -> None:
    leading_matches = tuple(
        MotifMatch(
            motif_id=f"motif_{index:02d}",
            start=0,
            end=1,
            strand="+",
            matched_sequence="A",
            raw_score=1.0,
            normalized_score=1.0,
        )
        for index in range(32)
    )
    matches = (
        *leading_matches,
        MotifMatch(
            motif_id="motif_zz",
            start=0,
            end=1,
            strand="+",
            matched_sequence="A",
            raw_score=0.0,
            normalized_score=0.0,
        ),
    )
    candidate = Candidate(
        candidate_id="candidate-0000000000000000",
        rank=1,
        sequence="A",
        balance_score=0.0,
        matches=matches,
    )

    match_map = render_candidate_match_map(candidate)
    profile = render_portfolio_balance_profile((candidate,))

    assert b'data-motif-id="motif_zz"' in match_map
    assert b'data-displayed-limiting="1"' in match_map
    assert b'data-total-limiting="1"' in match_map
    assert b'data-motif-id="motif_zz"' in profile
    assert b'data-displayed-limiting="1"' in profile
    assert b'data-total-limiting="1"' in profile
    assert b"0 \xc2\xb7 motif_zz" in profile


def test_profile_discloses_limiting_ties_beyond_the_column_bound() -> None:
    matches = tuple(
        MotifMatch(
            motif_id=f"motif_{index:02d}",
            start=0,
            end=1,
            strand="+",
            matched_sequence="A",
            raw_score=0.0,
            normalized_score=0.0,
        )
        for index in range(17)
    )
    candidate = Candidate(
        candidate_id="candidate-1111111111111111",
        rank=1,
        sequence="A",
        balance_score=0.0,
        matches=matches,
    )

    payload = render_portfolio_balance_profile((candidate,))

    assert b'data-displayed-limiting="16"' in payload
    assert b'data-total-limiting="17"' in payload
    assert b"motif_00, motif_01 +15" in payload


def test_inspection_html_embeds_product_visual_explainers(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    portfolio = design(pairwise_spec)
    bundle = tmp_path / "bundle"
    portfolio.write(bundle)
    inspection = inspect_result(
        bundle,
        kind="bundle",
        expected_bundle_id=portfolio.manifest.bundle_id,
    )

    report = render_inspection_html(inspection).decode()

    assert "How the result was built" in report
    assert "Where motif scores land" in report
    assert "Portfolio balance" in report
    assert "Best-so-far search progress" in report
    assert report.count("<svg") >= 3
    assert "recorded checkpoints, not a full optimizer trace" in report
    assert "<script" not in report
    assert "<foreignObject" not in report
    assert "href=" not in report
    assert "url(" not in report

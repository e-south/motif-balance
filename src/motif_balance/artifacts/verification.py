"""Scientific replay of an already parsed immutable portfolio."""

from __future__ import annotations

from pathlib import Path

from motif_balance.compile import build_run_id, compile_design, sequence_space_at_most
from motif_balance.constants import (
    GREEDY_INDEPENDENT_SEARCH_ENGINE,
    GREEDY_SEARCH_ENGINE,
    INDEPENDENT_SEARCH_ENGINE,
    RANDOM_SEARCH_ENGINE,
    RNG_NAME,
    SEARCH_ENGINE,
    SEARCH_ENGINE_VERSION,
)
from motif_balance.errors import ArtifactError
from motif_balance.model import (
    PortfolioRecord,
    candidate_id_for_sequence,
)
from motif_balance.scoring import evaluate

from .snapshot import BundleSnapshot, read_bundle_snapshot


def verify_portfolio_record(portfolio: PortfolioRecord) -> None:
    """Replay identities, search provenance, and every published candidate score."""

    problem = compile_design(portfolio.spec)
    if problem.problem_id != portfolio.manifest.problem_id:
        raise ArtifactError("scientific replay found a problem identity mismatch")
    expected_run = build_run_id(
        portfolio.spec,
        problem.problem_id,
        portfolio.manifest.search_engine,
        portfolio.manifest.search_engine_version,
        package_version=portfolio.manifest.package_version,
    )
    if expected_run != portfolio.manifest.run_id:
        raise ArtifactError("scientific replay found a run identity mismatch")

    sequence_space = sequence_space_at_most(portfolio.spec.length, portfolio.spec.evaluations)
    random_directional = (
        portfolio.manifest.search_engine == RANDOM_SEARCH_ENGINE
        and portfolio.spec.schema_version == "design-spec/v3"
    )
    if sequence_space is not None and not random_directional:
        expected_metadata = (
            "exhaustive_v1",
            SEARCH_ENGINE_VERSION,
            "none",
            "exhaustive",
            "not_applicable",
            sequence_space,
        )
    else:
        expected_metadata = (
            portfolio.manifest.search_engine
            if portfolio.manifest.search_engine
            in (
                INDEPENDENT_SEARCH_ENGINE,
                GREEDY_SEARCH_ENGINE,
                GREEDY_INDEPENDENT_SEARCH_ENGINE,
                RANDOM_SEARCH_ENGINE,
            )
            and portfolio.spec.schema_version == "design-spec/v3"
            else SEARCH_ENGINE,
            SEARCH_ENGINE_VERSION,
            RNG_NAME,
            "budget_exhausted",
            "contract_tested",
            portfolio.spec.evaluations,
        )
    actual_metadata = (
        portfolio.manifest.search_engine,
        portfolio.manifest.search_engine_version,
        portfolio.manifest.rng,
        portfolio.manifest.completion_status,
        portfolio.manifest.search_validation_status,
        portfolio.manifest.evaluation_count,
    )
    if actual_metadata != expected_metadata:
        raise ArtifactError("scientific replay found inconsistent search provenance")
    if portfolio.manifest.unique_evaluations > portfolio.manifest.evaluation_count:
        raise ArtifactError("scientific replay found impossible evaluation counts")
    if random_directional and (
        portfolio.manifest.exact_completion_status != "not_exact"
        or (sequence_space is not None and portfolio.manifest.unique_evaluations > sequence_space)
    ):
        raise ArtifactError("scientific replay found impossible random coverage metadata")

    best_observed = portfolio.manifest.best_observed
    if best_observed is not None:
        authoritative_best = evaluate(best_observed.sequence, problem)
        if authoritative_best != best_observed:
            raise ArtifactError(
                "scientific replay found scoring drift for the best observed candidate"
            )

    for elite in portfolio.manifest.elites:
        authoritative_elite = evaluate(elite.sequence, problem)
        if authoritative_elite != elite:
            raise ArtifactError(
                f"scientific replay found scoring drift for retained elite '{elite.sequence}'"
            )

    seen_ids: set[str] = set()
    for candidate in portfolio.candidates:
        if candidate.candidate_id in seen_ids:
            raise ArtifactError("scientific replay found duplicate candidate identifiers")
        seen_ids.add(candidate.candidate_id)
        authoritative = evaluate(candidate.sequence, problem)
        if candidate.candidate_id != candidate_id_for_sequence(candidate.sequence):
            raise ArtifactError(
                f"scientific replay found a candidate identity mismatch for rank {candidate.rank}"
            )
        if (
            candidate.balance_score != authoritative.balance_score
            or candidate.matches != authoritative.matches
            or candidate.avoidance_matches != authoritative.avoidance_matches
            or candidate.constraint_status != authoritative.constraint_status
            or candidate.max_avoidance_excess != authoritative.max_avoidance_excess
            or candidate.total_avoidance_excess != authoritative.total_avoidance_excess
        ):
            raise ArtifactError(
                f"scientific replay found scoring drift for '{candidate.candidate_id}'"
            )


def read_verified_portfolio_snapshot(
    directory: str | Path,
    *,
    expected_bundle_id: str | None = None,
) -> tuple[PortfolioRecord, BundleSnapshot]:
    """Read one descriptor-bound bundle snapshot and replay its scientific records."""

    snapshot = read_bundle_snapshot(directory)
    portfolio = snapshot.portfolio
    if expected_bundle_id is not None and portfolio.manifest.bundle_id != expected_bundle_id:
        raise ArtifactError("bundle identity does not match the externally expected identity")
    verify_portfolio_record(portfolio)
    return portfolio, snapshot


def read_verified_portfolio(
    directory: str | Path,
    *,
    expected_bundle_id: str | None = None,
) -> PortfolioRecord:
    portfolio, _snapshot = read_verified_portfolio_snapshot(
        directory,
        expected_bundle_id=expected_bundle_id,
    )
    return portfolio


def verify_bundle(
    directory: str | Path,
    *,
    expected_bundle_id: str | None = None,
) -> str:
    return read_verified_portfolio(
        directory,
        expected_bundle_id=expected_bundle_id,
    ).manifest.bundle_id

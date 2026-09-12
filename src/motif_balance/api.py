from __future__ import annotations

from pathlib import Path

from motif_balance.artifacts import (
    artifact_records,
    base_artifact_payloads,
    bundle_id,
    candidates_fasta,
    verify_portfolio_record,
    write_bundle,
)
from motif_balance.compile import CompiledProblem, build_run_id, compile_design, compile_scoring
from motif_balance.constants import (
    BUILD_LOCK_SHA256,
    GREEDY_INDEPENDENT_SEARCH_ENGINE,
    GREEDY_SEARCH_ENGINE,
    INDEPENDENT_SEARCH_ENGINE,
    MAX_SEARCH_OBSERVATION_BYTES,
    PACKAGE_VERSION,
    RANDOM_SEARCH_ENGINE,
    RUNTIME_CONTRACT,
    SEARCH_ENGINE,
    SEARCH_ENGINE_VERSION,
)
from motif_balance.errors import (
    ArtifactError,
    ConstraintFeasibilityExhausted,
    ExactConstraintInfeasible,
    IncompatibleDesign,
    PortfolioInfeasible,
)
from motif_balance.model import (
    DesignSpec,
    Evaluation,
    PortfolioRecord,
    RunManifest,
)
from motif_balance.model.search import SearchInitialization, SearchMethod
from motif_balance.model.search_observation import ObservationSpec, SearchObservation
from motif_balance.scoring import evaluate
from motif_balance.search import (
    AnnealedSearchEngine,
    GreedySearchEngine,
    SearchEngine,
    SearchResult,
    UniformRandomSearchEngine,
    search,
)
from motif_balance.search.observation import SearchRecorder
from motif_balance.selection import select_candidates

# Advanced observation helpers are explicit submodule imports, not scientific facade verbs.
__all__ = ["design", "score"]


class Portfolio(PortfolioRecord):
    """Public immutable portfolio with explicit publication conveniences."""

    def to_fasta(self) -> str:
        return candidates_fasta(self.candidates).decode()

    def write(self, path: str | Path) -> Path:
        if (
            self.manifest.schema_version not in {"run-manifest/v5", "run-manifest/v6"}
            or self.manifest.package_version != PACKAGE_VERSION
            or self.manifest.runtime_contract != RUNTIME_CONTRACT
            or self.manifest.build_lock_sha256 != BUILD_LOCK_SHA256
        ):
            raise ArtifactError("bundle publication requires current package provenance")
        verify_portfolio_record(self)
        return write_bundle(
            self,
            Path(path),
            base_artifact_payloads(self.spec, self.candidates),
        )


def score(sequence: str, spec: DesignSpec) -> Evaluation:
    """Evaluate one supplied sequence without testing portfolio-count feasibility."""

    return evaluate(sequence, compile_scoring(spec))


def _require_publishable_design(spec: DesignSpec) -> None:
    if spec.schema_version not in {"design-spec/v2", "design-spec/v3"}:
        raise IncompatibleDesign(
            "design-spec/v1 is read-only and cannot publish a new result",
            field="schema_version",
            hint="Use design-spec/v2 or design-spec/v3 with motif-model/v2 for new runs.",
        )


def _portfolio_from_search_result(
    spec: DesignSpec,
    problem: CompiledProblem,
    result: SearchResult,
) -> Portfolio:
    """Construct the ordinary immutable portfolio from one authoritative search result."""

    feasible = tuple(item for item in result.evaluations if item.constraint_feasible)
    best_infeasible = min(
        (item for item in result.evaluations if not item.constraint_feasible),
        key=lambda item: (
            item.max_avoidance_excess,
            item.total_avoidance_excess,
            -item.balance_score,
            item.sequence,
        ),
        default=None,
    )
    if spec.avoiders and not feasible:
        if result.completion_status == "exhaustive":
            raise ExactConstraintInfeasible(sequence_space_size=result.evaluations_used)
        raise ConstraintFeasibilityExhausted(
            requested_count=spec.count,
            feasible_count=0,
            evaluations_used=result.evaluations_used,
            best_max_excess=(
                None if best_infeasible is None else best_infeasible.max_avoidance_excess
            ),
            best_total_excess=(
                None if best_infeasible is None else best_infeasible.total_avoidance_excess
            ),
        )
    if spec.avoiders and len(feasible) < spec.count:
        if result.completion_status == "exhaustive":
            raise PortfolioInfeasible(
                requested_count=spec.count,
                valid_count=len(feasible),
                candidate_pool_size=len(feasible),
                minimum_distance=spec.min_distance,
                evaluations_used=result.evaluations_used,
                best_score=max((item.balance_score for item in feasible), default=None),
                design_space_exhausted=True,
            )
        raise ConstraintFeasibilityExhausted(
            requested_count=spec.count,
            feasible_count=len(feasible),
            evaluations_used=result.evaluations_used,
            best_max_excess=(
                None if best_infeasible is None else best_infeasible.max_avoidance_excess
            ),
            best_total_excess=(
                None if best_infeasible is None else best_infeasible.total_avoidance_excess
            ),
        )
    candidate_pool = feasible if spec.avoiders else result.evaluations
    best_observed = min(
        candidate_pool,
        key=lambda evaluation: (-evaluation.balance_score, evaluation.sequence),
    )
    candidates = select_candidates(
        candidate_pool,
        count=spec.count,
        min_distance=spec.min_distance,
        evaluations_used=result.evaluations_used,
        design_space_exhausted=result.completion_status == "exhaustive",
    )
    run_id = build_run_id(
        spec,
        problem.problem_id,
        result.engine,
        result.engine_version,
        package_version=PACKAGE_VERSION,
    )
    artifacts = artifact_records(base_artifact_payloads(spec, candidates))
    strand_factor = 2 if spec.strands == "both" else 1
    score_operations_per_evaluation = sum(
        (spec.length - motif.width + 1) * motif.width * strand_factor
        for motif in (*spec.scored_motifs, *(item.motif for item in spec.avoiders))
    )
    is_directional = spec.schema_version == "design-spec/v3"
    is_exact = result.completion_status == "exhaustive"
    provisional_manifest = RunManifest(
        schema_version=(
            "run-manifest/v6"
            if spec.schema_version == "design-spec/v3"
            else "run-manifest/v5"
            if spec.schema_version == "design-spec/v2"
            else "run-manifest/v4"
        ),
        package_version=PACKAGE_VERSION,
        runtime_contract=RUNTIME_CONTRACT,
        build_lock_sha256=BUILD_LOCK_SHA256,
        problem_id=problem.problem_id,
        run_id=run_id,
        bundle_id="bundle-000000000000000000000000",
        search_engine=result.engine,
        search_engine_version=result.engine_version,
        rng=result.rng,
        evaluation_count=result.evaluations_used,
        unique_evaluations=result.unique_evaluations,
        completion_status=result.completion_status,
        search_validation_status=result.search_validation_status,
        search_diagnostics=result.diagnostics,
        best_observed=best_observed,
        exact_completion_status=(
            ("complete" if is_exact else "not_exact") if is_directional else None
        ),
        state_space_size=result.evaluations_used if is_directional and is_exact else None,
        expected_candidate_count=result.evaluations_used if is_directional and is_exact else None,
        completed_candidate_count=result.evaluations_used if is_directional and is_exact else None,
        score_operation_count=(
            result.evaluations_used * score_operations_per_evaluation if is_directional else None
        ),
        elite_capacity=result.elite_capacity if is_directional else None,
        elite_fill_count=len(result.elites) if is_directional else None,
        elites=result.elites if is_directional else (),
        artifacts=artifacts,
    )
    manifest = provisional_manifest.model_copy(
        update={"bundle_id": bundle_id(provisional_manifest)}
    )
    return Portfolio(
        problem_id=problem.problem_id,
        run_id=run_id,
        spec=spec,
        candidates=candidates,
        manifest=manifest,
    )


def _search_engine(
    method: SearchMethod,
    initialization: SearchInitialization,
    observer: SearchRecorder | None = None,
) -> SearchEngine:
    if method not in ("annealed", "greedy", "random"):
        raise ValueError("method must be annealed, greedy, or random")
    if method == "random":
        if initialization != "related":
            raise ValueError("random search has no chain initialization; omit initialization")
        return UniformRandomSearchEngine(observer=observer)
    engine = AnnealedSearchEngine if method == "annealed" else GreedySearchEngine
    return engine(observer=observer, initialization=initialization)


def design(
    spec: DesignSpec,
    *,
    initialization: SearchInitialization = "related",
    method: SearchMethod = "annealed",
) -> Portfolio:
    """Return one exact immutable portfolio or raise a typed failure."""

    _require_publishable_design(spec)
    engine = _search_engine(method, initialization)
    problem = compile_design(spec)
    result = search(problem, engine=engine)
    return _portfolio_from_search_result(spec, problem, result)


def design_observed(
    spec: DesignSpec,
    observation_spec: ObservationSpec,
    *,
    initialization: SearchInitialization = "related",
    method: SearchMethod = "annealed",
) -> tuple[Portfolio, SearchObservation]:
    """Design once with passive diagnostics, leaving the canonical portfolio unchanged."""

    spec = DesignSpec.model_validate(spec.model_dump(mode="python"))
    observation_spec = ObservationSpec.model_validate(observation_spec.model_dump(mode="python"))
    _require_publishable_design(spec)
    recorder = SearchRecorder(spec, observation_spec)
    engine = _search_engine(method, initialization, recorder)
    problem = compile_design(spec)
    result = engine.search(problem)
    observation = recorder.finish(
        engine=result.engine,
        engine_version=result.engine_version,
        evaluation_count=result.evaluations_used,
    )
    if len(observation.model_dump_json().encode()) > MAX_SEARCH_OBSERVATION_BYTES:
        raise ValueError("search observation exceeds the 64 MiB byte limit")
    return _portfolio_from_search_result(spec, problem, result), observation


def verify_search_observation(observation: SearchObservation) -> None:
    """Replay a bounded observation, including exact hit times and chain identities."""

    checked = SearchObservation.model_validate(observation.model_dump(mode="python"))
    if checked.engine_version != SEARCH_ENGINE_VERSION or checked.engine not in (
        SEARCH_ENGINE,
        INDEPENDENT_SEARCH_ENGINE,
        GREEDY_SEARCH_ENGINE,
        GREEDY_INDEPENDENT_SEARCH_ENGINE,
        RANDOM_SEARCH_ENGINE,
        "exhaustive_v1",
    ):
        raise ValueError("unsupported search engine identity for observation replay")
    initialization: SearchInitialization = (
        "independent"
        if checked.engine in (INDEPENDENT_SEARCH_ENGINE, GREEDY_INDEPENDENT_SEARCH_ENGINE)
        else "related"
    )
    method: SearchMethod = (
        "random"
        if checked.engine == RANDOM_SEARCH_ENGINE
        else "greedy"
        if checked.engine in (GREEDY_SEARCH_ENGINE, GREEDY_INDEPENDENT_SEARCH_ENGINE)
        else "annealed"
    )
    _, replayed = design_observed(
        checked.spec, checked.observation_spec, initialization=initialization, method=method
    )
    if replayed != checked:
        raise ValueError("search observation replay differs from recorded search")


def read_search_observation(payload: bytes) -> SearchObservation:
    """Read caller-owned bytes with a transport bound and full deterministic replay."""

    if len(payload) > MAX_SEARCH_OBSERVATION_BYTES:
        raise ValueError("search observation exceeds the 64 MiB byte limit")
    observation = SearchObservation.model_validate_json(payload)
    verify_search_observation(observation)
    return observation

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
from motif_balance.compile import build_run_id, compile_design
from motif_balance.constants import (
    BUILD_LOCK_SHA256,
    PACKAGE_VERSION,
    RUNTIME_CONTRACT,
)
from motif_balance.errors import ArtifactError, IncompatibleDesign
from motif_balance.model import (
    DesignSpec,
    Evaluation,
    PortfolioRecord,
    RunManifest,
)
from motif_balance.scoring import evaluate
from motif_balance.search import search
from motif_balance.selection import select_candidates

__all__ = ["design", "score"]


class Portfolio(PortfolioRecord):
    """Public immutable portfolio with explicit publication conveniences."""

    def to_fasta(self) -> str:
        return candidates_fasta(self.candidates).decode()

    def write(self, path: str | Path) -> Path:
        if (
            self.manifest.schema_version != "run-manifest/v5"
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
    """Evaluate one sequence under the same authority used by design."""

    return evaluate(sequence, compile_design(spec))


def design(spec: DesignSpec) -> Portfolio:
    """Return one exact immutable portfolio or raise a typed failure."""

    if spec.schema_version != "design-spec/v2":
        raise IncompatibleDesign(
            "design-spec/v1 is read-only and cannot publish a new result",
            field="schema_version",
            hint="Use design-spec/v2 and motif-model/v2 for new design runs.",
        )

    problem = compile_design(spec)
    result = search(problem)
    best_observed = min(
        result.evaluations,
        key=lambda evaluation: (-evaluation.balance_score, evaluation.sequence),
    )
    candidates = select_candidates(
        result.evaluations,
        count=spec.count,
        min_distance=spec.min_distance,
        evaluations_used=result.evaluations_used,
    )
    run_id = build_run_id(
        spec,
        problem.problem_id,
        result.engine,
        result.engine_version,
        package_version=PACKAGE_VERSION,
    )
    artifacts = artifact_records(base_artifact_payloads(spec, candidates))
    provisional_manifest = RunManifest(
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

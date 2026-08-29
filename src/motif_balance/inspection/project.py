from __future__ import annotations

import hashlib
import math
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

from motif_balance.compile import CompiledProblem, compile_design
from motif_balance.constants import MAX_DISTANCE_BASE_COMPARISONS
from motif_balance.errors import ArtifactError
from motif_balance.model import (
    ArtifactDigest,
    Candidate,
    DesignSpec,
    ExecutionReceipt,
    ExecutionWorkspace,
    MotifMatch,
    MotifModel,
    candidate_id_for_sequence,
)
from motif_balance.scoring import evaluate

from .limits import MAX_INSPECTION_SUPPORT_ROWS
from .model import (
    BestObservedInspection,
    DeliveryInspection,
    DistanceInspection,
    ExecutionInspection,
    InspectionArtifact,
    InspectionAvoider,
    InspectionCandidate,
    InspectionMatch,
    InspectionMotif,
    InspectionPortfolio,
    InspectionProblem,
    InspectionRun,
    IntegrityInspection,
    LimitingMotifCount,
    PositionSupport,
    ResultInspection,
    SearchInspection,
)
from .verify import VerifiedResultSource

_BASE_INDEX = {base: index for index, base in enumerate("ACGT")}


def _support(motif: MotifModel, candidate: Candidate, match: MotifMatch) -> InspectionMatch:
    rows: list[PositionSupport] = []
    for motif_position, observed_base in enumerate(match.matched_sequence):
        base_index = _BASE_INDEX[observed_base]
        model_probability = motif.probabilities[motif_position][base_index]
        background_probability = motif.background[base_index]
        candidate_position = (
            match.start + motif_position if match.strand == "+" else match.end - 1 - motif_position
        )
        rows.append(
            PositionSupport(
                motif_position=motif_position,
                candidate_position=candidate_position,
                observed_base=cast(Literal["A", "C", "G", "T"], observed_base),
                model_probability=model_probability,
                background_probability=background_probability,
                llr_contribution=math.log2(model_probability / background_probability),
            )
        )
    return InspectionMatch(
        motif_id=match.motif_id,
        start=match.start,
        end=match.end,
        strand=match.strand,
        matched_sequence=match.matched_sequence,
        raw_score=match.raw_score,
        normalized_score=match.normalized_score,
        position_support=tuple(rows),
    )


def _project_candidate(
    spec: DesignSpec,
    candidate: Candidate,
    problem: CompiledProblem,
    *,
    nearest_neighbor_distance: float | None = None,
) -> InspectionCandidate:
    authoritative = evaluate(candidate.sequence, problem)
    if (
        authoritative.balance_score != candidate.balance_score
        or authoritative.matches != candidate.matches
    ):
        raise ArtifactError(f"inspection score replay failed for '{candidate.candidate_id}'")
    motifs = {motif.motif_id: motif for motif in spec.motifs}
    matches = tuple(
        _support(motifs[match.motif_id], candidate, match) for match in candidate.matches
    )
    avoider_models = {item.motif.motif_id: item.motif for item in spec.avoiders}
    avoidance_matches = tuple(
        _support(avoider_models[match.motif_id], candidate, match)
        for match in candidate.avoidance_matches
    )
    coverage = [0] * len(candidate.sequence)
    for match in (*matches, *avoidance_matches):
        for position in range(match.start, match.end):
            coverage[position] += 1
    limiting = tuple(
        sorted(
            match.motif_id
            for match in matches
            if math.isclose(match.normalized_score, candidate.balance_score, abs_tol=1.0e-12)
        )
    )
    return InspectionCandidate(
        candidate_id=candidate.candidate_id,
        rank=candidate.rank,
        sequence=candidate.sequence,
        complement_sequence=candidate.sequence.translate(str.maketrans("ACGT", "TGCA")),
        balance_score=candidate.balance_score,
        limiting_motif_ids=limiting,
        shared_coordinates=tuple(index for index, count in enumerate(coverage) if count > 1),
        nearest_neighbor_distance=nearest_neighbor_distance,
        matches=matches,
        avoidance_matches=avoidance_matches,
        constraint_status=candidate.constraint_status,
        max_avoidance_excess=candidate.max_avoidance_excess,
    )


def project_candidate(spec: DesignSpec, candidate: Candidate) -> InspectionCandidate:
    """Replay and project one candidate into renderer-ready computational score support."""

    support_rows = sum(motif.width for motif in spec.motifs) + sum(
        item.motif.width for item in spec.avoiders
    )
    if support_rows > MAX_INSPECTION_SUPPORT_ROWS:
        raise ArtifactError(
            "inspection position-support rows exceed the projection limit; "
            f"requested={support_rows}, limit={MAX_INSPECTION_SUPPORT_ROWS}"
        )

    return _project_candidate(spec, candidate, compile_design(spec))


def _distance_values(
    candidates: tuple[Candidate, ...],
) -> tuple[DistanceInspection, dict[str, float | None]]:
    if len(candidates) < 2:
        return (
            DistanceInspection(status="not_applicable", base_comparisons=0),
            {candidates[0].candidate_id: None},
        )
    sequence_length = len(candidates[0].sequence)
    pair_count = len(candidates) * (len(candidates) - 1) // 2
    base_comparisons = pair_count * sequence_length
    if base_comparisons > MAX_DISTANCE_BASE_COMPARISONS:
        return (
            DistanceInspection(status="not_computed_limit", base_comparisons=base_comparisons),
            {candidate.candidate_id: None for candidate in candidates},
        )
    nearest: dict[str, float | None] = {
        candidate.candidate_id: math.inf for candidate in candidates
    }
    closest_distance = math.inf
    closest_ids: tuple[str, str] | None = None
    for index, left in enumerate(candidates):
        for right in candidates[index + 1 :]:
            distance = (
                math.fsum(
                    1.0
                    for left_base, right_base in zip(left.sequence, right.sequence, strict=True)
                    if left_base != right_base
                )
                / sequence_length
            )
            left_distance = nearest[left.candidate_id]
            right_distance = nearest[right.candidate_id]
            assert left_distance is not None and right_distance is not None
            nearest[left.candidate_id] = min(left_distance, distance)
            nearest[right.candidate_id] = min(right_distance, distance)
            if distance < closest_distance:
                closest_distance = distance
                closest_ids = (left.candidate_id, right.candidate_id)
    if closest_ids is None:  # pragma: no cover - guarded by len(candidates)
        raise AssertionError("pairwise distance projection requires a candidate pair")
    return (
        DistanceInspection(
            status="exact",
            actual_min_distance=closest_distance,
            closest_candidate_ids=closest_ids,
            base_comparisons=base_comparisons,
        ),
        nearest,
    )


def _artifact(
    record: ArtifactDigest,
    payload: bytes,
) -> InspectionArtifact:
    path = record.path
    role: Literal["canonical", "derived"] = "derived" if path == "candidates.fasta" else "canonical"
    return InspectionArtifact(
        key=path.replace(".", "_"),
        role=role,
        path=path,
        format=Path(path).suffix.removeprefix(".") or "directory",
        bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def project_result(source: VerifiedResultSource) -> ResultInspection:
    portfolio = source.portfolio
    selected_sequences = {candidate.sequence for candidate in portfolio.candidates}
    extra_best = (
        1
        if portfolio.manifest.best_observed is not None
        and portfolio.manifest.best_observed.sequence not in selected_sequences
        else 0
    )
    support_rows = (len(portfolio.candidates) + extra_best) * (
        sum(motif.width for motif in portfolio.spec.motifs)
        + sum(item.motif.width for item in portfolio.spec.avoiders)
    )
    if support_rows > MAX_INSPECTION_SUPPORT_ROWS:
        raise ArtifactError(
            "inspection position-support rows exceed the projection limit; "
            f"requested={support_rows}, limit={MAX_INSPECTION_SUPPORT_ROWS}"
        )
    problem = compile_design(portfolio.spec)
    if problem.problem_id != portfolio.problem_id:
        raise ArtifactError("inspection problem replay changed the problem identity")
    distance, nearest = _distance_values(portfolio.candidates)
    candidates = tuple(
        _project_candidate(
            portfolio.spec,
            candidate,
            problem,
            nearest_neighbor_distance=nearest[candidate.candidate_id],
        )
        for candidate in portfolio.candidates
    )
    limiting: dict[str, int] = {}
    for candidate in candidates:
        for motif_id in candidate.limiting_motif_ids:
            limiting[motif_id] = limiting.get(motif_id, 0) + 1

    artifacts = [
        _artifact(record, payload)
        for record, payload in source.artifacts
        if record.path != "report.html"
    ]
    manifest_record = ArtifactDigest(
        path="manifest.json",
        bytes=len(source.canonical_manifest),
        sha256=hashlib.sha256(source.canonical_manifest).hexdigest(),
    )
    artifacts.append(_artifact(manifest_record, source.canonical_manifest))
    spec = portfolio.spec
    manifest = portfolio.manifest
    completion = manifest.completion_status
    best_observed: BestObservedInspection | None = None
    if manifest.best_observed is not None:
        selected_rank = next(
            (
                candidate.rank
                for candidate in candidates
                if candidate.sequence == manifest.best_observed.sequence
            ),
            None,
        )
        projected = _project_candidate(
            portfolio.spec,
            Candidate(
                candidate_id=candidate_id_for_sequence(manifest.best_observed.sequence),
                rank=selected_rank or 1,
                sequence=manifest.best_observed.sequence,
                balance_score=manifest.best_observed.balance_score,
                matches=manifest.best_observed.matches,
                avoidance_matches=manifest.best_observed.avoidance_matches,
                constraint_status=manifest.best_observed.constraint_status,
                max_avoidance_excess=manifest.best_observed.max_avoidance_excess,
                total_avoidance_excess=manifest.best_observed.total_avoidance_excess,
            ),
            problem,
        )
        best_observed = BestObservedInspection(
            candidate_id=projected.candidate_id,
            sequence=projected.sequence,
            complement_sequence=projected.complement_sequence,
            balance_score=projected.balance_score,
            limiting_motif_ids=projected.limiting_motif_ids,
            shared_coordinates=projected.shared_coordinates,
            selected_rank=selected_rank,
            matches=projected.matches,
            avoidance_matches=projected.avoidance_matches,
            constraint_status=projected.constraint_status,
            max_avoidance_excess=projected.max_avoidance_excess,
        )
    return ResultInspection(
        subject_kind=source.subject_kind,
        integrity=IntegrityInspection(
            state=source.integrity_state,
            trust_basis=source.trust_basis,
            checked_identities=source.checked_identities,
        ),
        problem=InspectionProblem(
            problem_id=portfolio.problem_id,
            motifs=tuple(
                InspectionMotif(
                    motif_id=motif.motif_id,
                    width=motif.width,
                    model_digest=motif.model_digest,
                    probabilities=motif.probabilities,
                    background=motif.background,
                    score_min=(
                        compiled.null_mean
                        if spec.scoring_semantics == "normalized_llr_v1"
                        else compiled.score_min
                    ),
                    score_max=(
                        compiled.consensus_score
                        if spec.scoring_semantics == "normalized_llr_v1"
                        else compiled.score_max
                    ),
                    score_reference_semantics=(
                        "null_mean_to_score_max_v1"
                        if spec.scoring_semantics == "normalized_llr_v1"
                        else "attainable_min_max_v2"
                    ),
                    probability_consensus=compiled.probability_consensus,
                    score_maximizing_sequence=compiled.score_maximizing_sequence,
                    source_name=motif.source_name,
                    source_digest=motif.source_digest,
                    canonical_file_name=motif.canonical_file_name,
                    canonical_file_digest=motif.canonical_file_digest,
                    conversion=motif.conversion,
                )
                for motif, compiled in zip(spec.motifs, problem.motifs, strict=True)
            ),
            avoiders=tuple(
                InspectionAvoider(
                    motif_id=item.motif.motif_id,
                    width=item.motif.width,
                    model_digest=item.motif.model_digest,
                    probabilities=item.motif.probabilities,
                    background=item.motif.background,
                    score_min=compiled.motif.score_min,
                    score_max=compiled.motif.score_max,
                    score_reference_semantics="attainable_min_max_v2",
                    probability_consensus=compiled.motif.probability_consensus,
                    score_maximizing_sequence=compiled.motif.score_maximizing_sequence,
                    source_name=item.motif.source_name,
                    source_digest=item.motif.source_digest,
                    canonical_file_name=item.motif.canonical_file_name,
                    canonical_file_digest=item.motif.canonical_file_digest,
                    conversion=item.motif.conversion,
                    score_ceiling=item.score_ceiling,
                )
                for item, compiled in zip(spec.avoiders, problem.avoiders, strict=True)
            ),
            length=spec.length,
            strands=spec.strands,
            scoring_semantics=spec.scoring_semantics,
            objective_semantics=spec.objective_semantics,
            tie_break_semantics=spec.tie_break_semantics,
        ),
        run=InspectionRun(
            run_id=portfolio.run_id,
            bundle_id=manifest.bundle_id,
            package_version=manifest.package_version,
            runtime_contract=manifest.runtime_contract,
            build_lock_sha256=manifest.build_lock_sha256,
            seed=spec.seed,
            min_distance_requested=spec.min_distance,
        ),
        delivery=DeliveryInspection(
            requested_count=spec.count,
            delivered_count=len(candidates),
            status="complete" if len(candidates) == spec.count else "incomplete",
        ),
        search=SearchInspection(
            completion=completion,
            stop_reason=(
                "sequence_space_exhausted"
                if completion == "exhaustive"
                else "evaluation_budget_exhausted"
            ),
            search_engine=manifest.search_engine,
            search_engine_version=manifest.search_engine_version,
            rng=manifest.rng,
            validation_status=manifest.search_validation_status,
            evaluation_budget=spec.evaluations,
            evaluator_calls=manifest.evaluation_count,
            unique_evaluations=manifest.unique_evaluations,
            checkpoints=manifest.search_diagnostics.checkpoints,
            restarts=manifest.search_diagnostics.restarts,
            restart_final_scores=manifest.search_diagnostics.restart_final_scores,
            restart_final_constraint_statuses=(
                manifest.search_diagnostics.restart_final_constraint_statuses
                if manifest.search_diagnostics.schema_version == "search-diagnostics/v2"
                else tuple("feasible" for _ in range(manifest.search_diagnostics.restarts))
            ),
            proposals=manifest.search_diagnostics.proposals,
        ),
        portfolio=InspectionPortfolio(
            best_observed_score=manifest.search_diagnostics.best_score,
            best_observed=best_observed,
            score_min=min(candidate.balance_score for candidate in candidates),
            score_max=max(candidate.balance_score for candidate in candidates),
            distance=distance,
            limiting_motifs=tuple(
                LimitingMotifCount(motif_id=motif_id, candidates=count)
                for motif_id, count in sorted(limiting.items())
            ),
            candidates=candidates,
        ),
        artifacts=tuple(sorted(artifacts, key=lambda item: item.path)),
        execution=source.execution,
    )


def project_execution(
    workspace: ExecutionWorkspace,
    receipt: ExecutionReceipt,
) -> ExecutionInspection:
    started = datetime.strptime(receipt.started_at_utc, "%Y-%m-%dT%H:%M:%SZ")
    finished = datetime.strptime(receipt.finished_at_utc, "%Y-%m-%dT%H:%M:%SZ")
    return ExecutionInspection(
        workspace_id=workspace.workspace_id,
        producer_revision=receipt.producer_revision,
        release_artifact_name=receipt.release_artifact_name,
        release_artifact_sha256=receipt.release_artifact_sha256,
        runtime_package_tree_sha256=receipt.runtime_package_tree_sha256,
        receipt_sha256=workspace.receipt.sha256,
        manifest_sha256=receipt.manifest_sha256,
        started_at_utc=receipt.started_at_utc,
        finished_at_utc=receipt.finished_at_utc,
        duration_seconds=(finished - started).total_seconds(),
        python_version=receipt.python_version,
        platform_system=receipt.platform_system,
        platform_machine=receipt.platform_machine,
        dependencies=receipt.dependencies,
    )


def _distance_inspection(candidates: tuple[Candidate, ...]) -> DistanceInspection:
    """Compatibility-free test seam for bounded distance projection."""

    return _distance_values(candidates)[0]

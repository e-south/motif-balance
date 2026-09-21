"""Summarize verified design results and provenance in readable terminal text.

Maintainer(s): Eric J. South, Dunlop Lab
"""

from __future__ import annotations

from ..model import ResultInspection


def _words(value: str) -> str:
    return value.replace("_", " ")


def render_text(inspection: ResultInspection) -> str:
    """Render the ordinary one-result terminal review."""

    best = inspection.portfolio.candidates[0]
    best_observed = inspection.portfolio.best_observed
    if best_observed.selected_rank is None:
        observed_lede = (
            f"The best observed balance_score was "
            f"{best_observed.balance_score:.6g}; that sequence was not selected "
            "under the portfolio constraint."
        )
    else:
        observed_lede = (
            f"The best observed balance_score was "
            f"{best_observed.balance_score:.6g}; that sequence was selected at "
            f"rank {best_observed.selected_rank}."
        )
    lines = [
        (
            f"Returned {inspection.delivery.delivered_count} of "
            f"{inspection.delivery.requested_count} requested sequences. "
            f"{observed_lede}"
        ),
        "",
        (
            f"Status: delivery {_words(inspection.delivery.status)} · "
            f"search {_words(inspection.search.completion)} · "
            f"integrity {_words(inspection.integrity.state)}"
        ),
        "",
        f"Problem: {inspection.problem.problem_id}",
        f"Run: {inspection.run.run_id}",
        f"Bundle: {inspection.run.bundle_id}",
        f"Motifs: {', '.join(motif.motif_id for motif in inspection.problem.motifs)}",
        f"Length: {inspection.problem.length} nt",
        f"Evaluator calls: {inspection.search.evaluator_calls}",
        f"Stop reason: {_words(inspection.search.stop_reason)}",
        f"Best observed balance_score: {inspection.portfolio.best_observed_score:.17g}",
        f"Top candidate: rank {best.rank}, {best.candidate_id}",
        f"Top balance_score: {best.balance_score:.17g}",
        f"Limiting specification: {', '.join(best.limiting_motif_ids)}",
        "",
        "Use --format svg --view candidate|portfolio|search for a figure, or",
        "--format html --out FILE for the self-contained shareable review.",
    ]
    if best_observed.selected_rank is None:
        lines.insert(
            13,
            f"Best observed sequence: {best_observed.sequence}; "
            "not selected under the portfolio constraint.",
        )
    else:
        lines.insert(
            13,
            f"Best observed sequence: {best_observed.sequence}; "
            f"selected at rank {best_observed.selected_rank}.",
        )
    if inspection.execution is not None:
        lines[6:6] = [
            f"Workspace: {inspection.execution.workspace_id}",
            f"Release SHA-256: {inspection.execution.release_artifact_sha256}",
            f"Producer revision: {inspection.execution.producer_revision}",
            "",
        ]
    specifications = ", ".join(
        f"{item.motif_id}: {item.direction}" for item in inspection.problem.motifs
    )
    lines.insert(12, f"Specifications: {specifications}")
    lines.insert(
        13,
        "Avoid satisfaction is 1 - attainment on the same model-relative scale; "
        "it does not establish biological absence.",
    )
    return "\n".join(lines) + "\n"

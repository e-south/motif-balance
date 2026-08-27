from __future__ import annotations

from ..model import ResultInspection


def _words(value: str) -> str:
    return value.replace("_", " ")


def render_text(inspection: ResultInspection) -> str:
    """Render the ordinary one-result terminal review."""

    best = inspection.portfolio.candidates[0]
    motif_count = len(inspection.problem.motifs)
    lines = [
        (
            f"Returned {inspection.delivery.delivered_count} of "
            f"{inspection.delivery.requested_count} requested sequences. "
            f"The top-ranked candidate balances {motif_count} motif "
            f"{'model' if motif_count == 1 else 'models'} at {best.balance_score:.6g}."
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
        f"Top candidate: rank {best.rank}, {best.candidate_id}",
        f"Top balance_score: {best.balance_score:.17g}",
        f"Limiting motif: {', '.join(best.limiting_motif_ids)}",
        "",
        "Use --format svg --view candidate|portfolio|search for a figure, or",
        "--format html --out FILE for the self-contained shareable review.",
    ]
    if inspection.execution is not None:
        lines[6:6] = [
            f"Workspace: {inspection.execution.workspace_id}",
            f"Release SHA-256: {inspection.execution.release_artifact_sha256}",
            f"Producer revision: {inspection.execution.producer_revision}",
            "",
        ]
    return "\n".join(lines) + "\n"

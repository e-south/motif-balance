from __future__ import annotations

from html import escape
from itertools import islice

from motif_balance.errors import ArtifactError

from ..limits import MAX_HTML_CANDIDATES, MAX_HTML_CHECKPOINTS, MAX_HTML_MATCHES
from ..model import InspectionCandidate, ResultInspection
from .candidate import render_candidate_svg
from .portfolio import render_portfolio_svg
from .search import render_search_svg


def _words(value: str) -> str:
    return value.replace("_", " ")


def _rows(rows: list[tuple[str, object]]) -> str:
    return "\n".join(
        f'<tr><th scope="row">{escape(label)}</th><td><code>{escape(str(value))}</code></td></tr>'
        for label, value in rows
    )


def _table(headings: tuple[str, ...], rows: str) -> str:
    head = "".join(f"<th>{escape(heading)}</th>" for heading in headings)
    return (
        '<div class="table-wrap"><table><thead><tr>'
        f"{head}</tr></thead><tbody>{rows}</tbody></table></div>"
    )


def _details(label: str, contents: str, *, opened: bool = False) -> str:
    open_attr = " open" if opened else ""
    return (
        f"<details{open_attr}><summary>{escape(label)}</summary>"
        f'<div class="detail">{contents}</div></details>'
    )


def _selected_candidate(
    inspection: ResultInspection,
    candidate_rank: int,
) -> InspectionCandidate:
    for candidate in inspection.portfolio.candidates:
        if candidate.rank == candidate_rank:
            return candidate
    raise ArtifactError(f"candidate rank {candidate_rank} is not present in this result")


def _candidate_rows(inspection: ResultInspection) -> tuple[str, str]:
    shown = inspection.portfolio.candidates[:MAX_HTML_CANDIDATES]
    rows = "\n".join(_candidate_row(candidate) for candidate in shown)
    note = (
        f"<p>Showing {len(shown)} of {len(inspection.portfolio.candidates)} candidates; "
        "the inspection JSON retains every candidate.</p>"
        if len(shown) < len(inspection.portfolio.candidates)
        else ""
    )
    return rows, note


def _candidate_row(candidate: InspectionCandidate) -> str:
    nearest = (
        "not computed"
        if candidate.nearest_neighbor_distance is None
        else format(candidate.nearest_neighbor_distance, ".17g")
    )
    return (
        "<tr>"
        f"<td>{candidate.rank}</td>"
        f"<td><code>{escape(candidate.candidate_id)}</code></td>"
        f'<td><code class="sequence">{escape(candidate.sequence)}</code></td>'
        f"<td>{candidate.balance_score:.17g}</td>"
        f"<td>{escape(', '.join(candidate.limiting_motif_ids))}</td>"
        f"<td>{nearest}</td>"
        "</tr>"
    )


def _match_rows(inspection: ResultInspection) -> tuple[str, str]:
    total = sum(len(candidate.matches) for candidate in inspection.portfolio.candidates)
    shown = tuple(
        islice(
            (
                (candidate, match)
                for candidate in inspection.portfolio.candidates
                for match in candidate.matches
            ),
            MAX_HTML_MATCHES,
        )
    )
    rows = "\n".join(
        "<tr>"
        f"<td>{candidate.rank}</td><td>{escape(match.motif_id)}</td>"
        f"<td><code>[{match.start}, {match.end})</code></td>"
        f"<td>{escape(match.strand)}</td>"
        f'<td><code class="sequence">{escape(match.matched_sequence)}</code></td>'
        f"<td>{match.raw_score:.17g}</td><td>{match.normalized_score:.17g}</td>"
        "</tr>"
        for candidate, match in shown
    )
    note = (
        f"<p>Showing {len(shown)} of {total} matches; the inspection JSON and "
        "verified matches.tsv retain every record.</p>"
        if len(shown) < total
        else ""
    )
    return rows, note


def _checkpoint_rows(inspection: ResultInspection) -> tuple[str, str]:
    shown = inspection.search.checkpoints[:MAX_HTML_CHECKPOINTS]
    rows = "\n".join(
        f"<tr><td>{item.evaluations}</td><td>{item.best_score:.17g}</td></tr>" for item in shown
    )
    note = (
        f"<p>Showing {len(shown)} of {len(inspection.search.checkpoints)} checkpoints; "
        "the inspection JSON retains every recorded checkpoint.</p>"
        if len(shown) < len(inspection.search.checkpoints)
        else ""
    )
    return rows, note


def _execution_table(inspection: ResultInspection) -> str:
    execution = inspection.execution
    if execution is None:
        return ""
    rows = _rows(
        [
            ("Workspace", execution.workspace_id),
            ("Producer revision", execution.producer_revision),
            ("Release artifact", execution.release_artifact_name),
            ("Release SHA-256", execution.release_artifact_sha256),
            ("Runtime package tree SHA-256", execution.runtime_package_tree_sha256),
            ("Receipt SHA-256", execution.receipt_sha256),
            ("Manifest SHA-256", execution.manifest_sha256),
            ("Started", execution.started_at_utc),
            ("Finished", execution.finished_at_utc),
            ("Duration seconds", execution.duration_seconds),
            ("Python", execution.python_version),
            ("Platform", f"{execution.platform_system} {execution.platform_machine}"),
        ]
    )
    return f"<table><tbody>{rows}</tbody></table>"


def _execution_details(inspection: ResultInspection) -> str:
    table = _execution_table(inspection)
    return "" if not table else _details("Execution provenance", table)


def _search_section(inspection: ResultInspection) -> str:
    payload = render_search_svg(inspection)
    if payload is None:
        return "<p>No checkpoint record was retained for this result.</p>"
    svg = payload.decode()
    return (
        f'<div class="figure-scroll" aria-label="Search record figure">{svg}</div>'
        "<p>This is a running maximum of the recorded published hard score. "
        "It does not show accepted-state history, literal hill climbing, chain dynamics, "
        "convergence, or global optimality.</p>"
    )


def _styles() -> str:
    return """
:root {
  --ink:#172021; --muted:#5b6667; --line:#d9dfdd;
  --paper:#fbfcfa; --accent:#d97757;
}
* { box-sizing:border-box; }
html, body { max-width:100%; overflow-x:hidden; }
body {
  margin:0; background:var(--paper); color:var(--ink);
  font:16px/1.5 system-ui,sans-serif;
}
main { width:100%; min-width:0; max-width:1180px; margin:auto; padding:2.5rem 1.1rem 5rem; }
h1 { font-size:clamp(2rem,5vw,3.2rem); line-height:1.05; margin:0 0 .8rem; overflow-wrap:anywhere; }
h2 { margin:2.8rem 0 1rem; border-top:1px solid var(--line); padding-top:1rem; }
h3 { margin-top:1.6rem; }
.lede { max-width:74ch; color:var(--muted); font-size:1.12rem; }
.contract { font-weight:650; letter-spacing:.01em; overflow-wrap:anywhere; }
.status-line { color:var(--muted); margin:1rem 0 2rem; }
.status-line span { white-space:nowrap; }
.figure-scroll {
  overflow-x:auto; inline-size:100%; max-width:100%; min-width:0; border:1px solid var(--line);
  padding:.5rem; background:var(--paper);
}
.figure-scroll svg { display:block; max-width:none; min-width:60rem; height:auto; }
.table-wrap { overflow-x:auto; max-width:100%; min-width:0; }
table { border-collapse:collapse; width:max-content; min-width:48rem; font-size:.9rem; }
th { text-align:left; color:var(--muted); }
th,td { border-bottom:1px solid var(--line); padding:.58rem; vertical-align:top; }
code { font:.82rem/1.4 ui-monospace,monospace; }
.sequence { letter-spacing:.05em; white-space:nowrap; }
details { border-top:1px solid var(--line); padding-top:1rem; margin-top:1rem; }
summary { cursor:pointer; font-weight:650; }
.detail { padding-top:.8rem; }
.print-records { display:none; }
.scope { border-left:3px solid var(--accent); padding:.2rem 1rem; max-width:82ch; }
@media(max-width:720px) {
  main { padding-inline:.8rem; }
  h1 { max-width:14ch; font-size:1.85rem; }
}
@media print {
  main { max-width:none; }
  .figure-scroll { overflow:visible; border:0; padding:0; }
  .figure-scroll svg { min-width:0; width:100%; height:auto; }
  .screen-records { display:none !important; }
  .print-records { display:block; }
}
"""


def _exact_records(inspection: ResultInspection) -> str:
    candidate_rows, candidate_note = _candidate_rows(inspection)
    match_rows, match_note = _match_rows(inspection)
    checkpoint_rows, checkpoint_note = _checkpoint_rows(inspection)
    candidate_table = _table(
        ("Rank", "ID", "Sequence", "balance_score", "Limiting motif", "Nearest distance"),
        candidate_rows,
    )
    match_table = _table(
        ("Rank", "Motif", "Coordinates", "Strand", "Oriented word", "Raw LLR", "Normalized"),
        match_rows,
    )
    checkpoint_table = _table(
        ("Evaluator calls", "Best observed balance_score"),
        checkpoint_rows,
    )
    screen = "".join(
        (
            _details("Candidate table", candidate_note + candidate_table, opened=True),
            _details("Motif match table", match_note + match_table),
            _details("Recorded checkpoints", checkpoint_note + checkpoint_table),
        )
    )
    printed = "".join(
        (
            f"<h3>Candidate table</h3>{candidate_note}{candidate_table}",
            f"<h3>Motif match table</h3>{match_note}{match_table}",
            f"<h3>Recorded checkpoints</h3>{checkpoint_note}{checkpoint_table}",
        )
    )
    return f'<div class="screen-records">{screen}</div><div class="print-records">{printed}</div>'


def _provenance_section(inspection: ResultInspection) -> str:
    provenance = _rows(
        [
            ("Problem", inspection.problem.problem_id),
            ("Run", inspection.run.run_id),
            ("Bundle", inspection.run.bundle_id),
            ("Package", inspection.run.package_version),
            ("Runtime contract", inspection.run.runtime_contract),
            ("Build lock SHA-256", inspection.run.build_lock_sha256),
            ("Trust basis", inspection.integrity.trust_basis),
            ("Checked identities", ", ".join(inspection.integrity.checked_identities) or "none"),
        ]
    )
    motif_rows = "\n".join(
        "<tr>"
        f"<td>{escape(motif.motif_id)}</td><td>{motif.width}</td>"
        f"<td><code>{motif.model_digest}</code></td>"
        f"<td>{escape(motif.source_name or 'not disclosed')}</td>"
        "</tr>"
        for motif in inspection.problem.motifs
    )
    artifact_rows = "\n".join(
        "<tr>"
        f"<td>{escape(item.role)}</td><td><code>{escape(item.path)}</code></td>"
        f"<td>{item.bytes}</td><td><code>{item.sha256}</code></td>"
        "</tr>"
        for item in inspection.artifacts
    )
    motif_table = _table(("Motif", "Width", "Model digest", "Source"), motif_rows)
    artifact_table = _table(("Role", "Path", "Bytes", "SHA-256"), artifact_rows)
    screen = "".join(
        (
            _details("Motif identities", motif_table),
            _details("Artifact inventory", artifact_table),
            _execution_details(inspection),
        )
    )
    printed = "".join(
        (
            f"<h3>Motif identities</h3>{motif_table}",
            f"<h3>Artifact inventory</h3>{artifact_table}",
            (
                f"<h3>Execution provenance</h3>{_execution_table(inspection)}"
                if inspection.execution is not None
                else ""
            ),
        )
    )
    return "".join(
        (
            '<h2>Provenance and integrity</h2><div class="table-wrap">',
            f"<table><tbody>{provenance}</tbody></table></div>",
            f'<div class="screen-records">{screen}</div>',
            f'<div class="print-records">{printed}</div>',
        )
    )


def _status_line(inspection: ResultInspection) -> str:
    delivery = (
        f"Portfolio delivery: {inspection.delivery.delivered_count}/"
        f"{inspection.delivery.requested_count} {escape(_words(inspection.delivery.status))}"
    )
    completion = (
        f"Search completion: {escape(_words(inspection.search.completion))} at "
        f"{inspection.search.evaluator_calls} evaluator calls"
    )
    integrity = f"Artifact integrity: {escape(_words(inspection.integrity.state))}"
    return (
        '<p class="status-line" aria-label="Independent result states">'
        f"<span>{delivery}</span> · <span>{completion}</span> · <span>{integrity}</span></p>"
    )


def render_html(
    inspection: ResultInspection,
    *,
    candidate_rank: int = 1,
) -> bytes:
    """Compose the single linear, self-contained, script-free result review."""

    selected = _selected_candidate(inspection, candidate_rank)
    candidate_svg = render_candidate_svg(inspection, candidate_rank=candidate_rank).decode()
    portfolio_svg = render_portfolio_svg(inspection).decode()
    lede = (
        f"Returned {inspection.delivery.delivered_count} of "
        f"{inspection.delivery.requested_count} requested sequences. The selected rank "
        f"{selected.rank} candidate balances {len(inspection.problem.motifs)} motif models "
        f"at {selected.balance_score:.6g}."
    )
    scope = " ".join(inspection.claim_scope)
    distance = (
        "no minimum distance"
        if inspection.run.min_distance_requested is None
        else f"minimum distance {inspection.run.min_distance_requested:.6g}"
    )
    contract = (
        f"{' + '.join(m.motif_id for m in inspection.problem.motifs)} · "
        f"{inspection.problem.length} nt · {inspection.problem.strands} strands · "
        f"{inspection.delivery.requested_count} candidates · {distance}"
    )
    body = "".join(
        (
            "<h1>Motif Balance result review</h1>",
            f'<h2>Result</h2><p class="lede">{escape(lede)}</p>',
            _status_line(inspection),
            f'<h2>Design contract</h2><p class="contract">{escape(contract)}</p>',
            "<h2>Portfolio balance</h2>",
            "<p>Rows retain deterministic rank order and columns retain canonical motif order. "
            "Numeric values are authoritative; color is only a reading aid.</p>",
            '<div class="figure-scroll" aria-label="Portfolio balance figure">',
            f"{portfolio_svg}</div>",
            "<h2>Selected candidate</h2>",
            f"<p>Rank {selected.rank} is shown by default. Supplied motif models map to one "
            "representative match per motif, including exact strand, coordinates, overlap, "
            "and observed-base score support.</p>",
            '<div class="figure-scroll" aria-label="Selected candidate realization figure">',
            f"{candidate_svg}</div>",
            '<div class="scope"><h3>Interpretation boundary</h3>',
            "<p>Predicted motif matches are model-defined sequence evidence, not measurements "
            "of binding, occupancy, competition, cooperativity, expression, or regulatory "
            "function.</p></div>",
            f"<h2>Exact records</h2>{_exact_records(inspection)}",
            _details("Search diagnostics", _search_section(inspection)),
            _provenance_section(inspection),
            f'<p class="lede">Full claim scope: {escape(scope)}</p>',
        )
    )
    document = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Motif Balance result review</title><style>{_styles()}</style>"
        f"</head><body><main>{body}</main></body></html>"
    )
    return document.encode("utf-8")

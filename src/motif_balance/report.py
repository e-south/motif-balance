from __future__ import annotations

from html import escape

from motif_balance.model import Candidate, DesignSpec


def _candidate_rows(candidates: tuple[Candidate, ...]) -> str:
    rows: list[str] = []
    for candidate in candidates:
        limiting_score = min(match.normalized_score for match in candidate.matches)
        limiting = ", ".join(
            escape(match.motif_id)
            for match in sorted(candidate.matches, key=lambda match: match.motif_id)
            if abs(match.normalized_score - limiting_score) <= 1.0e-12
        )
        score_summary = "<br>".join(
            f"<span><strong>{escape(match.motif_id)}</strong> {match.normalized_score:.6f}</span>"
            for match in sorted(candidate.matches, key=lambda match: match.motif_id)
        )
        rows.append(
            "<tr>"
            f"<td>{candidate.rank}</td>"
            f"<td><code>{escape(candidate.candidate_id)}</code></td>"
            f'<td><code class="sequence">{escape(candidate.sequence)}</code></td>'
            f"<td>{candidate.balance_score:.6f}</td>"
            f"<td>{limiting}</td>"
            f'<td class="scores">{score_summary}</td>'
            "</tr>"
        )
    return "\n".join(rows)


def _match_rows(candidates: tuple[Candidate, ...]) -> str:
    rows: list[str] = []
    for candidate in candidates:
        for match in sorted(candidate.matches, key=lambda item: item.motif_id):
            rows.append(
                "<tr>"
                f"<td><code>{escape(candidate.candidate_id)}</code></td>"
                f"<td>{escape(match.motif_id)}</td>"
                f"<td>{match.normalized_score:.6f}</td>"
                f"<td>{match.raw_score:.6f}</td>"
                f"<td><code>[{match.start}, {match.end})</code></td>"
                f"<td>{match.start + 1}&ndash;{match.end}</td>"
                f"<td>{match.strand}</td>"
                f'<td><code class="sequence">{escape(match.matched_sequence)}</code></td>'
                "</tr>"
            )
    return "\n".join(rows)


def render_report(spec: DesignSpec, candidates: tuple[Candidate, ...]) -> bytes:
    motif_rows = "\n".join(
        "<tr>"
        f"<td>{escape(motif.motif_id)}</td>"
        f"<td>{motif.width}</td>"
        f"<td><code>{motif.model_digest}</code></td>"
        "</tr>"
        for motif in spec.motifs
    )
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Motif Balance result</title>
  <style>
    :root {{ color-scheme: light; --ink: #172021; --muted: #5b6667; --line: #d9dfdd;
      --paper: #fbfcfa; --accent: #16635b; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--paper); color: var(--ink);
      font: 16px/1.5 ui-sans-serif, system-ui, sans-serif; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 3rem 1.25rem 5rem; }}
    h1 {{ font-size: clamp(2rem, 5vw, 3.6rem); line-height: 1; margin: 0 0 1rem; }}
    h2 {{ margin-top: 3rem; border-top: 1px solid var(--line); padding-top: 1.25rem; }}
    .lede {{ max-width: 72ch; color: var(--muted); font-size: 1.12rem; }}
    .facts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: .75rem; margin: 2rem 0; }}
    .fact {{ border-left: 3px solid var(--accent); padding: .35rem .8rem; }}
    .fact strong {{ display: block; font-size: 1.25rem; }}
    .fact span {{ color: var(--muted); font-size: .85rem; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .9rem; }}
    th {{ text-align: left; color: var(--muted); font-size: .75rem; letter-spacing: .04em;
      text-transform: uppercase; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: .65rem .55rem; vertical-align: top; }}
    code {{ font: .82rem/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; }}
    .sequence {{ letter-spacing: .055em; white-space: nowrap; }}
    .scores span {{ white-space: nowrap; }}
    .scope {{ border: 1px solid var(--line); padding: 1rem 1.2rem; max-width: 80ch; }}
  </style>
</head>
<body>
  <main>
    <h1>Motif Balance result</h1>
    <p class="lede">A fixed-length candidate portfolio evaluated against explicit motif
    models. The public balance score is the weakest normalized motif score for each sequence.</p>

    <div class="facts" aria-label="Design summary">
      <div class="fact"><strong>{len(candidates)}</strong><span>candidates</span></div>
      <div class="fact"><strong>{spec.length} nt</strong><span>exact sequence length</span></div>
      <div class="fact"><strong>{len(spec.motifs)}</strong><span>motif models</span></div>
      <div class="fact"><strong>{spec.evaluations:,}</strong><span>evaluation budget</span></div>
      <div class="fact"><strong>{escape(spec.strands)}</strong><span>strand policy</span></div>
    </div>

    <h2>Candidate portfolio</h2>
    <p>Rank is deterministic by descending balance score and then sequence. The limiting
    motif is the match that defines the reported balance score.</p>
    <div class="table-wrap"><table>
      <thead><tr><th>Rank</th><th>Candidate ID</th><th>Sequence</th><th>Balance score</th>
      <th>Limiting motif</th><th>Per-motif scores</th></tr></thead>
      <tbody>{_candidate_rows(candidates)}</tbody>
    </table></div>

    <h2>Per-motif matches</h2>
    <p>Machine coordinates are <strong>0-based, half-open</strong>. The adjacent human
    coordinates are 1-based and inclusive. Matched sequence is oriented in the motif-scoring
    direction.</p>
    <div class="table-wrap"><table>
      <thead><tr><th>Candidate ID</th><th>Motif</th><th>Normalized</th><th>Raw LLR</th>
      <th>Machine span</th><th>Human span</th><th>Strand</th><th>Oriented match</th></tr></thead>
      <tbody>{_match_rows(candidates)}</tbody>
    </table></div>

    <h2>Model identity</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>Motif</th><th>Width</th><th>Canonical model digest</th></tr></thead>
      <tbody>{motif_rows}</tbody>
    </table></div>

    <h2>Computational scope</h2>
    <div class="scope"><p>This report summarizes deterministic matches and computational
    motif scores under the declared models. It does not establish binding, simultaneous
    occupancy, expression, promoter function, regulatory grammar, synthesis readiness,
    biological portability, or global optimality.</p>
    <p>Use the canonical TSV and JSON files for analysis. This HTML file is a derived,
    regenerable review view.</p></div>
  </main>
</body>
</html>
"""
    return document.encode()

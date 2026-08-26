from __future__ import annotations

from html import escape

from motif_balance.model import Candidate, DesignSpec


def render_report(spec: DesignSpec, candidates: tuple[Candidate, ...]) -> bytes:
    rows = "\n".join(
        "<tr>"
        f"<td>{candidate.rank}</td>"
        f"<td><code>{escape(candidate.sequence)}</code></td>"
        f"<td>{candidate.balance_score:.6f}</td>"
        "</tr>"
        for candidate in candidates
    )
    motif_ids = ", ".join(escape(motif.motif_id) for motif in spec.motifs)
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Motif Balance result</title>
</head>
<body>
  <main>
    <h1>Motif Balance result</h1>
    <p>Motifs: {motif_ids}. Exact sequence length: {spec.length}.</p>
    <table>
      <thead><tr><th>Rank</th><th>Sequence</th><th>Balance score</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <p>This report summarizes computational motif scores. It does not establish binding,
    expression, promoter function, regulatory grammar, or synthesis readiness.</p>
  </main>
</body>
</html>
"""
    return document.encode()

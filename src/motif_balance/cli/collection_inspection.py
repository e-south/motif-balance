"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/cli/collection_inspection.py

Load a collection, rescore displayed members, and select its output representation.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

import json
from pathlib import Path

from motif_balance.errors import ArtifactError
from motif_balance.formats.collection import read_collection
from motif_balance.inspection.collection import inspect_collection
from motif_balance.inspection.render.collection import render_collection_svg
from motif_balance.inspection.render.png import svg_to_png


def collection_payload(
    subject: Path,
    *,
    format_name: str,
    candidate_rank: int | None,
    width: int,
) -> bytes:
    report = read_collection(subject)
    members = inspect_collection(report, candidate_rank=candidate_rank)
    if format_name == "json":
        return (json.dumps([m.model_dump(mode="json") for m in members], indent=2) + "\n").encode()
    if format_name == "text":
        rows = []
        for member in members:
            candidate = member.candidate
            rows.extend(
                [
                    f"Arrangement {candidate.rank}: {candidate.sequence}",
                    f"Balance B = {candidate.balance_score:.6g}",
                ]
            )
            rows.extend(
                f"{m.motif_id}: q = {m.normalized_score:.6g}; "
                f"positions {m.start + 1}\u2013{m.end}, strand {m.strand}"
                for m in candidate.matches
            )
        return ("\n".join(rows) + "\n").encode()
    drawing = render_collection_svg(members)
    if format_name == "svg":
        return drawing
    if format_name == "png":
        return svg_to_png(drawing, width=width)
    if format_name == "html":
        return (
            '<!doctype html><html lang="en"><meta charset="utf-8">'
            "<title>Selected motif arrangements</title>"
            "<style>body{margin:24px auto;max-width:1000px}svg{width:100%;height:auto}</style>"
            "<body>" + drawing.decode() + "</body></html>\n"
        ).encode()
    raise ArtifactError("Unsupported collection inspection format")

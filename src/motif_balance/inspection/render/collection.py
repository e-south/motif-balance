"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/inspection/render/collection.py

Arrange complete inspected collection drawings on one canvas.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from xml.etree import ElementTree as ET

from motif_balance.errors import ArtifactError

from ..candidate_model import CandidateInspection
from ..limits import MAX_SVG_CANDIDATES, MAX_VISUAL_BYTES
from .compact import render_compact_candidate_svg
from .svg_primitives import finish_svg, text


def render_collection_svg(members: tuple[CandidateInspection, ...]) -> bytes:
    """Show each selected layout at the same base spacing, with unique SVG IDs."""
    if not members:
        raise ArtifactError("The collection has no selected sequences to draw")
    if len(members) > MAX_SVG_CANDIDATES:
        raise ArtifactError(
            "Collection exceeds the drawing limit; select one member with --candidate"
        )
    drawings = []
    total_bytes = 0
    for member in members:
        payload = render_compact_candidate_svg(member.problem, member.candidate)
        total_bytes += len(payload)
        if total_bytes > MAX_VISUAL_BYTES:
            raise ArtifactError(
                "Collection exceeds the SVG byte limit; select one member with --candidate"
            )
        drawings.append(ET.fromstring(payload))
    width = max(int(d.attrib["width"]) for d in drawings)
    height = sum(int(d.attrib["height"]) + 32 for d in drawings)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">',
        "<title>Selected motif arrangements</title>",
        f'<rect width="{width}" height="{height}" rx="18" fill="#F4F9F7"/>',
    ]
    y = 0
    for member, drawing in zip(members, drawings, strict=True):
        rank = member.candidate.rank
        for node in drawing.iter():
            if "id" in node.attrib:
                node.set("id", f"arrangement-{rank}-{node.attrib['id']}")
            if "aria-labelledby" in node.attrib:
                node.set(
                    "aria-labelledby",
                    " ".join(
                        f"arrangement-{rank}-{item}"
                        for item in node.attrib["aria-labelledby"].split()
                    ),
                )
        parts.append(
            f'<g data-collection-rank="{rank}" data-sequence="{member.candidate.sequence}" '
            f'transform="translate(0 {y})">'
        )
        parts.append(
            text(width / 2, 24, f"Arrangement {rank}", size=20, anchor="middle", weight=650)
        )
        drawing.set("y", "32")
        parts.append(ET.tostring(drawing, encoding="unicode"))
        parts.append("</g>")
        y += int(drawing.attrib["height"]) + 32
    return finish_svg([*parts, "</svg>\n"])

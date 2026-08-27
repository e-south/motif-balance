from __future__ import annotations

from ..model import ResultInspection


def render_inspection_json(inspection: ResultInspection) -> bytes:
    """Render the complete path-free typed inspection projection."""

    return (inspection.model_dump_json(indent=2) + "\n").encode("utf-8")

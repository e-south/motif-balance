"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/inspection/render/png.py

Rasterize package-generated SVG at a bounded, explicit pixel width.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

import math
from xml.etree import ElementTree as ET

from motif_balance.errors import ArtifactError

from ..limits import MAX_VISUAL_BYTES


def svg_to_png(svg: bytes, *, width: int = 1800) -> bytes:
    """Convert an internal SVG view, with no network access or arbitrary file reads."""
    if type(width) is not int or not 400 <= width <= 4096:
        raise ArtifactError("PNG width must be an integer between 400 and 4096 pixels")
    if len(svg) > MAX_VISUAL_BYTES:
        raise ArtifactError("SVG exceeds the byte limit")
    if b"<!DOCTYPE" in svg or b"<!ENTITY" in svg:
        raise ArtifactError("PNG input must not declare external resources or entities")
    root = ET.fromstring(svg)
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] in {"image", "style", "foreignObject", "script"} or any(
            (key.rsplit("}", 1)[-1] == "href" and not value.startswith("#"))
            or "url(" in value.lower()
            for key, value in node.attrib.items()
        ):
            raise ArtifactError("PNG input must not refer to external resources")
    source_width, source_height = float(root.attrib["width"]), float(root.attrib["height"])
    if not all(math.isfinite(value) and value > 0 for value in (source_width, source_height)):
        raise ArtifactError("SVG dimensions must be finite and positive")
    height = round(width * source_height / source_width)
    if width * height > 24_000_000:
        raise ArtifactError("PNG exceeds 24 million pixels; lower --width or select one candidate")
    try:
        import resvg_py
    except ImportError as exc:
        raise ArtifactError(
            'PNG export needs the visualization extra: uv add "motif-balance[visualization]"'
        ) from exc
    return resvg_py.svg_to_bytes(svg_string=svg.decode(), width=width)

from __future__ import annotations

import hashlib
import re
from html import escape

from motif_balance.errors import ArtifactError

from ..limits import MAX_VISUAL_BYTES

INK = "#172021"
MUTED = "#5B6667"
LINE = "#D9DFDD"
PAPER = "#FBFCFA"
SOFT = "#E8EFED"
ACCENT = "#D97757"
POSITIVE = "#16635B"
NEGATIVE = "#A44838"
SHARED = "#F3D9A6"

_DOMAIN_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
_CANDIDATE_ID = re.compile(r"^candidate-[0-9a-f]{16}$")
_MOTIF_PALETTE = (
    "#4477AA",
    "#EE6677",
    "#228833",
    "#CCBB44",
    "#66CCEE",
    "#AA3377",
    "#EE7733",
    "#009988",
    "#CC3311",
)


def safe_text(value: object) -> str:
    return escape(str(value), quote=True)


def motif_id(value: str) -> str:
    if not _DOMAIN_ID.fullmatch(value):
        raise ArtifactError("derived visualization encountered an invalid motif identifier")
    return safe_text(value)


def motif_color(value: str) -> str:
    """Return one stable categorical color for a validated motif identifier."""

    motif_id(value)
    index = int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest()[:2], "big")
    return _MOTIF_PALETTE[index % len(_MOTIF_PALETTE)]


def candidate_id(value: str) -> str:
    if not _CANDIDATE_ID.fullmatch(value):
        raise ArtifactError("derived visualization encountered an invalid candidate identifier")
    return value


def svg_start(
    *,
    width: int,
    height: int,
    title_id: str,
    desc_id: str,
    view_id: str,
) -> list[str]:
    return [
        '<svg xmlns="http://www.w3.org/2000/svg"',
        f' id="{view_id}" width="{width}" height="{height}"',
        f' viewBox="0 0 {width} {height}" role="img"',
        f' aria-labelledby="{title_id} {desc_id}"',
        ' preserveAspectRatio="xMinYMin meet">',
    ]


def finish_svg(parts: list[str]) -> bytes:
    payload = "".join(parts).encode("utf-8")
    if len(payload) > MAX_VISUAL_BYTES:
        raise ArtifactError("derived visualization exceeds the byte limit")
    return payload


def text(
    x: float,
    y: float,
    value: object,
    *,
    size: int = 12,
    fill: str = INK,
    anchor: str | None = None,
    weight: int | None = None,
    family: str = "system-ui,sans-serif",
    extra: str = "",
) -> str:
    anchor_attr = f' text-anchor="{anchor}"' if anchor else ""
    weight_attr = f' font-weight="{weight}"' if weight else ""
    return (
        f'<text x="{x:.3f}" y="{y:.3f}" fill="{fill}" '
        f'font-family="{family}" font-size="{size}"{anchor_attr}{weight_attr}{extra}>'
        f"{safe_text(value)}</text>"
    )

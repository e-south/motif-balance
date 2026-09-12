"""Shared information-height Arial glyphs for candidate and pre-search views."""

import math

from .logo_glyphs import ARIAL_BOLD_GLYPHS

PIXELS_PER_BIT = 36.0


def information_bits(row: tuple[float, float, float, float]) -> float:
    entropy = -sum(p * math.log2(p) for p in row if p)
    return min(2.0, max(0.0, 2.0 - entropy))


def information_letter(
    *,
    base: str,
    probability: float,
    bits: float,
    color: str,
    center_x: float,
    bottom_y: float,
    width: float,
    glyph_id: str,
    observed: bool | None = None,
) -> str:
    height = probability * bits * PIXELS_PER_BIT
    if height == 0:
        return ""
    observed_attribute = "" if observed is None else f'data-observed="{str(observed).lower()}" '
    return (
        f'<path class="information-logo-letter" id="{glyph_id}" '
        f'd="{ARIAL_BOLD_GLYPHS[base]}" fill="{color}" fill-rule="evenodd" '
        'data-font-family="Arial" data-font-weight="700" '
        f'transform="translate({center_x - width / 2:.9g} {bottom_y - height:.9g}) '
        f'scale({width / 100:.9g} {height / 100:.9g})" '
        f'data-base="{base}" data-probability="{probability:.17g}" '
        f'data-height-bits="{probability * bits:.17g}" '
        f'{observed_attribute}aria-label="{base}"/>'
    )

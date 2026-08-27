from __future__ import annotations

import math
import re
from heapq import nsmallest
from html import escape
from typing import Literal

from motif_balance.errors import ArtifactError
from motif_balance.model import Candidate, SearchCheckpoint, SearchDiagnostics

_INK = "#172021"
_MUTED = "#5B6667"
_LINE = "#D9DFDD"
_PAPER = "#FBFCFA"
_SOFT = "#E8EFED"
_ACCENT = "#D97757"
_MAX_VISUAL_BYTES = 1_000_000
_MAX_MATCHES = 32
_MAX_PROFILE_CANDIDATES = 24
_MAX_PROFILE_MOTIFS = 16
_MAX_CHECKPOINTS = 256
_MOTIF_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
_CANDIDATE_ID = re.compile(r"^candidate-[0-9a-f]{16}$")


def _finish_svg(parts: list[str]) -> bytes:
    payload = "".join(parts).encode("utf-8")
    if len(payload) > _MAX_VISUAL_BYTES:
        raise ArtifactError("derived visualization exceeds the byte limit")
    return payload


def _motif_id(value: str) -> str:
    if not _MOTIF_ID.fullmatch(value):
        raise ArtifactError("derived visualization encountered an invalid motif identifier")
    return escape(value, quote=True)


def _candidate_id(value: str) -> str:
    if not _CANDIDATE_ID.fullmatch(value):
        raise ArtifactError("derived visualization encountered an invalid candidate identifier")
    return value


def _short_candidate_id(value: str) -> str:
    _candidate_id(value)
    return f"candidate {value[-8:]}"


def _limiting_label(motif_ids: tuple[str, ...]) -> str:
    shown = motif_ids[:2]
    label = ", ".join(value if len(value) <= 20 else f"{value[:19]}…" for value in shown)
    omitted = len(motif_ids) - len(shown)
    return f"{label} +{omitted}" if omitted else label


def _svg_start(*, width: int, height: int, title_id: str, desc_id: str) -> list[str]:
    return [
        '<svg xmlns="http://www.w3.org/2000/svg"',
        f' viewBox="0 0 {width} {height}" role="img"',
        f' aria-labelledby="{title_id} {desc_id}"',
        ' preserveAspectRatio="xMinYMin meet">',
    ]


def render_candidate_match_map(candidate: Candidate) -> bytes:
    """Render a bounded coordinate view of one candidate's best motif matches."""

    sequence_length = len(candidate.sequence)
    if sequence_length == 0:
        raise ArtifactError("candidate match map requires a nonempty sequence")
    candidate_id = _candidate_id(candidate.candidate_id)
    total_limiting = 0
    for match in candidate.matches:
        _motif_id(match.motif_id)
        if match.end > sequence_length:
            raise ArtifactError("candidate match coordinates exceed the candidate length")
        if math.isclose(match.normalized_score, candidate.balance_score, abs_tol=1.0e-12):
            total_limiting += 1
    limiting_shown = tuple(
        nsmallest(
            _MAX_MATCHES,
            (
                match
                for match in candidate.matches
                if math.isclose(
                    match.normalized_score,
                    candidate.balance_score,
                    abs_tol=1.0e-12,
                )
            ),
            key=lambda item: (item.motif_id, item.start, item.end, item.strand),
        )
    )
    remaining = _MAX_MATCHES - len(limiting_shown)
    other_shown = tuple(
        nsmallest(
            remaining,
            (
                match
                for match in candidate.matches
                if not math.isclose(
                    match.normalized_score,
                    candidate.balance_score,
                    abs_tol=1.0e-12,
                )
            ),
            key=lambda item: (item.motif_id, item.start, item.end, item.strand),
        )
    )
    shown = tuple(
        sorted(
            (*limiting_shown, *other_shown),
            key=lambda item: (item.motif_id, item.start, item.end, item.strand),
        )
    )
    total_matches = len(candidate.matches)
    lane_height = 34
    top = 92
    height = top + max(1, len(shown)) * lane_height + 46
    width = 960
    left = 190
    right = 38
    plot_width = width - left - right
    limiting = {match.motif_id for match in limiting_shown}
    parts = _svg_start(
        width=width,
        height=height,
        title_id="candidate-map-title",
        desc_id="candidate-map-desc",
    )
    parts.extend(
        [
            '<title id="candidate-map-title">Best motif-match coordinates</title>',
            '<desc id="candidate-map-desc">',
            f"Candidate {candidate_id}, rank {candidate.rank}; showing ",
            f"{len(shown)} of {total_matches} ",
            "one-best-match records on a shared zero-based half-open coordinate axis. ",
            f"Coral marks {len(limiting_shown)} of {total_limiting} motifs tied for the ",
            "weakest normalized score.</desc>",
            f'<rect width="{width}" height="{height}" fill="{_PAPER}"/>',
            f'<text x="20" y="28" fill="{_INK}" font-family="system-ui,sans-serif" ',
            'font-size="18" font-weight="650">Where motif scores land</text>',
            f'<text x="20" y="52" fill="{_MUTED}" font-family="system-ui,sans-serif" ',
            f'font-size="13">{candidate_id} · rank {candidate.rank} · ',
            f"length {sequence_length} · ",
            f"balance score {candidate.balance_score:.6g} · limiting ",
            f"{len(limiting_shown)}/{total_limiting}</text>",
            f'<line x1="{left}" y1="76" x2="{left + plot_width}" y2="76" ',
            f'stroke="{_INK}" stroke-width="1.5"/>',
            f'<text x="{left}" y="70" fill="{_MUTED}" font-family="system-ui,sans-serif" ',
            'font-size="11">0</text>',
            f'<text x="{left + plot_width}" y="70" text-anchor="end" fill="{_MUTED}" ',
            f'font-family="system-ui,sans-serif" font-size="11">{sequence_length}</text>',
        ]
    )
    for index, match in enumerate(shown):
        y = top + index * lane_height
        x = left + plot_width * match.start / sequence_length
        span_width = max(2.0, plot_width * (match.end - match.start) / sequence_length)
        fill = _ACCENT if match.motif_id in limiting else _SOFT
        label = _motif_id(match.motif_id)
        parts.extend(
            [
                f'<text x="20" y="{y + 16}" fill="{_INK}" ',
                'font-family="ui-monospace,monospace" font-size="12">',
                f"{label} ({match.strand})</text>",
                f'<line x1="{left}" y1="{y + 12}" x2="{left + plot_width}" ',
                f'y2="{y + 12}" stroke="{_LINE}"/>',
                f'<rect x="{x:.3f}" y="{y + 2}" width="{span_width:.3f}" height="20" ',
                f'fill="{fill}" stroke="{_INK}" stroke-width="1" rx="3" ',
                f'data-motif-id="{label}" data-start="{match.start}" ',
                f'data-end="{match.end}" data-strand="{match.strand}"/>',
                f'<text x="{left + plot_width}" y="{y + 28}" text-anchor="end" ',
                f'fill="{_MUTED}" font-family="system-ui,sans-serif" font-size="10">',
                f"[{match.start}, {match.end}) · score {match.normalized_score:.6g}</text>",
            ]
        )
    if len(shown) < total_matches:
        parts.append(
            f'<text x="20" y="{height - 14}" fill="{_MUTED}" '
            'font-family="system-ui,sans-serif" font-size="11">'
            f"Showing {len(shown)} of {total_matches} matches; use the exact match table below."
            "</text>"
        )
    parts.append("</svg>")
    parts[3] = parts[3].replace(
        ">",
        f' data-displayed-limiting="{len(limiting_shown)}" data-total-limiting="{total_limiting}">',
    )
    return _finish_svg(parts)


def _checkpoint_view(
    diagnostics: SearchDiagnostics,
) -> tuple[tuple[SearchCheckpoint, ...], Literal["change_preserving_step", "sampled_markers"]]:
    checkpoints = diagnostics.checkpoints
    if len(checkpoints) <= _MAX_CHECKPOINTS:
        return checkpoints, "change_preserving_step"
    change_indices = tuple(
        index
        for index in range(1, len(checkpoints))
        if checkpoints[index].best_score > checkpoints[index - 1].best_score + 1.0e-12
    )
    essential = {0, len(checkpoints) - 1}
    for index in change_indices:
        essential.update((index - 1, index))
    if len(essential) <= _MAX_CHECKPOINTS:
        return tuple(checkpoints[index] for index in sorted(essential)), "change_preserving_step"
    last = len(checkpoints) - 1
    sampled = tuple(
        sorted({round(index * last / (_MAX_CHECKPOINTS - 1)) for index in range(_MAX_CHECKPOINTS)})
    )
    return tuple(checkpoints[index] for index in sampled), "sampled_markers"


def render_search_progress(diagnostics: SearchDiagnostics) -> bytes:
    """Render recorded best-so-far checkpoints without implying a full trajectory."""

    shown, render_mode = _checkpoint_view(diagnostics)
    total = len(diagnostics.checkpoints)
    width = 960
    height = 330
    left = 82
    right = 36
    top = 78
    bottom = 66
    plot_width = width - left - right
    plot_height = height - top - bottom
    x_max = diagnostics.checkpoints[-1].evaluations
    scores = [checkpoint.best_score for checkpoint in shown]
    y_min = min(scores)
    y_max = max(scores)
    y_span = y_max - y_min

    def x(value: int) -> float:
        return left + plot_width * value / x_max

    def y(value: float) -> float:
        if math.isclose(y_span, 0.0, abs_tol=1.0e-15):
            return top + plot_height / 2
        return top + plot_height * (y_max - value) / y_span

    change_evaluations = tuple(
        shown[index].evaluations
        for index in range(1, len(shown))
        if shown[index].best_score > shown[index - 1].best_score + 1.0e-12
    )
    parts = _svg_start(
        width=width,
        height=height,
        title_id="search-progress-title",
        desc_id="search-progress-desc",
    )
    parts.extend(
        [
            '<title id="search-progress-title">Best-so-far score at recorded checkpoints</title>',
            '<desc id="search-progress-desc">',
            f"A {render_mode.replace('_', ' ')} view showing {len(shown)} of {total} ",
            f"recorded checkpoints through {x_max} evaluator calls. It is not a full ",
            "optimizer trace.</desc>",
            f'<rect width="{width}" height="{height}" fill="{_PAPER}"/>',
            f'<text x="20" y="28" fill="{_INK}" font-family="system-ui,sans-serif" ',
            'font-size="18" font-weight="650">Best-so-far search progress</text>',
            f'<text x="20" y="52" fill="{_MUTED}" font-family="system-ui,sans-serif" ',
            f'font-size="13">{render_mode.replace("_", " ")} · showing ',
            f"{len(shown)} of {total} recorded checkpoints</text>",
            f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" ',
            f'y2="{top + plot_height}" stroke="{_INK}"/>',
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" ',
            f'stroke="{_INK}"/>',
        ]
    )
    if render_mode == "change_preserving_step":
        points: list[tuple[float, float]] = []
        for checkpoint in shown:
            current = (x(checkpoint.evaluations), y(checkpoint.best_score))
            if points:
                points.append((current[0], points[-1][1]))
            points.append(current)
        path = " ".join(
            ("M" if index == 0 else "L") + f" {px:.3f} {py:.3f}"
            for index, (px, py) in enumerate(points)
        )
        parts.append(
            f'<path d="{path}" fill="none" stroke="{_ACCENT}" stroke-width="3" '
            f'stroke-linejoin="round" data-checkpoint-count="{total}" '
            f'data-displayed-checkpoints="{len(shown)}" '
            f'data-render-mode="{render_mode}"/>'
        )
        for evaluation in change_evaluations:
            checkpoint = next(item for item in shown if item.evaluations == evaluation)
            parts.append(
                f'<circle cx="{x(evaluation):.3f}" cy="{y(checkpoint.best_score):.3f}" r="3" '
                f'fill="{_ACCENT}" stroke="{_INK}" '
                f'data-improvement-evaluations="{evaluation}"/>'
            )
    else:
        parts.append(
            f'<g data-checkpoint-count="{total}" data-displayed-checkpoints="{len(shown)}" '
            f'data-render-mode="{render_mode}">'
        )
        for checkpoint in shown:
            parts.append(
                f'<circle cx="{x(checkpoint.evaluations):.3f}" '
                f'cy="{y(checkpoint.best_score):.3f}" r="2.25" fill="{_ACCENT}" '
                f'stroke="{_INK}" stroke-width=".6"/>'
            )
        parts.append("</g>")
    parts.extend(
        [
            f'<circle cx="{x(shown[-1].evaluations):.3f}" cy="{y(shown[-1].best_score):.3f}" ',
            f'r="4" fill="{_ACCENT}" stroke="{_INK}"/>',
            f'<text x="{left + plot_width}" y="{height - 22}" text-anchor="end" ',
            f'fill="{_INK}" font-family="system-ui,sans-serif" font-size="12">',
            f"Evaluator calls: {x_max}</text>",
            f'<text x="{left + 8}" y="{top + 14}" fill="{_MUTED}" ',
            f'font-family="system-ui,sans-serif" font-size="11">{y_max:.6g}</text>',
            f'<text x="{left + 8}" y="{top + plot_height - 8}" fill="{_MUTED}" ',
            f'font-family="system-ui,sans-serif" font-size="11">{y_min:.6g}</text>',
            f'<text x="{left + plot_width - 8}" y="{y(shown[-1].best_score) - 9:.3f}" ',
            f'text-anchor="end" fill="{_INK}" font-family="system-ui,sans-serif" ',
            f'font-size="12">final best {shown[-1].best_score:.6g}</text>',
            "</svg>",
        ]
    )
    return _finish_svg(parts)


def render_portfolio_balance_profile(candidates: tuple[Candidate, ...]) -> bytes:
    """Render bounded within-portfolio per-motif scores with direct labels."""

    if not candidates:
        raise ArtifactError("portfolio balance profile requires at least one candidate")
    shown_candidates = candidates[:_MAX_PROFILE_CANDIDATES]
    total_motifs = len(candidates[0].matches)
    limiting_ids = {
        match.motif_id
        for candidate in shown_candidates
        for match in candidate.matches
        if math.isclose(match.normalized_score, candidate.balance_score, abs_tol=1.0e-12)
    }
    limiting_shown = tuple(sorted(limiting_ids)[:_MAX_PROFILE_MOTIFS])
    remaining = _MAX_PROFILE_MOTIFS - len(limiting_shown)
    other_shown = tuple(
        match.motif_id
        for match in nsmallest(
            remaining,
            (match for match in candidates[0].matches if match.motif_id not in limiting_ids),
            key=lambda item: item.motif_id,
        )
    )
    shown_motifs = tuple(sorted((*limiting_shown, *other_shown)))
    for motif_id in shown_motifs:
        _motif_id(motif_id)
    all_scores = [
        match.normalized_score
        for candidate in shown_candidates
        for match in candidate.matches
        if match.motif_id in shown_motifs
    ]
    max_score = max(all_scores, default=0.0)
    cell_width = 108
    left = 170
    top = 96
    row_height = 34
    hard_min_width = 250
    width = max(760, left + len(shown_motifs) * cell_width + hard_min_width + 24)
    height = top + len(shown_candidates) * row_height + 58
    parts = _svg_start(
        width=width,
        height=height,
        title_id="portfolio-profile-title",
        desc_id="portfolio-profile-desc",
    )
    parts.extend(
        [
            '<title id="portfolio-profile-title">Within-portfolio motif score profile</title>',
            '<desc id="portfolio-profile-desc">',
            f"Showing {len(shown_candidates)} of {len(candidates)} candidates and ",
            f"{len(shown_motifs)} of {total_motifs} motifs. Values are normalized motif ",
            "scores under this result's declared semantics, not probabilities. ",
            f"{len(limiting_shown)} of {len(limiting_ids)} limiting motif columns are shown; ",
            "every row directly labels its hard minimum and limiting motifs.</desc>",
            f'<rect width="{width}" height="{height}" fill="{_PAPER}"/>',
            f'<text x="20" y="28" fill="{_INK}" font-family="system-ui,sans-serif" ',
            'font-size="18" font-weight="650">Portfolio balance</text>',
            f'<text x="20" y="52" fill="{_MUTED}" font-family="system-ui,sans-serif" ',
            f'font-size="13">{len(shown_candidates)} of {len(candidates)} candidates · ',
            f"{len(shown_motifs)} of {total_motifs} motifs · limiting columns ",
            f"{len(limiting_shown)}/{len(limiting_ids)}</text>",
        ]
    )
    for column, motif_id in enumerate(shown_motifs):
        x_label = left + column * cell_width + cell_width / 2
        parts.append(
            f'<text x="{x_label:.3f}" y="82" text-anchor="middle" fill="{_MUTED}" '
            'font-family="ui-monospace,monospace" font-size="10">'
            f"{_motif_id(motif_id)}</text>"
        )
    hard_min_x = left + len(shown_motifs) * cell_width + 14
    parts.append(
        f'<text x="{hard_min_x}" y="82" fill="{_MUTED}" '
        'font-family="system-ui,sans-serif" font-size="10">hard minimum · limiting</text>'
    )
    for row, candidate in enumerate(shown_candidates):
        y = top + row * row_height
        score_by_motif = {
            match.motif_id: match.normalized_score
            for match in candidate.matches
            if match.motif_id in shown_motifs
        }
        row_limiting = tuple(
            sorted(
                match.motif_id
                for match in candidate.matches
                if math.isclose(
                    match.normalized_score,
                    candidate.balance_score,
                    abs_tol=1.0e-12,
                )
            )
        )
        parts.append(
            f'<text x="20" y="{y + 19}" fill="{_INK}" '
            'font-family="system-ui,sans-serif" font-size="11">'
            f"rank {candidate.rank} · {_short_candidate_id(candidate.candidate_id)}</text>"
        )
        for column, motif_id in enumerate(shown_motifs):
            x_cell = left + column * cell_width
            value = score_by_motif.get(motif_id)
            parts.append(
                f'<rect x="{x_cell + 3}" y="{y + 3}" width="{cell_width - 6}" height="24" '
                f'fill="{_SOFT}" stroke="{_LINE}" data-motif-id="{_motif_id(motif_id)}"/>'
            )
            if value is None:
                label = "missing"
                bar_width = 0.0
            else:
                label = f"{value:.5g}"
                bar_width = 0.0 if max_score == 0.0 else (cell_width - 6) * value / max_score
            if bar_width > 0.0:
                is_limiting = math.isclose(
                    value or 0.0,
                    candidate.balance_score,
                    abs_tol=1.0e-12,
                )
                parts.append(
                    f'<rect x="{x_cell + 3}" y="{y + 3}" width="{bar_width:.3f}" height="24" '
                    f'fill="{_ACCENT if is_limiting else _MUTED}" opacity="0.32"/>'
                )
            parts.append(
                f'<text x="{x_cell + cell_width / 2:.3f}" y="{y + 19}" '
                f'text-anchor="middle" fill="{_INK}" font-family="system-ui,sans-serif" '
                f'font-size="10">{label}</text>'
            )
        parts.append(
            f'<text x="{hard_min_x}" y="{y + 19}" fill="{_INK}" '
            'font-family="system-ui,sans-serif" font-size="10">'
            f"{candidate.balance_score:.5g} · {_limiting_label(row_limiting)}</text>"
        )
    if len(shown_candidates) < len(candidates) or len(shown_motifs) < total_motifs:
        parts.append(
            f'<text x="20" y="{height - 18}" fill="{_MUTED}" '
            'font-family="system-ui,sans-serif" font-size="11">'
            f"Bounded view: {len(shown_candidates)}/{len(candidates)} candidates and "
            f"{len(shown_motifs)}/{total_motifs} motifs; use the exact tables below."
            "</text>"
        )
    parts[3] = parts[3].replace(
        ">",
        f' data-displayed-candidates="{len(shown_candidates)}" '
        f'data-total-candidates="{len(candidates)}" '
        f'data-displayed-limiting="{len(limiting_shown)}" '
        f'data-total-limiting="{len(limiting_ids)}">',
    )
    parts.append("</svg>")
    return _finish_svg(parts)

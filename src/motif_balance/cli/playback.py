"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/cli/playback.py

Replay an explicit search observation and export a view without overwriting files.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import os
import stat
from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import ValidationError

from motif_balance.errors import ArtifactError, MotifBalanceError
from motif_balance.playback import inspect_playback, render_playback_html, render_playback_svg
from motif_balance.playback.media import render_playback_media

from .errors import _emit_error
from .output import _require_new_inspection_output, _write_new_file


def _read_observation(path: Path) -> bytes:
    # Bound the bytes from one open regular file, without following a symbolic link.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ArtifactError("playback input must be a regular observation JSON file")
        payload = handle.read(64 * 1024 * 1024 + 1)
    if len(payload) > 64 * 1024 * 1024:
        raise ArtifactError("playback observation exceeds the 64 MiB input limit")
    return payload


def animate_command(
    observation: Annotated[Path, typer.Argument(help="Recorded SearchObservation JSON file.")],
    out: Annotated[Path, typer.Option("--out", help="New output file.")],
    format_name: Annotated[
        Literal["html", "svg", "png", "gif", "mp4"], typer.Option("--format")
    ] = "html",
    chain: Annotated[
        int | None,
        typer.Option(
            "--chain",
            min=0,
            max=7,
            help="Optional zero-based chain identity; default shows the best sequence so far.",
        ),
    ] = None,
    fps: Annotated[int, typer.Option("--fps", min=1, max=30)] = 4,
    frame: Annotated[
        int, typer.Option("--frame", help="Zero-based SVG/PNG frame; -1 is final.")
    ] = -1,
    debug: Annotated[bool, typer.Option("--debug")] = False,
) -> None:
    """Replay recorded search states beside a sampled best-score trace."""
    try:
        _require_new_inspection_output(out, field="out")
        if out.suffix.lower() != "." + format_name:
            raise ArtifactError("output suffix must match --format")
        if format_name not in ("svg", "png") and frame != -1:
            raise ArtifactError("--frame is supported only for SVG or PNG")
        value = inspect_playback(_read_observation(observation), chain_id=chain)
        if format_name == "html":
            payload = render_playback_html(value, fps=fps)
        elif format_name == "svg":
            payload = render_playback_svg(value, frame=frame)
        else:
            payload = render_playback_media(value, format_name=format_name, fps=fps, frame=frame)
        _write_new_file(out, payload, label="playback output")
        typer.echo(f"Wrote {len(value.frames)} recorded observations to {out.name}")
    except (MotifBalanceError, ValidationError, ValueError, OSError) as exc:
        _emit_error(exc, domain="playback", debug=debug)

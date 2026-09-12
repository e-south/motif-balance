from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml
from pydantic import ValidationError

from motif_balance.errors import InvalidMotif, MotifBalanceError
from motif_balance.execution import execute_design_workspace
from motif_balance.formats import convert_jaspar

from .errors import _emit_error
from .output import _write_new_file


def _background(value: str) -> tuple[float, float, float, float]:
    try:
        parsed = tuple(float(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise InvalidMotif(
            "Background must contain four comma-separated numbers in A,C,G,T order.",
            field="background",
            hint="For a uniform background use 0.25,0.25,0.25,0.25.",
        ) from exc
    if len(parsed) != 4:
        raise InvalidMotif(
            "Background must contain exactly four values in A,C,G,T order.",
            field="background",
            hint="For a uniform background use 0.25,0.25,0.25,0.25.",
        )
    return parsed[0], parsed[1], parsed[2], parsed[3]


def prepare_motif_command(
    source: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    motif_id: Annotated[str, typer.Option("--motif-id")],
    background: Annotated[str, typer.Option("--background")],
    out: Annotated[Path, typer.Option("--out")],
    debug: Annotated[bool, typer.Option("--debug")] = False,
) -> None:
    """Prepare one canonical motif model from a supported source file."""

    try:
        motif = convert_jaspar(
            source,
            motif_id=motif_id,
            background=_background(background),
        )
        payload = yaml.safe_dump(
            motif.model_dump(mode="json", exclude_none=True),
            sort_keys=False,
        ).encode()
        _write_new_file(out, payload, label="motif model")
        typer.echo(f"complete {motif.model_digest} {out}")
    except (OSError, MotifBalanceError, ValidationError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="motif")


def execute_command(
    specification: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    producer_revision: Annotated[str, typer.Option("--producer-revision")],
    release_artifact: Annotated[
        Path,
        typer.Option("--release-artifact", exists=True, dir_okay=False, readable=True),
    ],
    out: Annotated[Path, typer.Option("--out")],
    debug: Annotated[bool, typer.Option("--debug")] = False,
) -> None:
    """Publish one release-attested execution workspace."""

    try:
        workspace = execute_design_workspace(
            specification,
            out,
            producer_revision=producer_revision,
            release_artifact=release_artifact,
        )
        typer.echo(f"complete {workspace.workspace_id} {out}")
    except (OSError, MotifBalanceError, ValidationError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="design")

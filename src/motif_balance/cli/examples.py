"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/cli/examples.py

Prepare a complete biological example with an editable design request.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from pathlib import Path
from typing import Annotated

import typer

from motif_balance.errors import MotifBalanceError
from motif_balance.examples import prepare_example
from motif_balance.examples.preparation import ExampleName

from .errors import _emit_error


def example_command(
    name: Annotated[ExampleName, typer.Argument(help="argr-cra or twelve-motifs")],
    out: Annotated[Path, typer.Option(help="New directory for the request and motif inputs.")],
    cache: Annotated[Path | None, typer.Option(help="Publisher archive cache directory.")] = None,
    debug: Annotated[bool, typer.Option(help="Show the underlying exception.")] = False,
) -> None:
    """Download and check published motifs, then write an editable example."""
    try:
        prepare_example(name, out, cache=cache)
        typer.echo(f"Prepared {name} in {out}")
        typer.echo("Edit design.yaml to change the motifs, DNA length, or search allowance.")
    except (OSError, MotifBalanceError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="design")

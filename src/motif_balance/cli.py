from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import ValidationError

from motif_balance.api import compile_spec, design, load_spec
from motif_balance.errors import MotifBalanceError

app = typer.Typer(add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False)


@app.callback()
def root() -> None:
    """Design fixed-length DNA sequences against explicit motif models."""


@app.command("design")
def design_command(
    specification: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    out: Annotated[Path | None, typer.Option("--out", help="Immutable output directory.")] = None,
    check: Annotated[
        bool, typer.Option("--check", help="Compile and validate without search.")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Show the underlying exception.")] = False,
) -> None:
    """Compile or execute one immutable scientific design specification."""
    try:
        spec = load_spec(specification)
        problem_id = compile_spec(spec)
        if check:
            typer.echo(f"valid {problem_id}")
            return
        if out is None:
            raise typer.BadParameter("--out is required unless --check is used")
        portfolio = design(spec)
        portfolio.write(out)
        typer.echo(f"complete {portfolio.manifest.bundle_id} {out}")
    except (MotifBalanceError, ValidationError, ValueError) as exc:
        if debug:
            raise
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from None


def main() -> Any:
    return app()


if __name__ == "__main__":  # pragma: no cover
    main()

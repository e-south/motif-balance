"""Thin command registration; scientific behavior remains in the owning APIs."""

from typing import Any

import typer

from .assessment import assess_command
from .design import design_command
from .inspection import inspect_command
from .preparation import execute_command, prepare_motif_command
from .scoring import score_command

app = typer.Typer(add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False)
motif_app = typer.Typer(add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False)
orchestration_app = typer.Typer(
    add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False
)
app.add_typer(motif_app, name="motif", hidden=True)
app.add_typer(orchestration_app, name="orchestration", hidden=True)


@app.callback()
def root() -> None:
    """Assess motif pairs; design, score, and inspect fixed-length DNA sequences."""


app.command("assess")(assess_command)
app.command("design")(design_command)
app.command("score")(score_command)
app.command("inspect")(inspect_command)
motif_app.command("prepare")(prepare_motif_command)
orchestration_app.command("execute")(execute_command)


def main() -> Any:
    return app()

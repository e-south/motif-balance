"""Thin command registration; scientific behavior remains in the owning APIs.

Maintainer(s): Eric J. South, Dunlop Lab
"""

from typing import Any

import typer

from .assessment import assess_command
from .collection import collect_command
from .design import design_command
from .inspection import inspect_command
from .playback import animate_command
from .preparation import execute_command, prepare_motif_command
from .scoring import score_command

app = typer.Typer(add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False)
motif_app = typer.Typer(add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False)
orchestration_app = typer.Typer(
    add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False
)
app.add_typer(motif_app, name="motif", help="Prepare motif profiles for sequence design.")
app.add_typer(orchestration_app, name="orchestration", hidden=True)


@app.callback()
def root() -> None:
    """Design DNA from motif preferences, compare alternatives, and inspect search results."""


app.command("assess")(assess_command)
app.command("design")(design_command)
app.command("collect")(collect_command)
app.command("score")(score_command)
app.command("inspect")(inspect_command)
app.command("animate")(animate_command)
motif_app.command("prepare")(prepare_motif_command)
orchestration_app.command("execute")(execute_command)


def main() -> Any:
    return app()

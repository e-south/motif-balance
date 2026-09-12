from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import ValidationError

from motif_balance.api import score
from motif_balance.errors import ArtifactError, MotifBalanceError
from motif_balance.formats.design import load_design_spec

from .errors import _emit_error
from .output import _write_new_file


def score_command(
    specification: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    sequence: Annotated[str, typer.Argument(help="Exact A/C/G/T sequence to score.")],
    format_name: Annotated[
        Literal["text", "json"],
        typer.Option("--format", help="Terminal or machine-readable result."),
    ] = "text",
    out: Annotated[Path | None, typer.Option("--out", help="New output file.")] = None,
    debug: Annotated[bool, typer.Option("--debug", help="Show the underlying exception.")] = False,
) -> None:
    """Score one sequence under an explicit DesignSpec."""

    try:
        if out is not None and os.path.lexists(out):
            raise ArtifactError(
                f"Refusing to replace existing score output '{out.name}'.",
                field="out",
                hint="Choose a new output path.",
            )
        spec = load_design_spec(specification)
        evaluation = score(sequence, spec)
        if format_name == "json":
            payload = (evaluation.model_dump_json(indent=2) + "\n").encode()
        else:
            if spec.schema_version == "design-spec/v3":
                target_matches = "\n".join(
                    f"{match.motif_id}: direction={match.spec_direction} "
                    f"attainment={match.normalized_score:.17g} "
                    f"satisfaction={match.spec_satisfaction:.17g} "
                    f"raw={match.raw_score:.17g} strand={match.strand} "
                    f"coordinates=[{match.start}, {match.end})"
                    for match in evaluation.matches
                    if match.spec_satisfaction is not None
                )
            else:
                target_matches = "\n".join(
                    f"{match.motif_id}: normalized={match.normalized_score:.17g} "
                    f"raw={match.raw_score:.17g} strand={match.strand} "
                    f"coordinates=[{match.start}, {match.end})"
                    for match in evaluation.matches
                )
            ceilings = {item.motif.motif_id: item.score_ceiling for item in spec.avoiders}
            avoidance_matches = "\n".join(
                f"{match.motif_id}: avoidance normalized={match.normalized_score:.17g} "
                f"ceiling={ceilings[match.motif_id]:.17g} raw={match.raw_score:.17g} "
                f"strand={match.strand} coordinates=[{match.start}, {match.end})"
                for match in evaluation.avoidance_matches
            )
            constraint = (
                f"constraint_status={evaluation.constraint_status}\n"
                f"max_avoidance_excess={evaluation.max_avoidance_excess:.17g}\n"
                f"total_avoidance_excess={evaluation.total_avoidance_excess:.17g}\n"
                if spec.avoiders
                else ""
            )
            payload = (
                f"balance_score={evaluation.balance_score:.17g}\n"
                f"sequence={evaluation.sequence}\n{constraint}{target_matches}\n"
                + (f"{avoidance_matches}\n" if avoidance_matches else "")
            ).encode()
        if out is None:
            typer.echo(payload.decode(), nl=False)
        else:
            _write_new_file(out, payload, label="score output")
    except (OSError, MotifBalanceError, ValidationError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="design")

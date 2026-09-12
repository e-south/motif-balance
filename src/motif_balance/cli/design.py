from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from motif_balance.api import design
from motif_balance.compile import compile_design, planned_search_kind
from motif_balance.errors import ArtifactError, InvalidDesign, MotifBalanceError
from motif_balance.formats.design import load_design_spec

from .errors import _emit_error


def design_command(
    specification: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    out: Annotated[Path | None, typer.Option("--out", help="Immutable output directory.")] = None,
    check: Annotated[
        bool, typer.Option("--check", help="Compile and validate without search.")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Show the underlying exception.")] = False,
) -> None:
    """Validate or execute one immutable DesignSpec."""

    try:
        spec = load_design_spec(specification)
        problem_id = compile_design(spec).problem_id
        if check:
            typer.echo(f"valid {problem_id}")
            if spec.schema_version == "design-spec/v3":
                specification_summary = " ".join(
                    (
                        f"specifications={len(spec.specifications)}",
                        "directions="
                        + ",".join(
                            f"{item.motif.motif_id}:{item.direction}"
                            for item in spec.specifications
                        ),
                    )
                )
            else:
                specification_summary = f"motifs={len(spec.motifs)} avoiders={len(spec.avoiders)}"
            typer.echo(
                f"{specification_summary} length={spec.length} count={spec.count} "
                f"strands={spec.strands} evaluations={spec.evaluations} "
                f"min_distance={spec.min_distance} search={planned_search_kind(spec)}"
            )
            return
        if out is None:
            raise InvalidDesign(
                "--out is required unless --check is used.",
                field="out",
                hint="Supply a new output directory with --out.",
            )
        if os.path.lexists(out):
            raise ArtifactError(
                f"Output directory already exists or is unsafe: '{out.name}'.",
                field="out",
                hint="Choose a new output directory.",
            )
        portfolio = design(spec)
        portfolio.write(out)
        best = portfolio.best
        best_observed = portfolio.best_observed
        if best_observed is None:  # pragma: no cover - required by current writer
            raise ArtifactError("current result is missing the best observed evaluation")
        if spec.schema_version == "design-spec/v3":
            motif_summary = ", ".join(
                f"{item.motif.motif_id}:{item.direction}" for item in spec.specifications
            )
        else:
            motif_summary = ", ".join(motif.motif_id for motif in spec.motifs)
        typer.echo(
            f"Returned {len(portfolio.candidates)} of {spec.count} candidates for "
            f"{motif_summary}, each {spec.length} nt."
        )
        typer.echo(f"Best observed balance score: {best_observed.balance_score:.6g}.")
        if best_observed.sequence not in {candidate.sequence for candidate in portfolio.candidates}:
            typer.echo(
                "The best observed candidate was not selected under the portfolio constraint."
            )
            typer.echo(f"Best selected balance score: {best.balance_score:.6g}.")
        if spec.min_distance is not None and spec.min_distance > 0.0:
            typer.echo(f"Requested minimum distance: {spec.min_distance:.6g}.")
        if spec.avoiders:
            ceilings = ", ".join(
                f"{item.motif.motif_id}<={item.score_ceiling:.6g}" for item in spec.avoiders
            )
            typer.echo(f"Hard avoidance satisfied: {ceilings}.")
        if portfolio.manifest.completion_status == "exhaustive":
            typer.echo(
                "Search completed after exhausting all "
                f"{portfolio.manifest.evaluation_count} sequences."
            )
        else:
            typer.echo(
                "Search stopped after exhausting "
                f"{portfolio.manifest.evaluation_count} evaluator calls."
            )
        typer.echo(f"Result written to {out}.")
        typer.echo(f"Bundle: {portfolio.manifest.bundle_id}")
    except (OSError, MotifBalanceError, ValidationError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="design")

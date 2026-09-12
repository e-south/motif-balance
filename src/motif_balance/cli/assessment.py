"""Read two models and present the generic pre-search assessment."""

import os
from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import ValidationError

from motif_balance.assessment import assess_pair
from motif_balance.errors import ArtifactError, InvalidMotif, MotifBalanceError
from motif_balance.formats import read_motif
from motif_balance.inspection.assessment import inspect_pair_assessment
from motif_balance.inspection.limits import MAX_SVG_ASSESSMENT_LENGTH
from motif_balance.inspection.render import render_pair_assessment_svg

from .errors import _emit_error
from .output import _write_new_file


def assess_command(
    left: Annotated[
        Path,
        typer.Argument(
            exists=True, dir_okay=False, readable=True, help="Left canonical YAML/JSON motif model."
        ),
    ],
    right: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Right canonical YAML/JSON motif model.",
        ),
    ],
    length: Annotated[
        int, typer.Option("--length", min=1, help="Available DNA length in nucleotides.")
    ],
    strands: Annotated[
        Literal["forward", "both"], typer.Option("--strands", help="Allowed strand policy.")
    ] = "both",
    format_name: Annotated[
        Literal["text", "json", "svg"],
        typer.Option("--format", help="Summary, full JSON profile, or pre-search logo diagram."),
    ] = "text",
    out: Annotated[
        Path | None, typer.Option("--out", help="New output file; omit to print.")
    ] = None,
    debug: Annotated[bool, typer.Option("--debug", help="Show the underlying exception.")] = False,
) -> None:
    """Assess shared-base conflicts for two desired motifs without sequence search."""
    try:
        if out is not None and os.path.lexists(out):
            raise ArtifactError(
                f"Refusing to replace existing assessment output '{out.name}'.",
                field="out",
                hint="Choose a new output path.",
            )
        if format_name == "svg" and length > MAX_SVG_ASSESSMENT_LENGTH:
            raise ArtifactError(
                f"Assessment SVG supports at most {MAX_SVG_ASSESSMENT_LENGTH} nt.",
                field="length",
                hint="Use --format json for longer requests.",
            )
        for path in (left, right):
            if path.suffix.lower() not in {".json", ".yaml", ".yml"}:
                raise InvalidMotif(
                    "Assessment requires two canonical YAML/JSON motif models.",
                    field="motif",
                    hint="Prepare one explicit motif-model/v2 file per input; "
                    "do not supply a multi-model database.",
                )
        if format_name == "svg":
            view = inspect_pair_assessment(
                read_motif(left), read_motif(right), length=length, strands=strands
            )
            payload = render_pair_assessment_svg(view)
        else:
            result = assess_pair(
                read_motif(left), read_motif(right), length=length, strands=strands
            )
        if format_name == "json":
            payload = (result.model_dump_json(indent=2) + "\n").encode()
        elif format_name == "text":
            best = result.best_arrangement
            payload = (
                f"Models: left={result.motifs[0].motif_id}; right={result.motifs[1].motif_id}\n"
                f"Length: {result.length} nt; strands: {result.strands}\n"
                f"Structural score: {result.structural_score:.6g}\n"
                f"Best relative arrangement: left start={best.left_start} "
                f"strand={best.left_strand}; right start={best.right_start} "
                f"strand={best.right_strand}; overlap={best.overlap_bases} nt\n"
                f"Relative arrangements: {result.arrangement_count}\n"
                "Sequence evaluations: 0\n"
                "This is a local-conflict assessment, not a predicted sequence score "
                "or binding probability.\n"
                "Use --format json for all arrangements or --format svg for the motif diagram.\n"
                "Design generates candidate sequences.\n"
            ).encode()
        if out is None:
            typer.echo(payload.decode(), nl=False)
        else:
            _write_new_file(out, payload, label="assessment output")
    except (OSError, MotifBalanceError, ValidationError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="motif")

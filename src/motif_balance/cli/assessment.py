"""Read supplied motifs and report pair or bounded joint base conflicts.

Maintainer(s): Eric J. South, Dunlop Lab
"""

import os
from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import ValidationError

from motif_balance.assessment import assess_motifs, assess_pair
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
    additional: Annotated[
        list[Path] | None,
        typer.Option(
            "--additional",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Additional desired model; repeat once for four-model joint assessment.",
        ),
    ] = None,
    format_name: Annotated[
        Literal["text", "json", "svg"],
        typer.Option("--format", help="Summary, full JSON profile, or pre-search logo diagram."),
    ] = "text",
    out: Annotated[
        Path | None, typer.Option("--out", help="New output file; omit to print.")
    ] = None,
    debug: Annotated[bool, typer.Option("--debug", help="Show the underlying exception.")] = False,
) -> None:
    """Assess base conflicts without sequence search; optional exact joint assessment."""
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
        if additional and (len(additional) > 2 or format_name == "svg"):
            raise InvalidMotif(
                "Joint assessment supports at most four models; SVG supports two models.",
                hint="Use text or JSON for joint assessment of three or four models.",
            )
        paths = (left, right, *(additional or ()))
        for path in paths:
            if path.suffix.lower() not in {".json", ".yaml", ".yml"}:
                raise InvalidMotif(
                    "Assessment requires two canonical YAML/JSON motif models.",
                    field="motif",
                    hint="Prepare one explicit motif-model/v2 file per input; "
                    "do not supply a multi-model database.",
                )
        if additional:
            joint = assess_motifs(
                tuple(read_motif(path) for path in paths), length=length, strands=strands
            )
            payload = (
                (joint.model_dump_json(indent=2) + "\n").encode()
                if format_name == "json"
                else (
                    f"Joint assessment: {len(joint.motifs)} motifs\n"
                    f"Length: {joint.length} nt; strands: {joint.strands}\n"
                    f"Structural score: {joint.structural_score:.6g}\n"
                    f"Relative arrangements: {joint.arrangement_count}; proof: {joint.proof}\n"
                    + "".join(
                        f"Model {i}: {model.motif_id}; start={start}; strand={strand}\n"
                        for i, (model, start, strand) in enumerate(
                            zip(
                                joint.motifs,
                                joint.best_arrangement.starts,
                                joint.best_arrangement.strands,
                                strict=True,
                            ),
                            1,
                        )
                    )
                    + "Sequence evaluations: 0\n"
                    "This is a local-conflict assessment, not a predicted sequence score "
                    "or binding probability.\n"
                ).encode()
            )
            if out is None:
                typer.echo(payload.decode(), nl=False)
            else:
                _write_new_file(out, payload, label="assessment output")
            return
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

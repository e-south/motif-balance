"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/cli/variants.py

CLI adapter for post-design, score-constrained nucleotide libraries.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Literal

import typer

from motif_balance.api import score
from motif_balance.artifacts import read_verified_portfolio
from motif_balance.errors import ArtifactError, InvalidDesign, MotifBalanceError
from motif_balance.formats.collection import read_collection
from motif_balance.formats.design import load_design_spec
from motif_balance.formats.variants import variants_fasta, variants_tsv
from motif_balance.inspection.render.variants import render_variant_map
from motif_balance.variants import diversify

from .errors import _emit_error
from .output import _validate_inspection_output_path, _write_new_directory, _write_new_file


def diversify_command(
    source: Annotated[
        Path,
        typer.Argument(
            exists=True, readable=True, help="Saved design, collection JSON, or design request."
        ),
    ],
    sequence: Annotated[
        str | None, typer.Argument(help="Parent DNA, required only with a design request.")
    ] = None,
    candidate: Annotated[
        int, typer.Option(min=1, help="One-based rank in a saved design or collection.")
    ] = 1,
    max_score_loss: Annotated[
        float, typer.Option(min=0.0, max=1.0, help="Permitted per-model component loss.")
    ] = 0.02,
    max_variants: Annotated[
        int, typer.Option(min=1, max=256, help="Encoded sequence cap, including parent.")
    ] = 256,
    editable_mask: Annotated[
        str | None, typer.Option(help="One 0/1 per position; default covers desired sites.")
    ] = None,
    format_name: Annotated[
        Literal["json", "text", "fasta", "tsv", "svg", "all"] | None, typer.Option("--format")
    ] = None,
    out: Annotated[
        Path | None, typer.Option(help="New output file, or directory for all four exports.")
    ] = None,
    debug: Annotated[bool, typer.Option(help="Show the underlying exception.")] = False,
) -> None:
    """Vary a selected sequence while preserving sites and limiting motif-score loss."""
    try:
        if out is not None and os.path.lexists(out):
            raise ArtifactError("Refusing to replace existing variant output.", field="out")
        if source.is_dir():
            if sequence is not None:
                raise InvalidDesign(
                    "a saved design already supplies the parent; omit the DNA argument"
                )
            if out is not None:
                _validate_inspection_output_path(out, subject=source, field="out")
            saved = read_verified_portfolio(source)
            if candidate > len(saved.candidates):
                raise InvalidDesign(
                    f"candidate rank must be from 1 to {len(saved.candidates)} in this design.",
                    field="candidate",
                )
            parent, spec = saved.candidates[candidate - 1].as_evaluation(), saved.spec
            sequence = parent.sequence
        elif sequence is None:
            report = read_collection(source)
            if candidate > report.collection.delivered_count:
                raise InvalidDesign(
                    "candidate rank is outside the saved collection.",
                    field="candidate",
                    hint=f"Choose a rank from 1 to {report.collection.delivered_count}.",
                )
            parent = report.collection.members[candidate - 1].evaluation
            spec = report.ranking.spec
            if score(parent.sequence, spec) != parent:
                raise ArtifactError(
                    "The selected collection member does not match its rescored DNA.",
                    hint="Regenerate the collection from its saved design.",
                )
            sequence = parent.sequence
        else:
            if candidate != 1:
                raise InvalidDesign(
                    "candidate selection applies only to saved designs or collections",
                    field="candidate",
                )
            spec = load_design_spec(source)
        inferred: dict[str, Literal["json", "text", "fasta", "tsv", "svg", "all"]] = {
            ".json": "json",
            ".fasta": "fasta",
            ".fa": "fasta",
            ".tsv": "tsv",
            ".svg": "svg",
            ".txt": "text",
            "": "all",
        }
        if format_name is None and out is not None and out.suffix.lower() not in inferred:
            raise InvalidDesign(
                "Unrecognized output suffix.",
                field="out",
                hint="Use a directory without a suffix, a supported file suffix, or --format.",
            )
        format_name = format_name or (inferred[out.suffix.lower()] if out is not None else "json")
        if format_name == "all" and out is None:
            raise InvalidDesign("--out is required for a variant directory", field="out")
        if editable_mask is not None and set(editable_mask) - {"0", "1"}:
            raise InvalidDesign("editable mask must contain only 0 and 1", field="editable_mask")
        mask = None if editable_mask is None else tuple(c == "1" for c in editable_mask)
        library = diversify(
            sequence,
            spec,
            max_score_loss=max_score_loss,
            max_variants=max_variants,
            editable_mask=mask,
        )
        if format_name == "all":
            assert out is not None
            _write_new_directory(
                out,
                {
                    "library.json": (library.model_dump_json(indent=2) + "\n").encode(),
                    "variants.fasta": variants_fasta(library).encode(),
                    "scores.tsv": variants_tsv(library).encode(),
                    "substitutions.svg": render_variant_map(library).encode(),
                },
            )
            typer.echo(f"{library.encoded_sequence_count} checked sequences written to {out}.")
            typer.echo(
                f"Template {library.template}; lowest balance {library.minimum_balance:.3f}."
            )
            if library.status == "parent_only":
                typer.echo("No additional variants found under these settings.")
            return
        if format_name == "json":
            payload = library.model_dump_json(indent=2) + "\n"
        elif format_name == "fasta":
            payload = variants_fasta(library)
        elif format_name == "tsv":
            payload = variants_tsv(library)
        elif format_name == "svg":
            payload = render_variant_map(library)
        else:
            payload = (
                f"Encoded sequence count: {library.encoded_sequence_count}\n"
                f"Template: {library.template}\nMinimum balance: {library.minimum_balance:.6g}\n"
                f"Largest component loss: {library.maximum_component_loss:.6g}\n"
                f"Stopping reason: {library.stop_reason.replace('_', ' ')}\n"
                f"Diversification evaluations: {library.evaluations_used}\n"
            )
            if library.status == "parent_only":
                payload += "No additional variants found under these settings.\n"
        if out is None:
            typer.echo(payload, nl=False)
        else:
            _write_new_file(out, payload.encode(), label="variant output")
    except (OSError, MotifBalanceError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="design")

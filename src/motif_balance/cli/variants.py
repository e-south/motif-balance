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

from motif_balance.errors import ArtifactError, MotifBalanceError
from motif_balance.formats.design import load_design_spec
from motif_balance.formats.variants import variants_fasta, variants_tsv
from motif_balance.inspection.render.variants import render_variant_map
from motif_balance.variants import diversify

from .errors import _emit_error
from .output import _write_new_file


def diversify_command(
    specification: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    sequence: Annotated[str, typer.Argument(help="Parent A/C/G/T sequence.")],
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
        Literal["json", "text", "fasta", "tsv", "svg"], typer.Option("--format")
    ] = "json",
    out: Annotated[Path | None, typer.Option(help="New output file.")] = None,
    debug: Annotated[bool, typer.Option(help="Show the underlying exception.")] = False,
) -> None:
    """Vary a selected sequence while preserving sites and limiting motif-score loss."""
    try:
        if out is not None and os.path.lexists(out):
            raise ArtifactError("Refusing to replace existing variant output.", field="out")
        if editable_mask is not None and set(editable_mask) - {"0", "1"}:
            raise ValueError("editable mask must contain only 0 and 1")
        mask = None if editable_mask is None else tuple(c == "1" for c in editable_mask)
        library = diversify(
            sequence,
            load_design_spec(specification),
            max_score_loss=max_score_loss,
            max_variants=max_variants,
            editable_mask=mask,
        )
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

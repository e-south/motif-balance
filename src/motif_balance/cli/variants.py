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
from motif_balance.model import DesignSpec
from motif_balance.variants import diversify, diversify_collection

from .errors import _emit_error
from .output import _validate_inspection_output_path, _write_new_directory, _write_new_file

_VariantFormat = Literal["json", "text", "fasta", "tsv", "svg", "all"]


def _resolve_format(format_name: _VariantFormat | None, out: Path | None) -> _VariantFormat:
    """Resolve export options before loading and verifying a saved parent."""
    inferred: dict[str, _VariantFormat] = {
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
    resolved = format_name or (inferred[out.suffix.lower()] if out is not None else "json")
    if resolved == "all" and out is None:
        raise InvalidDesign("--out is required for a variant directory", field="out")
    return resolved


def _read_parent(
    source: Path, sequence: str | None, candidate: int, out: Path | None
) -> tuple[str, DesignSpec]:
    """Resolve and rescore one saved parent for either post-design operation."""
    if source.is_dir():
        if sequence is not None:
            raise InvalidDesign("a saved design already supplies the parent; omit the DNA argument")
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
    assert sequence is not None
    return sequence, spec


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
        int | None, typer.Option(min=1, help="One-based rank in a saved design or collection.")
    ] = None,
    all_members: Annotated[
        bool, typer.Option("--all", help="Expand every member of a saved collection.")
    ] = False,
    max_score_loss: Annotated[
        float | None,
        typer.Option(
            min=0.0,
            max=1.0,
            help="Permitted per-model component loss; default 0.02 without a floor.",
        ),
    ] = None,
    min_balance: Annotated[
        float | None,
        typer.Option(
            min=0.0, max=1.0, help="Absolute balance floor, without a parental-loss limit."
        ),
    ] = None,
    max_variants: Annotated[
        int, typer.Option(min=1, max=1024, help="Encoded sequence cap, including parent.")
    ] = 256,
    editable_mask: Annotated[
        str | None, typer.Option(help="One 0/1 per position; default covers desired sites.")
    ] = None,
    max_total_score_operations: Annotated[
        int | None,
        typer.Option(
            min=1,
            max=16_000_000_000,
            help="Total work allowance for --all; default one billion. Per-library limits remain.",
        ),
    ] = None,
    format_name: Annotated[_VariantFormat | None, typer.Option("--format")] = None,
    out: Annotated[
        Path | None, typer.Option(help="New output file, or directory for all four exports.")
    ] = None,
    debug: Annotated[bool, typer.Option(help="Show the underlying exception.")] = False,
) -> None:
    """Construct a checked degenerate template at selected motif sites."""
    try:
        if max_total_score_operations is not None and not all_members:
            raise InvalidDesign("--max-total-score-operations requires --all")
        if max_score_loss is not None and min_balance is not None:
            raise InvalidDesign("specify either --min-balance or --max-score-loss")
        if all_members and (candidate is not None or sequence is not None or source.is_dir()):
            raise InvalidDesign(
                "--all requires a collection JSON without --candidate or a DNA argument"
            )
        if all_members and format_name not in (None, "json", "all"):
            raise InvalidDesign("--all supports JSON or a complete output directory")
        candidate = 1 if candidate is None else candidate
        if out is not None and os.path.lexists(out):
            raise ArtifactError("Refusing to replace existing variant output.", field="out")
        format_name = _resolve_format(format_name, out)
        if editable_mask is not None and set(editable_mask) - {"0", "1"}:
            raise InvalidDesign("editable mask must contain only 0 and 1", field="editable_mask")
        mask = None if editable_mask is None else tuple(c == "1" for c in editable_mask)
        if all_members:
            if format_name not in ("all", "json"):
                raise InvalidDesign("--all supports JSON or a complete output directory")
            expanded = diversify_collection(
                read_collection(source),
                min_balance=min_balance,
                max_score_loss=max_score_loss,
                max_variants=max_variants,
                editable_mask=mask,
                max_total_score_operations=(
                    1_000_000_000
                    if max_total_score_operations is None
                    else max_total_score_operations
                ),
            )
            payload = expanded.model_dump_json(indent=2) + "\n"
            if format_name == "all":
                assert out is not None
                files = {"collection.json": payload.encode()}
                for rank, member_library in enumerate(expanded.libraries, 1):
                    files[f"arrangement-{rank}.fasta"] = variants_fasta(member_library).encode()
                    files[f"arrangement-{rank}-scores.tsv"] = variants_tsv(member_library).encode()
                    files[f"arrangement-{rank}-substitutions.svg"] = render_variant_map(
                        member_library
                    ).encode()
                _write_new_directory(out, files)
                typer.echo(
                    f"{len(expanded.libraries)} arrangements; "
                    f"{len(expanded.unique_sequences)} distinct checked sequences written to {out}."
                )
            elif out is None:
                typer.echo(payload, nl=False)
            else:
                _write_new_file(out, payload.encode(), label="collection variants")
            return
        sequence, spec = _read_parent(source, sequence, candidate, out)
        library = diversify(
            sequence,
            spec,
            max_score_loss=max_score_loss,
            min_balance=min_balance,
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

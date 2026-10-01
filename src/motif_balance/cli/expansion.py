"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/cli/expansion.py

Expand selected layouts into explicit score-qualified sequence lists.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

import os
from pathlib import Path
from typing import Annotated, Literal

import typer

from motif_balance.errors import ArtifactError, InvalidDesign, MotifBalanceError
from motif_balance.formats.collection import read_collection
from motif_balance.formats.variants import variants_fasta, variants_tsv
from motif_balance.model.sequence_expansion import SequenceExpansion
from motif_balance.variants import expand, expand_collection

from .errors import _emit_error
from .output import _write_new_directory, _write_new_file
from .variants import _read_parent, _resolve_format


def _describe(result: SequenceExpansion) -> str:
    reason = {
        "variant_limit": "sequence allowance reached",
        "evaluation_limit": "evaluation allowance reached",
        "frontier_exhausted": "all neighbours of retained sequences tested",
    }[result.stop_reason]
    summary = (
        f"{len(result.variants)} retained from {result.evaluations_used} tested; "
        f"lowest balance {result.minimum_balance:.3f}; {reason}."
    )
    if len(result.variants) == 1:
        summary += " No additional qualifying sequences found under these settings."
    return summary


def expand_command(
    source: Annotated[
        Path,
        typer.Argument(
            exists=True,
            readable=True,
            help="Saved collection, design directory, or design request.",
        ),
    ],
    min_balance: Annotated[
        float,
        typer.Option(min=0, max=1, help="Minimum balance required for every returned sequence."),
    ],
    sequence: Annotated[
        str | None, typer.Argument(help="Parent DNA, only with a design request.")
    ] = None,
    all_members: Annotated[
        bool, typer.Option("--all", help="Expand every delivered arrangement in a collection.")
    ] = False,
    candidate: Annotated[
        int | None, typer.Option(min=1, help="One-based rank in a saved design or collection.")
    ] = None,
    max_variants: Annotated[
        int,
        typer.Option(
            min=1, max=1024, help="Returned sequence limit per arrangement, including its parent."
        ),
    ] = 256,
    max_evaluations: Annotated[
        int,
        typer.Option(
            min=1,
            max=100000,
            help="Complete-sequence evaluation limit per arrangement, including its parent.",
        ),
    ] = 4096,
    editable_mask: Annotated[
        str | None, typer.Option(help="One 0/1 per position; default freezes uncovered DNA.")
    ] = None,
    max_total_score_operations: Annotated[
        int | None,
        typer.Option(min=1, max=16_000_000_000, help="Total sequential work allowance for --all."),
    ] = None,
    format_name: Annotated[
        Literal["all", "json", "fasta", "tsv", "text"] | None, typer.Option("--format")
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option(
            help="New output file, or directory for sequences, scores, and the verified handoff."
        ),
    ] = None,
    debug: Annotated[bool, typer.Option(help="Show the underlying exception.")] = False,
) -> None:
    """Keep qualifying nucleotide alternatives at fixed selected motif sites."""
    try:
        if max_total_score_operations is not None and not all_members:
            raise InvalidDesign("--max-total-score-operations requires --all")
        if all_members and (candidate is not None or sequence is not None or source.is_dir()):
            raise InvalidDesign(
                "--all requires a collection JSON without --candidate or a DNA argument"
            )
        if editable_mask is not None and set(editable_mask) - {"0", "1"}:
            raise InvalidDesign("editable mask must contain only 0 and 1")
        mask = None if editable_mask is None else tuple(b == "1" for b in editable_mask)
        resolved = _resolve_format(format_name, out)
        if resolved == "svg" or (all_members and resolved not in ("all", "json")):
            raise InvalidDesign(
                "explicit expansion supports JSON, FASTA, TSV, text, or a directory; "
                "--all supports JSON or a directory"
            )
        if out is not None and os.path.lexists(out):
            raise ArtifactError("Refusing to replace existing expansion output.")
        if all_members:
            collection = expand_collection(
                read_collection(source),
                min_balance=min_balance,
                max_variants=max_variants,
                max_evaluations=max_evaluations,
                editable_mask=mask,
                max_total_score_operations=1_000_000_000
                if max_total_score_operations is None
                else max_total_score_operations,
            )
            payload = collection.model_dump_json(indent=2) + "\n"
            if resolved == "all":
                assert out is not None
                files = {"collection.json": payload.encode()}
                for rank, library in enumerate(collection.libraries, 1):
                    files[f"arrangement-{rank}.fasta"] = variants_fasta(library).encode()
                    files[f"arrangement-{rank}-scores.tsv"] = variants_tsv(library).encode()
                _write_new_directory(out, files)
                for rank, library in enumerate(collection.libraries, 1):
                    typer.echo(f"Arrangement {rank}: {_describe(library)}")
                return
        else:
            dna, spec = _read_parent(source, sequence, candidate or 1, out)
            library = expand(
                dna,
                spec,
                min_balance=min_balance,
                max_variants=max_variants,
                max_evaluations=max_evaluations,
                editable_mask=mask,
            )
            summary = _describe(library) + "\n"
            if resolved == "all":
                assert out is not None
                _write_new_directory(
                    out,
                    {
                        "expansion.json": (library.model_dump_json(indent=2) + "\n").encode(),
                        "sequences.fasta": variants_fasta(library).encode(),
                        "scores.tsv": variants_tsv(library).encode(),
                    },
                )
                typer.echo(summary, nl=False)
                return
            payload = (
                variants_fasta(library)
                if resolved == "fasta"
                else variants_tsv(library)
                if resolved == "tsv"
                else summary
                if resolved == "text"
                else library.model_dump_json(indent=2) + "\n"
            )
        if out is None:
            typer.echo(payload, nl=False)
        else:
            _write_new_file(out, payload.encode(), label="expansion")
    except (OSError, MotifBalanceError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="design")

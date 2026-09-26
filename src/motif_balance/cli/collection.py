"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/cli/collection.py

Collect ranked architectures from the retained pool of a verified bundle.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import os
from pathlib import Path
from typing import Annotated, Literal

import typer

from motif_balance.alternatives import rank_architectures
from motif_balance.artifacts import read_verified_portfolio
from motif_balance.errors import ArtifactError, MotifBalanceError
from motif_balance.formats.collection import collection_json

from .errors import _emit_error
from .output import _validate_inspection_output_path, _write_new_file


def collect_command(
    bundle: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    count: Annotated[int, typer.Option(min=1, help="Return up to this many motif arrangements.")],
    expected_bundle_id: Annotated[
        str | None, typer.Option(help="Also check a separately retained result identity.")
    ] = None,
    grouping: Annotated[
        Literal["interval_topology", "exact_offsets"],
        typer.Option(help="Compare boundary relationships or exact site positions."),
    ] = "interval_topology",
    format_name: Annotated[Literal["text", "json"] | None, typer.Option("--format")] = None,
    out: Annotated[Path | None, typer.Option(help="New output file.")] = None,
    debug: Annotated[bool, typer.Option(help="Show the underlying exception.")] = False,
) -> None:
    """Choose different motif arrangements from a saved design."""
    try:
        if out is not None and os.path.lexists(out):
            raise ArtifactError("Refusing to replace existing collection output.", field="out")
        if out is not None:
            _validate_inspection_output_path(out, subject=bundle, field="out")
        saved = read_verified_portfolio(bundle, expected_bundle_id=expected_bundle_id)
        ranking = rank_architectures(
            tuple(item.sequence for item in saved.manifest.elites), saved.spec, grouping=grouping
        )
        collection = ranking.select_up_to(count)
        format_name = format_name or (
            "json" if out is not None and out.suffix == ".json" else "text"
        )
        if format_name == "json":
            payload = collection_json(
                ranking,
                count=count,
                source_id=saved.manifest.bundle_id,
                anchored=expected_bundle_id is not None,
            )
        else:
            rows = [
                f"Delivered {collection.delivered_count} of up to {count} arrangements: "
                f"{collection.status}.",
                f"Available arrangements: {collection.available_count} in the retained sequences. "
                f"Grouping: {grouping}.",
                "Arrangements selected / weakest balance:",
                *(f"{p.architecture_count} / {p.minimum_balance:.6g}" for p in ranking.prefixes),
                "Selected sequences:",
                *(
                    f"{m.rank}: {m.evaluation.sequence} balance={m.evaluation.balance_score:.6g}"
                    for m in collection.members
                ),
                "Selection uses retained sequences. A shortfall does not prove that "
                "other arrangements are impossible.",
            ]
            payload = "\n".join(rows) + "\n"
        if out is None:
            typer.echo(payload, nl=False)
        else:
            _write_new_file(out, payload.encode(), label="collection output")
            typer.echo(
                f"Selected {collection.delivered_count} of {count} requested arrangements. "
                f"Saved to {out}."
            )
            for member in collection.members:
                typer.echo(
                    f"Rank {member.rank}: balance {member.evaluation.balance_score:.3f}; "
                    f"{member.evaluation.sequence}"
                )
            if collection.delivered_count < count:
                typer.echo("The retained sequences did not supply the full requested collection.")
    except (OSError, MotifBalanceError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="design")

"""Collect ranked architectures from the retained pool of a verified bundle.

Maintainer(s): Eric J. South, Dunlop Lab
"""

import json
import os
from pathlib import Path
from typing import Annotated, Literal

import typer

from motif_balance.alternatives import rank_architectures
from motif_balance.artifacts import read_verified_portfolio
from motif_balance.errors import ArtifactError, MotifBalanceError

from .errors import _emit_error
from .output import _write_new_file


def collect_command(
    bundle: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    expected_bundle_id: Annotated[
        str, typer.Option(help="Separately retained identity of the search bundle.")
    ],
    count: Annotated[int, typer.Option(min=1, help="Return up to this many architectures.")],
    grouping: Annotated[
        Literal["interval_topology", "exact_offsets"],
        typer.Option(help="Architecture equivalence policy."),
    ] = "interval_topology",
    format_name: Annotated[Literal["text", "json"], typer.Option("--format")] = "text",
    out: Annotated[Path | None, typer.Option(help="New output file.")] = None,
    debug: Annotated[bool, typer.Option(help="Show the underlying exception.")] = False,
) -> None:
    """Choose up to COUNT distinct architectures and report the full size-quality profile."""
    try:
        if out is not None and os.path.lexists(out):
            raise ArtifactError("Refusing to replace existing collection output.", field="out")
        saved = read_verified_portfolio(bundle, expected_bundle_id=expected_bundle_id)
        ranking = rank_architectures(
            tuple(item.sequence for item in saved.manifest.elites), saved.spec, grouping=grouping
        )
        collection = ranking.select_up_to(count)
        if format_name == "json":
            payload = (
                json.dumps(
                    {
                        "source_bundle_id": expected_bundle_id,
                        "pool": "retained_elites",
                        "ranking": ranking.model_dump(mode="json"),
                        "collection": collection.model_dump(mode="json"),
                    },
                    indent=2,
                    allow_nan=False,
                )
                + "\n"
            )
        else:
            rows = [
                f"Delivered {collection.delivered_count} of up to {count} architectures: "
                f"{collection.status}.",
                f"Grouping: {grouping}; support: {collection.available_count} classes "
                "in retained elites.",
                "Size / weakest balance (every supported size):",
                *(f"{p.architecture_count} / {p.minimum_balance:.6g}" for p in ranking.prefixes),
                "Selected sequences:",
                *(
                    f"{m.rank}: {m.evaluation.sequence} balance={m.evaluation.balance_score:.6g}"
                    for m in collection.members
                ),
                "Coverage is the retained pool; shortfall does not prove "
                "sequence-space impossibility.",
            ]
            payload = "\n".join(rows) + "\n"
        if out is None:
            typer.echo(payload, nl=False)
        else:
            _write_new_file(out, payload.encode(), label="collection output")
    except (OSError, MotifBalanceError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="design")

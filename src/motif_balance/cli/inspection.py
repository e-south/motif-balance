"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/cli/inspection.py

Inspect saved designs and collections as text, JSON, HTML, SVG, or PNG.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import ValidationError

from motif_balance.errors import ArtifactError, MotifBalanceError
from motif_balance.inspection import ResultInspection, inspect_result
from motif_balance.inspection.candidate_svg_receipt import render_candidate_svg_receipt
from motif_balance.inspection.render import (
    render_candidate_svg,
    render_html,
    render_inspection_json,
    render_portfolio_svg,
    render_search_svg,
    render_text,
)
from motif_balance.inspection.render.png import svg_to_png

from .collection_inspection import collection_payload
from .errors import _emit_error
from .output import (
    _publish_or_emit,
    _require_new_inspection_output,
    _validate_inspection_output_path,
    _write_new_file_pair,
)


def _inspection_payload(
    value: ResultInspection,
    *,
    format_name: Literal["text", "json", "html", "svg", "png"],
    view: Literal["candidate", "portfolio", "search"] | None = None,
    candidate_rank: int = 1,
    compact: bool = False,
    width: int = 1800,
) -> bytes:
    if format_name == "text":
        return render_text(value).encode()
    if format_name == "json":
        return render_inspection_json(value)
    if format_name == "html":
        return render_html(value)
    if format_name == "png":
        return svg_to_png(
            render_candidate_svg(value, candidate_rank=candidate_rank, compact=True), width=width
        )
    if format_name == "svg":
        if view is None:
            raise ArtifactError("SVG inspection requires --view candidate, portfolio, or search")
        if view == "candidate":
            return render_candidate_svg(value, candidate_rank=candidate_rank, compact=compact)
        if view == "portfolio":
            return render_portfolio_svg(value)
        if view == "search":
            payload = render_search_svg(value)
            if payload is None:
                raise ArtifactError("this result does not contain a recorded search view")
            return payload
        raise ArtifactError(f"unsupported inspection view '{view}'")
    raise ArtifactError(f"unsupported inspection format '{format_name}'")


def inspect_command(
    subject: Annotated[Path, typer.Argument(exists=True, readable=True)],
    source: Annotated[
        Literal["bundle", "execution"],
        typer.Option("--source", help="Saved design or recorded execution."),
    ] = "bundle",
    format_name: Annotated[
        Literal["text", "json", "html", "svg", "png"],
        typer.Option("--format", help="Text, structured data, or a visual review."),
    ] = "text",
    view: Annotated[
        Literal["candidate", "portfolio", "search"] | None,
        typer.Option("--view", help="SVG view for a design bundle."),
    ] = None,
    candidate_rank: Annotated[
        int | None,
        typer.Option(
            "--candidate", min=1, help="One candidate rank, or all selected collection members."
        ),
    ] = None,
    compact: Annotated[
        bool, typer.Option(help="Show only the molecule and scores in a candidate SVG.")
    ] = False,
    width: Annotated[int, typer.Option(min=400, max=4096, help="PNG width in pixels.")] = 1800,
    out: Annotated[Path | None, typer.Option("--out", help="New derived output file.")] = None,
    receipt_out: Annotated[
        Path | None,
        typer.Option("--receipt-out", help="New candidate SVG receipt file."),
    ] = None,
    expected_bundle_id: Annotated[str | None, typer.Option("--expected-bundle-id")] = None,
    expected_workspace_id: Annotated[str | None, typer.Option("--expected-workspace-id")] = None,
    expected_receipt_sha256: Annotated[
        str | None, typer.Option("--expected-receipt-sha256")
    ] = None,
    expected_release_sha256: Annotated[
        str | None, typer.Option("--expected-release-sha256")
    ] = None,
    expected_producer_revision: Annotated[
        str | None, typer.Option("--expected-producer-revision")
    ] = None,
    debug: Annotated[bool, typer.Option("--debug")] = False,
) -> None:
    """View DNA and scores from a saved design or collection JSON."""

    try:
        if out is not None:
            _validate_inspection_output_path(out, subject=subject, field="out")
            _require_new_inspection_output(out, field="out")
        collection = subject.is_file()
        if collection:
            if (
                source != "bundle"
                or receipt_out is not None
                or any(
                    value is not None
                    for value in (
                        expected_bundle_id,
                        expected_workspace_id,
                        expected_receipt_sha256,
                        expected_release_sha256,
                        expected_producer_revision,
                    )
                )
            ):
                raise ArtifactError(
                    "Collection inspection rechecks scores; bundle identity and receipt "
                    "options require a result directory"
                )
            if view not in (None, "candidate"):
                raise ArtifactError(
                    "A collection supports molecular views, not search or portfolio views"
                )
        if format_name != "png" and width != 1800:
            raise ArtifactError("--width applies only to PNG output")
        if compact and not (format_name == "svg" and view == "candidate" and not collection):
            raise ArtifactError("--compact applies only to a design's candidate SVG")
        if receipt_out is not None and compact:
            raise ArtifactError("Candidate receipts require the full SVG view")
        if receipt_out is not None and not (
            format_name == "svg" and view == "candidate" and out is not None
        ):
            raise ArtifactError("--receipt-out is valid only with candidate SVG --out")
        if receipt_out is not None and out is not None:
            if receipt_out.resolve(strict=False) == out.resolve(strict=False):
                raise ArtifactError("--out and --receipt-out must use distinct paths")
            _validate_inspection_output_path(
                receipt_out,
                subject=subject,
                field="receipt_out",
            )
            _require_new_inspection_output(receipt_out, field="receipt_out")
        if format_name in {"html", "svg", "png"} and out is None:
            raise ArtifactError(
                f"--out is required for {format_name.upper()} inspection.",
                field="out",
                hint="Choose a new file outside the inspected result.",
            )
        if format_name not in {"svg", "png"} and view is not None:
            raise ArtifactError("--view is valid only with SVG or PNG output")
        if format_name == "png" and view not in (None, "candidate"):
            raise ArtifactError("PNG inspection supports the candidate view")
        if (
            not collection
            and format_name != "png"
            and view != "candidate"
            and candidate_rank is not None
        ):
            raise ArtifactError("--candidate is valid only for candidate SVG or PNG output")
        if collection:
            payload = collection_payload(
                subject, format_name=format_name, candidate_rank=candidate_rank, width=width
            )
            _publish_or_emit(payload, out, subject_roots=(subject,))
            return
        result = inspect_result(
            subject,
            kind=source,
            expected_bundle_id=expected_bundle_id,
            expected_workspace_id=expected_workspace_id,
            expected_receipt_sha256=expected_receipt_sha256,
            expected_release_sha256=expected_release_sha256,
            expected_producer_revision=expected_producer_revision,
        )
        payload = _inspection_payload(
            result,
            format_name=format_name,
            view=view,
            candidate_rank=candidate_rank or 1,
            compact=compact,
            width=width,
        )
        receipt = (
            render_candidate_svg_receipt(
                result,
                candidate_rank=candidate_rank or 1,
                svg=payload,
            )
            if receipt_out is not None
            else None
        )
        if receipt_out is not None:
            assert receipt is not None
            assert out is not None
            _write_new_file_pair(out, payload, receipt_out, receipt)
        else:
            _publish_or_emit(
                payload,
                out,
                subject_roots=(subject,),
            )
    except (OSError, MotifBalanceError, ValidationError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="artifact")

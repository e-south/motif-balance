from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Annotated, Any, Literal, NoReturn

import typer
import yaml
from pydantic import ValidationError

from motif_balance.api import design, score
from motif_balance.compile import compile_design, planned_search_kind
from motif_balance.errors import ArtifactError, InvalidDesign, InvalidMotif, MotifBalanceError
from motif_balance.execution import execute_design_workspace
from motif_balance.formats import convert_jaspar
from motif_balance.formats.design import load_design_spec
from motif_balance.inspection import ResultInspection, inspect_result
from motif_balance.inspection.render import (
    render_candidate_svg,
    render_html,
    render_inspection_json,
    render_portfolio_svg,
    render_search_svg,
    render_text,
)

app = typer.Typer(add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False)
motif_app = typer.Typer(add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False)
orchestration_app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
app.add_typer(motif_app, name="motif", hidden=True)
app.add_typer(orchestration_app, name="orchestration", hidden=True)


@app.callback()
def root() -> None:
    """Design, score, and inspect fixed-length DNA sequences against motif models."""


def _validation_error(exc: ValidationError, *, domain: str) -> MotifBalanceError:
    error = exc.errors(include_url=False)[0]
    location = ".".join(str(part) for part in error.get("loc", ())) or None
    if domain == "design" and error.get("type") == "extra_forbidden":
        message = f"Unknown field '{location}'."
        hint = "Remove the field or use a documented design-spec/v1 field."
    else:
        message = f"Invalid {domain} value{f' for {location}' if location else ''}: {error['msg']}."
        hint = f"Correct the {domain} input and retry the operation."
    error_type = _domain_error_type(domain)
    return error_type(message, field=location, hint=hint)


def _domain_error_type(
    domain: str,
) -> type[ArtifactError] | type[InvalidMotif] | type[InvalidDesign]:
    return (
        ArtifactError
        if domain == "artifact"
        else InvalidMotif
        if domain == "motif"
        else InvalidDesign
    )


def _emit_error(exc: Exception, *, debug: bool, domain: str) -> NoReturn:
    if debug:
        raise exc
    if isinstance(exc, ValidationError):
        error: MotifBalanceError = _validation_error(exc, domain=domain)
    elif isinstance(exc, MotifBalanceError):
        error = exc
    else:
        error = _domain_error_type(domain)(
            f"Unable to complete the {domain} operation.",
            hint="Run with --debug for the underlying exception after checking the input.",
        )
    typer.echo(f"error {error.code}: {error}", err=True)
    if error.field is not None:
        typer.echo(f"field: {error.field}", err=True)
    if error.motif_id is not None:
        typer.echo(f"motif: {error.motif_id}", err=True)
    if error.hint is not None:
        typer.echo(f"hint: {error.hint}", err=True)
    raise typer.Exit(code=2)


def _publish_or_emit(
    payload: bytes,
    out: Path | None,
    *,
    subject_roots: tuple[Path, ...] = (),
) -> None:
    if out is None:
        typer.echo(payload.decode(), nl=False)
        return
    resolved_out = out.resolve(strict=False)
    if any(resolved_out.is_relative_to(root.resolve()) for root in subject_roots):
        raise ArtifactError(
            "Inspection output must remain outside every inspected result root.",
            field="out",
            hint="Choose a separate review or handoff directory.",
        )
    _write_new_file(out, payload, label="inspection output")


def _write_new_file(path: Path, payload: bytes, *, label: str) -> None:
    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path, follow_symlinks=False)
    except FileExistsError as exc:
        raise ArtifactError(
            f"Refusing to replace existing {label} '{path.name}'.",
            field="out",
            hint="Choose a new output path.",
        ) from exc
    except OSError as exc:
        raise ArtifactError(
            f"Unable to write {label} '{path.name}'.",
            field="out",
            hint="Choose a writable output path whose parent directory exists.",
        ) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@app.command("design")
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
            typer.echo(
                f"motifs={len(spec.motifs)} length={spec.length} count={spec.count} "
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
        portfolio = design(spec)
        portfolio.write(out)
        best = portfolio.best
        typer.echo(
            f"Returned {len(portfolio.candidates)} of {spec.count} candidates for "
            f"{', '.join(motif.motif_id for motif in spec.motifs)}, each {spec.length} nt."
        )
        typer.echo(f"Best balance score: {best.balance_score:.6g}.")
        if spec.min_distance is not None and spec.min_distance > 0.0:
            typer.echo(f"Requested minimum distance: {spec.min_distance:.6g}.")
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


@app.command("score")
def score_command(
    specification: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    sequence: Annotated[str, typer.Argument(help="Exact A/C/G/T sequence to score.")],
    format_name: Annotated[
        Literal["text", "json"],
        typer.Option("--format", help="Terminal or machine-readable result."),
    ] = "text",
    out: Annotated[Path | None, typer.Option("--out", help="New output file.")] = None,
    debug: Annotated[bool, typer.Option("--debug", help="Show the underlying exception.")] = False,
) -> None:
    """Score one sequence under an explicit DesignSpec."""

    try:
        evaluation = score(sequence, load_design_spec(specification))
        if format_name == "json":
            payload = (evaluation.model_dump_json(indent=2) + "\n").encode()
        else:
            matches = "\n".join(
                f"{match.motif_id}: normalized={match.normalized_score:.17g} "
                f"raw={match.raw_score:.17g} strand={match.strand} "
                f"coordinates=[{match.start}, {match.end})"
                for match in evaluation.matches
            )
            payload = (
                f"balance_score={evaluation.balance_score:.17g}\n"
                f"sequence={evaluation.sequence}\n{matches}\n"
            ).encode()
        _publish_or_emit(payload, out)
    except (OSError, MotifBalanceError, ValidationError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="design")


def _inspection_payload(
    value: ResultInspection,
    *,
    format_name: Literal["text", "json", "html", "svg"],
    view: Literal["candidate", "portfolio", "search"] | None = None,
    candidate_rank: int = 1,
) -> bytes:
    if format_name == "text":
        return render_text(value).encode()
    if format_name == "json":
        return render_inspection_json(value)
    if format_name == "html":
        return render_html(value)
    if format_name == "svg":
        if view is None:
            raise ArtifactError("SVG inspection requires --view candidate, portfolio, or search")
        if view == "candidate":
            return render_candidate_svg(value, candidate_rank=candidate_rank)
        if view == "portfolio":
            return render_portfolio_svg(value)
        if view == "search":
            payload = render_search_svg(value)
            if payload is None:
                raise ArtifactError("this result does not contain a recorded search view")
            return payload
        raise ArtifactError(f"unsupported inspection view '{view}'")
    raise ArtifactError(f"unsupported inspection format '{format_name}'")


@app.command("inspect")
def inspect_command(
    subject: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    source: Annotated[
        Literal["bundle", "execution"],
        typer.Option("--source", help="Explicit result source contract."),
    ] = "bundle",
    format_name: Annotated[
        Literal["text", "json", "html", "svg"],
        typer.Option("--format", help="Review projection format."),
    ] = "text",
    view: Annotated[
        Literal["candidate", "portfolio", "search"] | None,
        typer.Option("--view", help="Required only for SVG output."),
    ] = None,
    candidate_rank: Annotated[
        int,
        typer.Option("--candidate", min=1, help="Candidate rank for the candidate SVG."),
    ] = 1,
    out: Annotated[Path | None, typer.Option("--out", help="New derived output file.")] = None,
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
    """Verify and review one immutable result."""

    try:
        if format_name in {"html", "svg"} and out is None:
            raise ArtifactError(
                f"--out is required for {format_name.upper()} inspection.",
                field="out",
                hint="Choose a new file outside the inspected result.",
            )
        if format_name != "svg" and view is not None:
            raise ArtifactError("--view is valid only with --format svg")
        if view != "candidate" and candidate_rank != 1:
            raise ArtifactError("--candidate is valid only for the candidate SVG view")
        result = inspect_result(
            subject,
            kind=source,
            expected_bundle_id=expected_bundle_id,
            expected_workspace_id=expected_workspace_id,
            expected_receipt_sha256=expected_receipt_sha256,
            expected_release_sha256=expected_release_sha256,
            expected_producer_revision=expected_producer_revision,
        )
        _publish_or_emit(
            _inspection_payload(
                result,
                format_name=format_name,
                view=view,
                candidate_rank=candidate_rank,
            ),
            out,
            subject_roots=(subject,),
        )
    except (OSError, MotifBalanceError, ValidationError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="artifact")


def _background(value: str) -> tuple[float, float, float, float]:
    try:
        parsed = tuple(float(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise InvalidMotif(
            "Background must contain four comma-separated numbers in A,C,G,T order.",
            field="background",
            hint="For a uniform background use 0.25,0.25,0.25,0.25.",
        ) from exc
    if len(parsed) != 4:
        raise InvalidMotif(
            "Background must contain exactly four values in A,C,G,T order.",
            field="background",
            hint="For a uniform background use 0.25,0.25,0.25,0.25.",
        )
    return parsed[0], parsed[1], parsed[2], parsed[3]


@motif_app.command("prepare")
def prepare_motif_command(
    source: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    motif_id: Annotated[str, typer.Option("--motif-id")],
    background: Annotated[str, typer.Option("--background")],
    prior_weight: Annotated[float, typer.Option("--prior-weight", min=0.0)],
    out: Annotated[Path, typer.Option("--out")],
    debug: Annotated[bool, typer.Option("--debug")] = False,
) -> None:
    """Prepare one canonical motif model from a supported source file."""

    try:
        motif = convert_jaspar(
            source,
            motif_id=motif_id,
            background=_background(background),
            prior_weight=prior_weight,
        )
        payload = yaml.safe_dump(
            motif.model_dump(mode="json", exclude_none=True),
            sort_keys=False,
        ).encode()
        _write_new_file(out, payload, label="motif model")
        typer.echo(f"complete {motif.model_digest} {out}")
    except (OSError, MotifBalanceError, ValidationError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="motif")


@orchestration_app.command("execute")
def execute_command(
    specification: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    producer_revision: Annotated[str, typer.Option("--producer-revision")],
    release_artifact: Annotated[
        Path,
        typer.Option("--release-artifact", exists=True, dir_okay=False, readable=True),
    ],
    out: Annotated[Path, typer.Option("--out")],
    debug: Annotated[bool, typer.Option("--debug")] = False,
) -> None:
    """Publish one release-attested execution workspace."""

    try:
        workspace = execute_design_workspace(
            specification,
            out,
            producer_revision=producer_revision,
            release_artifact=release_artifact,
        )
        typer.echo(f"complete {workspace.workspace_id} {out}")
    except (OSError, MotifBalanceError, ValidationError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="design")


def main() -> Any:
    return app()


if __name__ == "__main__":  # pragma: no cover
    main()

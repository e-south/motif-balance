from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer
import yaml
from pydantic import ValidationError

from motif_balance.api import (
    _planned_search_kind,
    compile_spec,
    convert_motif,
    design,
    execute_design_workspace,
    load_spec,
    render_bundle_report,
    verify_bundle,
    verify_execution_workspace,
)
from motif_balance.errors import ArtifactError, InvalidDesign, InvalidMotif, MotifBalanceError

app = typer.Typer(add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False)


@app.callback()
def root() -> None:
    """Design fixed-length DNA sequences against explicit motif models."""


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


@app.command("design")
def design_command(
    specification: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    out: Annotated[Path | None, typer.Option("--out", help="Immutable output directory.")] = None,
    check: Annotated[
        bool, typer.Option("--check", help="Compile and validate without search.")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Show the underlying exception.")] = False,
) -> None:
    """Compile or execute one immutable scientific design specification."""
    try:
        spec = load_spec(specification)
        problem_id = compile_spec(spec)
        if check:
            search_kind = _planned_search_kind(spec)
            typer.echo(f"valid {problem_id}")
            typer.echo(
                f"motifs={len(spec.motifs)} length={spec.length} count={spec.count} "
                f"strands={spec.strands} evaluations={spec.evaluations} "
                f"min_distance={spec.min_distance} search={search_kind}"
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
        typer.echo(f"complete {portfolio.manifest.bundle_id} {out}")
    except (OSError, MotifBalanceError, ValidationError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="design")


@app.command("verify")
def verify_command(
    bundle: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    expected_bundle_id: Annotated[
        str | None,
        typer.Option("--expected-bundle-id", help="Externally trusted bundle identity."),
    ] = None,
    debug: Annotated[bool, typer.Option("--debug", help="Show the underlying exception.")] = False,
) -> None:
    """Verify bytes, schemas, identities, and scientific replay."""
    try:
        identity = verify_bundle(bundle, expected_bundle_id=expected_bundle_id)
        typer.echo(f"valid {identity}")
    except (MotifBalanceError, ValidationError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="artifact")


@app.command("render-report")
def render_report_command(
    bundle: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    out: Annotated[Path, typer.Option("--out", help="New HTML report path.")],
    debug: Annotated[bool, typer.Option("--debug", help="Show the underlying exception.")] = False,
) -> None:
    """Regenerate a report from a verified canonical bundle."""
    try:
        bundle_id = render_bundle_report(bundle, out)
        typer.echo(f"complete {bundle_id} {out}")
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


@app.command("convert-motif")
def convert_motif_command(
    source: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    motif_id: Annotated[str, typer.Option("--motif-id", help="Canonical output motif ID.")],
    background: Annotated[
        str,
        typer.Option("--background", help="Explicit A,C,G,T background frequencies."),
    ],
    prior_weight: Annotated[
        float,
        typer.Option("--prior-weight", min=0.0, help="Explicit probability-mixture weight."),
    ],
    out: Annotated[Path, typer.Option("--out", help="New canonical YAML model path.")],
    debug: Annotated[bool, typer.Option("--debug", help="Show the underlying exception.")] = False,
) -> None:
    """Convert one JASPAR count matrix under explicit scientific semantics."""
    try:
        motif = convert_motif(
            source,
            motif_id=motif_id,
            background=_background(background),
            prior_weight=prior_weight,
        )
        payload = yaml.safe_dump(
            motif.model_dump(mode="json", exclude_none=True),
            sort_keys=False,
        ).encode()
        try:
            with out.open("xb") as handle:
                handle.write(payload)
        except FileExistsError as exc:
            raise ArtifactError(
                f"Refusing to replace existing motif model '{out.name}'.",
                field="out",
                hint="Choose a new output path.",
            ) from exc
        typer.echo(f"complete {motif.model_digest} {out}")
    except (OSError, MotifBalanceError, ValidationError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="motif")


@app.command("execute")
def execute_command(
    specification: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    producer_revision: Annotated[
        str,
        typer.Option("--producer-revision", help="Exact 40-character source revision."),
    ],
    release_artifact: Annotated[
        Path,
        typer.Option(
            "--release-artifact",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Exact wheel whose package tree must match the running implementation.",
        ),
    ],
    out: Annotated[Path, typer.Option("--out", help="New atomic execution workspace.")],
    debug: Annotated[bool, typer.Option("--debug", help="Show the underlying exception.")] = False,
) -> None:
    """Execute design and atomically publish input, release, bundle, and receipt."""
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


@app.command("verify-execution")
def verify_execution_command(
    workspace: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    expected_workspace_id: Annotated[str, typer.Option("--expected-workspace-id")],
    expected_receipt_sha256: Annotated[str, typer.Option("--expected-receipt-sha256")],
    expected_release_sha256: Annotated[str, typer.Option("--expected-release-sha256")],
    expected_producer_revision: Annotated[str, typer.Option("--expected-producer-revision")],
    debug: Annotated[bool, typer.Option("--debug", help="Show the underlying exception.")] = False,
) -> None:
    """Verify an execution workspace against externally trusted identities."""
    try:
        identity = verify_execution_workspace(
            workspace,
            expected_workspace_id=expected_workspace_id,
            expected_receipt_sha256=expected_receipt_sha256,
            expected_release_sha256=expected_release_sha256,
            expected_producer_revision=expected_producer_revision,
        )
        typer.echo(f"valid {identity}")
    except (OSError, MotifBalanceError, ValidationError, ValueError) as exc:
        _emit_error(exc, debug=debug, domain="artifact")


def main() -> Any:
    return app()


if __name__ == "__main__":  # pragma: no cover
    main()

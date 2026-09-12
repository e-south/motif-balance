from __future__ import annotations

from typing import NoReturn

import typer
from pydantic import ValidationError

from motif_balance.errors import ArtifactError, InvalidDesign, InvalidMotif, MotifBalanceError


def _validation_error(exc: ValidationError, *, domain: str) -> MotifBalanceError:
    error = exc.errors(include_url=False)[0]
    location = ".".join(str(part) for part in error.get("loc", ())) or None
    if domain == "design" and error.get("type") == "extra_forbidden":
        message = f"Unknown field '{location}'."
        hint = "Remove the field or use a documented DesignSpec field."
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

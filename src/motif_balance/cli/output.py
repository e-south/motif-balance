from __future__ import annotations

import os
import tempfile
from pathlib import Path

import typer

from motif_balance.errors import ArtifactError


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


def _validate_inspection_output_path(path: Path, *, subject: Path, field: str) -> None:
    if path.resolve(strict=False).is_relative_to(subject.resolve()):
        raise ArtifactError(
            "Inspection output must remain outside every inspected result root.",
            field=field,
            hint="Choose a separate review or handoff directory.",
        )


def _require_new_inspection_output(path: Path, *, field: str) -> None:
    if os.path.lexists(path):
        raise ArtifactError(
            f"Refusing to replace existing inspection output '{path.name}'.",
            field=field,
            hint="Choose a new output path.",
        )


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


def _write_new_file_pair(
    first_path: Path,
    first_payload: bytes,
    second_path: Path,
    second_payload: bytes,
) -> None:
    """Publish two new files as one pair, rolling back only links created here."""

    staged: list[tuple[Path, Path]] = []
    created: list[tuple[Path, Path]] = []
    try:
        for path, payload in (
            (first_path, first_payload),
            (second_path, second_payload),
        ):
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=path.parent,
            )
            temporary = Path(temporary_name)
            staged.append((path, temporary))
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        for path, temporary in staged:
            os.link(temporary, path, follow_symlinks=False)
            created.append((path, temporary))
    except FileExistsError as exc:
        raise ArtifactError(
            "Refusing to replace an existing candidate SVG publication file.",
            field="out",
            hint="Choose new output and receipt paths.",
        ) from exc
    except OSError as exc:
        raise ArtifactError(
            "Unable to write the candidate SVG publication pair.",
            field="out",
            hint="Choose writable output paths whose parent directories exist.",
        ) from exc
    finally:
        if len(created) != 2:
            for path, temporary in created:
                try:
                    if os.path.samefile(path, temporary):
                        path.unlink()
                except (FileNotFoundError, OSError):
                    pass
        for _, temporary in staged:
            temporary.unlink(missing_ok=True)

from __future__ import annotations

import os
from pathlib import Path

import pytest

import motif_balance.formats.structured as structured_module
from motif_balance.errors import InvalidDesign, InvalidMotif
from motif_balance.formats import convert_jaspar, read_motif
from motif_balance.formats.design import load_design_spec

_MOTIF = b"""schema_version: motif-model/v2
motif_id: trusted
probabilities:
  - [0.7, 0.1, 0.1, 0.1]
background: [0.25, 0.25, 0.25, 0.25]
"""
_DESIGN = b"""schema_version: design-spec/v2
motifs:
  trusted:
    schema_version: motif-model/v2
    probabilities:
      - [0.7, 0.1, 0.1, 0.1]
    background: [0.25, 0.25, 0.25, 0.25]
length: 1
count: 1
evaluations: 4
seed: 0
"""
_JASPAR = b">MA0001.1 trusted\nA [8 0]\nC [0 8]\nG [0 0]\nT [0 0]\n"


def _case(kind: str, path: Path) -> None:
    if kind == "design":
        load_design_spec(path)
    elif kind == "motif":
        read_motif(path)
    else:
        convert_jaspar(
            path,
            motif_id="trusted",
            background=(0.25, 0.25, 0.25, 0.25),
        )


@pytest.mark.parametrize(
    ("kind", "name", "payload", "error"),
    [
        ("design", "design.yaml", _DESIGN, InvalidDesign),
        ("motif", "motif.yaml", _MOTIF, InvalidMotif),
        ("jaspar", "motif.jaspar", _JASPAR, InvalidMotif),
    ],
)
@pytest.mark.parametrize("substitution", ["inode", "symlink", "fifo"])
def test_untrusted_input_readers_reject_substitution_without_blocking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    name: str,
    payload: bytes,
    error: type[Exception],
    substitution: str,
) -> None:
    source = tmp_path / name
    source.write_bytes(payload)
    original = tmp_path / f"original-{name}"
    real_open = structured_module.os.open
    substituted = False

    def substitute_then_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
        nonlocal substituted
        if Path(path) in {source, Path(source.name)} and not substituted:
            substituted = True
            source.rename(original)
            if substitution == "inode":
                source.write_bytes(original.read_bytes())
            elif substitution == "symlink":
                source.symlink_to(original.name)
            else:
                os.mkfifo(source)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(structured_module.os, "open", substitute_then_open)

    with pytest.raises(error, match=r"unsafe|changed"):
        _case(kind, source)


@pytest.mark.parametrize(
    ("kind", "name", "payload", "error"),
    [
        ("design", "design.yaml", _DESIGN, InvalidDesign),
        ("motif", "motif.yaml", _MOTIF, InvalidMotif),
        ("jaspar", "motif.jaspar", _JASPAR, InvalidMotif),
    ],
)
def test_untrusted_input_readers_reject_growth_during_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    name: str,
    payload: bytes,
    error: type[Exception],
) -> None:
    source = tmp_path / name
    source.write_bytes(payload)
    source_inode = source.stat().st_ino
    real_read = structured_module.os.read
    grown = False

    def grow_then_read(descriptor: int, count: int) -> bytes:
        nonlocal grown
        if os.fstat(descriptor).st_ino == source_inode and not grown:
            grown = True
            with source.open("ab") as handle:
                handle.write(b"\n")
        return real_read(descriptor, count)

    monkeypatch.setattr(structured_module.os, "read", grow_then_read)

    with pytest.raises(error, match="changed"):
        _case(kind, source)


def test_oversized_input_is_rejected_before_path_read_allocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "oversized.yaml"
    source.write_bytes(b"x" * 17)
    monkeypatch.setattr(structured_module, "MAX_INPUT_BYTES", 16)

    def reject_path_allocation(_path: Path) -> bytes:
        raise AssertionError("UNBOUNDED_PATH_READ_REACHED")

    monkeypatch.setattr(Path, "read_bytes", reject_path_allocation)

    with pytest.raises(InvalidMotif, match="byte limit"):
        read_motif(source)


@pytest.mark.parametrize("role", ["target", "avoider"])
@pytest.mark.parametrize("substitution", ["inode", "symlink"])
def test_design_motif_references_reject_intermediate_directory_substitution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
    substitution: str,
) -> None:
    specification = tmp_path / "specification"
    models = specification / "models"
    models.mkdir(parents=True)
    motif_name = f"{role}.yaml"
    (models / motif_name).write_bytes(_MOTIF.replace(b"trusted", role.encode()))
    external = tmp_path / "external-models"
    external.mkdir()
    (external / motif_name).write_bytes(_MOTIF.replace(b"trusted", role.encode()))
    design = specification / "design.yaml"
    if role == "target":
        motif_section = f"motifs:\n  {role}: models/{motif_name}\n"
    else:
        motif_section = (
            "motifs:\n"
            "  target:\n"
            "    schema_version: motif-model/v2\n"
            "    probabilities: [[0.7, 0.1, 0.1, 0.1]]\n"
            "    background: [0.25, 0.25, 0.25, 0.25]\n"
            f"avoiders:\n  {role}:\n    motif: models/{motif_name}\n"
            "    score_ceiling: 0.5\n"
        )
    design.write_text(
        "schema_version: design-spec/v2\n"
        f"{motif_section}"
        "length: 1\ncount: 1\nevaluations: 4\nseed: 0\n"
    )
    original = specification / "original-models"
    real_resolve = Path.resolve
    real_stat = structured_module.os.stat
    substituted = False

    def substitute_directory() -> None:
        nonlocal substituted
        substituted = True
        models.rename(original)
        if substitution == "inode":
            models.mkdir()
            (models / motif_name).write_bytes((external / motif_name).read_bytes())
        else:
            models.symlink_to(external, target_is_directory=True)

    def resolve_then_substitute(self: Path, *args: object, **kwargs: object) -> Path:
        resolved = real_resolve(self, *args, **kwargs)
        if not substituted and self == models / motif_name:
            substitute_directory()
        return resolved

    def stat_then_substitute(
        path: object,
        *args: object,
        **kwargs: object,
    ) -> os.stat_result:
        result = real_stat(path, *args, **kwargs)
        if not substituted and Path(path).name == "models":
            substitute_directory()
        return result

    monkeypatch.setattr(Path, "resolve", resolve_then_substitute)
    monkeypatch.setattr(structured_module.os, "stat", stat_then_substitute)

    with pytest.raises(InvalidDesign, match=r"unsafe|changed|symbolic"):
        load_design_spec(design)


def test_design_motif_reference_rejects_same_size_in_place_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    models = tmp_path / "models"
    models.mkdir()
    motif = models / "target.yaml"
    motif.write_bytes(_MOTIF)
    motif_inode = motif.stat().st_ino
    design = tmp_path / "design.yaml"
    design.write_text(
        "schema_version: design-spec/v2\n"
        "motifs:\n  trusted: models/target.yaml\n"
        "length: 1\ncount: 1\nevaluations: 4\nseed: 0\n"
    )
    real_read = structured_module.os.read
    mutated = False

    def mutate_then_read(descriptor: int, count: int) -> bytes:
        nonlocal mutated
        if os.fstat(descriptor).st_ino == motif_inode and not mutated:
            mutated = True
            motif.write_bytes(_MOTIF.replace(b"0.7", b"0.6"))
        return real_read(descriptor, count)

    monkeypatch.setattr(structured_module.os, "read", mutate_then_read)

    with pytest.raises(InvalidDesign, match="changed"):
        load_design_spec(design)

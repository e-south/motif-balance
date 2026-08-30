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
        if Path(path) == source and not substituted:
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

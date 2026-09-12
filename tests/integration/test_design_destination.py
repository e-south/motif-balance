"""Reject occupied destinations before search without weakening publication."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

import motif_balance.cli as cli
from motif_balance import DesignSpec, Portfolio
from motif_balance.api import design
from motif_balance.cli import design as design_cli

SPECIFICATION = Path(__file__).resolve().parents[2] / "examples/synthetic-pairwise/design.yaml"
runner = CliRunner()


@pytest.mark.parametrize("kind", ["directory", "file", "symlink", "dangling_symlink"])
def test_occupied_destination_is_rejected_before_search(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    output = tmp_path / "result"
    if kind == "directory":
        output.mkdir()
    elif kind == "file":
        output.write_text("keep me")
    else:
        target = tmp_path / "target"
        if kind == "symlink":
            target.mkdir()
        output.symlink_to(target)
    identity = output.lstat()

    def forbidden_search(spec: DesignSpec) -> Portfolio:
        pytest.fail("an occupied destination must be rejected before search")

    monkeypatch.setattr(design_cli, "design", forbidden_search)
    result = runner.invoke(cli.app, ["design", str(SPECIFICATION), "--out", str(output)])

    assert result.exit_code == 2, result.output
    assert "error artifact_error:" in result.output
    assert "field: out" in result.output
    assert "hint: Choose a new output directory." in result.output
    observed = output.lstat()
    # Reading a symlink can update its access time on Linux.
    for field in (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_nlink",
        "st_uid",
        "st_gid",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    ):
        assert getattr(observed, field) == getattr(identity, field)
    if kind == "file":
        assert output.read_text() == "keep me"


def test_destination_created_during_search_is_not_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "result"

    def racing_search(spec: DesignSpec) -> Portfolio:
        portfolio = design(spec)
        output.mkdir()
        (output / "owner.txt").write_text("another caller")
        return portfolio

    monkeypatch.setattr(design_cli, "design", racing_search)
    result = runner.invoke(cli.app, ["design", str(SPECIFICATION), "--out", str(output)])

    assert result.exit_code == 2
    assert "already exists" in result.output
    assert list(output.iterdir()) == [output / "owner.txt"]
    assert (output / "owner.txt").read_text() == "another caller"


def test_check_does_not_reserve_an_output_path(tmp_path: Path) -> None:
    output = tmp_path / "new-parent" / "result"

    result = runner.invoke(cli.app, ["design", str(SPECIFICATION), "--check", "--out", str(output)])

    assert result.exit_code == 0, result.output
    assert not output.parent.exists()

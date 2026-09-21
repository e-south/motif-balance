"""The playback command preserves inputs and refuses invalid output requests."""

import typer
from typer.testing import CliRunner

from motif_balance.api import design_observed
from motif_balance.cli.playback import animate_command
from motif_balance.model.search_observation import ObservationSpec


def test_playback_cli_uses_a_verified_record_and_new_output(pairwise_spec, tmp_path):
    app = typer.Typer()
    app.command()(animate_command)
    runner = CliRunner()
    _, observation = design_observed(
        pairwise_spec.model_copy(update={"count": 1}), ObservationSpec(max_snapshots=3)
    )
    source = tmp_path / "observation.json"
    source.write_text(observation.model_dump_json())
    out = tmp_path / "playback.html"
    result = runner.invoke(app, [str(source), "--out", str(out)])
    assert result.exit_code == 0, result.output
    original = out.read_bytes()
    again = runner.invoke(app, [str(source), "--out", str(out)])
    assert again.exit_code != 0 and out.read_bytes() == original
    wrong = runner.invoke(app, [str(source), "--out", str(tmp_path / "wrong.mp4")])
    assert wrong.exit_code != 0
    assert not (tmp_path / "wrong.mp4").exists()
    source.write_text('{"engine":"invented"}')
    bad = tmp_path / "bad.html"
    result = runner.invoke(app, [str(source), "--out", str(bad)])
    assert result.exit_code != 0 and not bad.exists()


def test_playback_cli_refuses_symbolic_link_input(tmp_path):
    app = typer.Typer()
    app.command()(animate_command)
    source = tmp_path / "source.json"
    source.write_text("{}")
    alias = tmp_path / "alias.json"
    alias.symlink_to(source)
    out = tmp_path / "view.html"
    result = CliRunner().invoke(app, [str(alias), "--out", str(out)])
    assert result.exit_code != 0 and not out.exists()

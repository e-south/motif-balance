"""
--------------------------------------------------------------------------------
motif-balance
tests/integration/test_playback_cli.py

The playback command preserves inputs and refuses invalid output requests.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

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


def test_playback_cli_can_overlay_one_recorded_search_chain(pairwise_spec, tmp_path):
    app = typer.Typer()
    app.command()(animate_command)
    _, observation = design_observed(
        pairwise_spec.model_copy(update={"count": 1, "evaluations": 64}),
        ObservationSpec(max_snapshots=3),
    )
    source = tmp_path / "observation.json"
    source.write_text(observation.model_dump_json())
    out = tmp_path / "playback.svg"
    args = [str(source), "--search-chain", "0", "--format", "svg", "--out", str(out)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert 'data-duplex-layout="search"' in out.read_text()
    invalid = tmp_path / "conflict.svg"
    result = CliRunner().invoke(app, [*args[:-1], str(invalid), "--chain", "1"])
    assert result.exit_code != 0 and not invalid.exists()


def test_showcase_cli_shows_all_chains_and_stops_at_last_improvement(pairwise_spec, tmp_path):
    import xml.etree.ElementTree as ET

    app = typer.Typer()
    app.command()(animate_command)
    _, observation = design_observed(
        pairwise_spec.model_copy(update={"count": 1, "evaluations": 128}),
        ObservationSpec(max_snapshots=8),
    )
    source = tmp_path / "observation.json"
    source.write_text(observation.model_dump_json())
    out = tmp_path / "showcase.svg"
    result = CliRunner().invoke(
        app,
        [
            str(source),
            "--search-chain",
            "all",
            "--until-last-improvement",
            "--format",
            "svg",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    root = ET.fromstring(out.read_bytes())
    final_score = observation.snapshots[-1].incumbent.balance_score
    first_final = next(
        s.evaluations for s in observation.snapshots if s.incumbent.balance_score == final_score
    )
    assert root.get("data-evaluations") == str(first_final)
    assert len(root.findall(".//{http://www.w3.org/2000/svg}circle[@data-search-state]")) == 8
    invalid = tmp_path / "wrong.svg"
    result = CliRunner().invoke(
        app,
        [str(source), "--pacing", "accelerating", "--format", "svg", "--out", str(invalid)],
    )
    assert result.exit_code != 0 and not invalid.exists()

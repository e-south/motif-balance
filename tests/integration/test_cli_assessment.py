"""A pair can be assessed without a design request, search, or output directory."""

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from typer.main import get_command
from typer.testing import CliRunner

from motif_balance.cli import app

runner = CliRunner()


def _models(root: Path) -> tuple[Path, Path]:
    paths = root / "left.json", root / "right.json"
    for path, probabilities in zip(
        paths, ((0.7, 0.1, 0.1, 0.1), (0.1, 0.7, 0.1, 0.1)), strict=True
    ):
        path.write_text(
            json.dumps(
                {
                    "schema_version": "motif-model/v2",
                    "motif_id": path.stem,
                    "probabilities": [probabilities] * 3,
                    "background": [0.25] * 4,
                }
            )
        )
    return paths


def test_cli_assesses_a_pair_and_explains_its_scope(tmp_path: Path) -> None:
    left, right = _models(tmp_path)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    result = runner.invoke(app, ["assess", str(left), str(right), "--length", "3"])

    assert result.exit_code == 0, result.output
    assert "Structural score: 0.5" in result.stdout
    assert "Length: 3 nt; strands: both" in result.stdout
    assert "Sequence evaluations: 0" in result.stdout
    assert "not a predicted sequence score" in result.stdout
    assert "--format json" in result.stdout
    assert "Models: left=left; right=right" in result.stdout
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_cli_exports_the_complete_pair_profile_as_json(tmp_path: Path) -> None:
    left, right = _models(tmp_path)
    result = runner.invoke(
        app, ["assess", str(left), str(right), "--length", "6", "--format", "json"]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "pair-assessment/v1"
    assert payload["structural_score"] == pytest.approx(1.0)
    assert payload["sequence_evaluations"] == 0
    assert payload["arrangement_count"] == len(payload["arrangements"]) == 14
    assert payload["motifs"][0]["motif_id"] == "left"


@pytest.mark.parametrize("file_output", [False, True])
def test_cli_renders_presearch_preferences_without_a_candidate(tmp_path, file_output):
    left, right = _models(tmp_path)
    out = tmp_path / "preferences.svg"
    inputs = left.read_bytes(), right.read_bytes()
    result = runner.invoke(
        app,
        ["assess", str(left), str(right), "--length", "3", "--format", "svg"]
        + (["--out", str(out)] if file_output else []),
    )
    assert result.exit_code == 0, result.output
    root = ET.fromstring(out.read_bytes() if file_output else result.stdout)
    assert "not a designed sequence" in " ".join(root.itertext())
    assert len(root.findall(".//{http://www.w3.org/2000/svg}g[@class='assessment-logo']")) == 2
    assert (left.read_bytes(), right.read_bytes()) == inputs
    assert (result.stdout == "") == file_output


def test_svg_limit_refuses_before_calculation_or_writes(tmp_path, monkeypatch):
    from motif_balance.cli import assessment

    left, right = _models(tmp_path)
    out = tmp_path / "preferences.svg"

    def forbidden(*args, **kwargs):
        pytest.fail("SVG length admission must precede model assessment")

    monkeypatch.setattr(assessment, "assess_pair", forbidden)
    result = runner.invoke(
        app,
        ["assess", str(left), str(right), "--length", "129", "--format", "svg", "--out", str(out)],
    )
    assert result.exit_code == 2
    assert "128" in result.output
    assert "json" in result.output
    assert not out.exists()


def test_assessment_is_a_visible_journey_with_specific_help() -> None:
    commands = get_command(app).commands
    assert sorted(name for name, child in commands.items() if not child.hidden) == [
        "assess",
        "design",
        "inspect",
        "score",
    ]
    result = runner.invoke(app, ["assess", "--help"])
    assert result.exit_code == 0
    assert "without sequence search" in result.stdout
    assert "canonical YAML/JSON" in result.stdout


@pytest.mark.parametrize("kind", ["file", "directory", "symlink", "dangling_symlink"])
def test_occupied_output_fails_before_assessment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    from motif_balance.cli import assessment

    left, right = _models(tmp_path)
    out = tmp_path / "assessment.json"
    if kind == "directory":
        out.mkdir()
    elif kind == "file":
        out.write_text("existing")
    else:
        out.symlink_to(left if kind == "symlink" else tmp_path / "absent")
    before = out.lstat()

    def forbidden(*args, **kwargs):
        pytest.fail("occupied output must fail before assessment")

    monkeypatch.setattr(assessment, "assess_pair", forbidden)
    result = runner.invoke(
        app, ["assess", str(left), str(right), "--length", "3", "--out", str(out)]
    )
    assert result.exit_code == 2, result.output
    assert "Refusing to replace existing assessment output" in result.output
    assert out.lstat() == before


def test_cli_rejects_a_multimotif_format_without_silently_choosing_a_record(tmp_path: Path) -> None:
    _left, right = _models(tmp_path)
    meme = tmp_path / "ambiguous.meme"
    meme.write_text(
        "MEME version 4\nBackground letter frequencies\nA 0.25 C 0.25 G 0.25 T 0.25\n"
        "MOTIF first\nletter-probability matrix: alength= 4 w= 3\n"
        "0.7 0.1 0.1 0.1\n0.7 0.1 0.1 0.1\n0.7 0.1 0.1 0.1\n"
        "MOTIF second\nletter-probability matrix: alength= 4 w= 3\n"
        "0.1 0.7 0.1 0.1\n0.1 0.7 0.1 0.1\n0.1 0.7 0.1 0.1\n"
    )
    result = runner.invoke(app, ["assess", str(meme), str(right), "--length", "3"])
    assert result.exit_code == 2, result.output
    assert "canonical YAML/JSON motif models" in result.output
    assert "hint:" in result.output


@pytest.mark.parametrize(
    "options",
    [
        [],
        ["--length", "0"],
        ["--length", "2"],
        ["--length", "10001"],
        ["--length", "3", "--strands", "reverse"],
        ["--length", "3", "--format", "html"],
        ["--length", "3", "--seed", "7"],
    ],
)
def test_invalid_assessment_options_do_not_write(tmp_path: Path, options: list[str]) -> None:
    left, right = _models(tmp_path)
    out = tmp_path / "assessment.json"
    result = runner.invoke(app, ["assess", str(left), str(right), *options, "--out", str(out)])
    assert result.exit_code == 2, result.output
    assert not out.exists()
    assert "Traceback" not in result.output


@pytest.mark.parametrize("fault", ["symlink", "malformed", "unknown_field", "v1"])
def test_invalid_models_fail_without_an_assessment(tmp_path: Path, fault: str) -> None:
    left, right = _models(tmp_path)
    if fault == "symlink":
        alias = tmp_path / "alias.json"
        alias.symlink_to(left)
        left = alias
    elif fault == "malformed":
        left.write_text("not a JSON object")
    else:
        model = json.loads(left.read_text())
        model["unexpected" if fault == "unknown_field" else "schema_version"] = "motif-model/v1"
        left.write_text(json.dumps(model))
    result = runner.invoke(app, ["assess", str(left), str(right), "--length", "3"])
    assert result.exit_code == 2, result.output
    assert "error " in result.output
    assert "Structural score:" not in result.stdout


def test_json_file_output_preserves_inputs_and_has_no_console_payload(tmp_path: Path) -> None:
    left, right = _models(tmp_path)
    inputs = left.read_bytes(), right.read_bytes()
    out = tmp_path / "assessment.json"
    result = runner.invoke(
        app,
        [
            "assess",
            str(left),
            str(right),
            "--length",
            "4",
            "--strands",
            "forward",
            "--format",
            "json",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    payload = json.loads(out.read_text())
    assert payload["structural_score"] == pytest.approx(2 / 3)
    assert payload["arrangement_count"] == 3
    assert payload["equivalence"] == "translation"
    assert (left.read_bytes(), right.read_bytes()) == inputs
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "assessment.json",
        "left.json",
        "right.json",
    ]


def test_assessment_does_not_replace_output_created_during_calculation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from motif_balance.cli import assessment

    left, right = _models(tmp_path)
    out = tmp_path / "assessment.json"
    calculate = assessment.assess_pair

    def racing(*args, **kwargs):
        result = calculate(*args, **kwargs)
        out.write_text("another caller")
        return result

    monkeypatch.setattr(assessment, "assess_pair", racing)
    result = runner.invoke(
        app, ["assess", str(left), str(right), "--length", "3", "--out", str(out)]
    )
    assert result.exit_code == 2
    assert "Refusing to replace existing assessment output" in result.output
    assert out.read_text() == "another caller"
    assert len(list(tmp_path.iterdir())) == 3

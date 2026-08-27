from __future__ import annotations

import base64
import hashlib
import json
import struct
import zipfile
from pathlib import Path

from typer.testing import CliRunner

import motif_balance
from motif_balance.cli import app

runner = CliRunner()

_DESIGN = """schema_version: design-spec/v1
motifs:
  motif_a:
    probabilities:
      - [0.7, 0.1, 0.1, 0.1]
    background: [0.25, 0.25, 0.25, 0.25]
  motif_b:
    probabilities:
      - [0.1, 0.1, 0.7, 0.1]
    background: [0.25, 0.25, 0.25, 0.25]
length: 2
count: 2
strands: both
evaluations: 16
seed: 7
min_distance: 0.5
"""


def _write_runtime_equivalent_wheel(path: Path) -> None:
    package_root = Path(motif_balance.__file__).parent
    entries: dict[str, bytes] = {}
    for source in sorted(package_root.rglob("*")):
        if source.is_dir() or "__pycache__" in source.parts or source.suffix == ".pyc":
            continue
        entries[f"motif_balance/{source.relative_to(package_root).as_posix()}"] = (
            source.read_bytes()
        )
    dist_info = "motif_balance-0.3.0a1.dist-info/"
    entries[f"{dist_info}METADATA"] = (
        b"Metadata-Version: 2.4\nName: motif-balance\nVersion: 0.3.0a1\n"
    )
    entries[f"{dist_info}WHEEL"] = b"Wheel-Version: 1.0\n"
    entries[f"{dist_info}entry_points.txt"] = (
        b"[console_scripts]\nmotif-balance = motif_balance.cli:app\n"
    )
    record = "".join(
        f"{name},sha256={base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b'=').decode()},{len(payload)}\n"
        for name, payload in sorted(entries.items())
    )
    record += f"{dist_info}RECORD,,\n"
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
        archive.writestr(f"{dist_info}RECORD", record)


def _corrupt_stored_wheel_member(path: Path, member_name: str) -> None:
    payload = bytearray(path.read_bytes())
    with zipfile.ZipFile(path) as archive:
        member = archive.getinfo(member_name)
    header = payload[member.header_offset : member.header_offset + 30]
    signature, *_, name_length, extra_length = struct.unpack("<IHHHHHIIIHH", header)
    assert signature == 0x04034B50
    member_start = member.header_offset + 30 + name_length + extra_length
    payload[member_start] ^= 1
    path.write_bytes(payload)


def test_primary_cli_help_exposes_only_the_three_product_journeys() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "design" in result.stdout
    assert "score" in result.stdout
    assert "inspect" in result.stdout
    assert "render-report" not in result.stdout
    assert "integration" not in result.stdout
    assert "prepare" not in result.stdout
    assert "orchestration" not in result.stdout


def test_cli_scores_one_sequence_and_exports_one_candidate_svg(tmp_path: Path) -> None:
    spec = tmp_path / "design.yaml"
    bundle = tmp_path / "result"
    candidate_svg = tmp_path / "candidate.svg"
    spec.write_text(_DESIGN)

    scored = runner.invoke(app, ["score", str(spec), "AG"])
    designed = runner.invoke(app, ["design", str(spec), "--out", str(bundle)])
    rendered = runner.invoke(
        app,
        [
            "inspect",
            str(bundle),
            "--format",
            "svg",
            "--view",
            "candidate",
            "--candidate",
            "2",
            "--out",
            str(candidate_svg),
        ],
    )

    assert scored.exit_code == 0
    assert "balance_score=" in scored.stdout
    assert designed.exit_code == 0
    assert rendered.exit_code == 0
    assert b'id="candidate-realization-view"' in candidate_svg.read_bytes()


def test_cli_check_compiles_without_search_or_output(tmp_path: Path) -> None:
    spec = tmp_path / "design.yaml"
    spec.write_text(_DESIGN)

    result = runner.invoke(app, ["design", str(spec), "--check"])

    assert result.exit_code == 0
    assert result.stdout.startswith("valid problem-")
    assert "motifs=2" in result.stdout
    assert "length=2" in result.stdout
    assert "count=2" in result.stdout
    assert "evaluations=16" in result.stdout
    assert "search=exhaustive" in result.stdout
    assert {path.name for path in tmp_path.iterdir()} == {"design.yaml"}


def test_cli_design_writes_verified_bundle(tmp_path: Path) -> None:
    spec = tmp_path / "design.yaml"
    output = tmp_path / "result"
    spec.write_text(_DESIGN)

    result = runner.invoke(app, ["design", str(spec), "--out", str(output)])

    assert result.exit_code == 0
    assert result.stdout.startswith("complete bundle-")
    assert (output / "manifest.json").is_file()


def test_cli_design_rejects_a_dangling_output_symlink_without_a_traceback(
    tmp_path: Path,
) -> None:
    spec = tmp_path / "design.yaml"
    output = tmp_path / "result"
    spec.write_text(_DESIGN)
    output.symlink_to(tmp_path / "missing", target_is_directory=True)

    result = runner.invoke(app, ["design", str(spec), "--out", str(output)])

    assert result.exit_code == 2
    assert "error artifact_error:" in result.stderr
    assert "already exists or is unsafe: 'result'" in result.stderr
    assert "Traceback" not in result.stderr
    assert str(tmp_path) not in result.stderr


def test_cli_design_requires_output_when_not_checking(tmp_path: Path) -> None:
    spec = tmp_path / "design.yaml"
    spec.write_text(_DESIGN)

    result = runner.invoke(app, ["design", str(spec)])

    assert result.exit_code == 2
    assert "error invalid_design:" in result.stderr
    assert "field: out" in result.stderr


def test_cli_rejects_unknown_scientific_fields(tmp_path: Path) -> None:
    spec = tmp_path / "design.yaml"
    spec.write_text(_DESIGN + "objective: soft-min\n")

    result = runner.invoke(app, ["design", str(spec), "--check"])

    assert result.exit_code == 2
    assert "error invalid_design:" in result.stderr
    assert "field: objective" in result.stderr
    assert "hint:" in result.stderr
    assert "extra_forbidden" not in result.stderr
    assert "pydantic.dev" not in result.stderr


def test_cli_rejects_duplicate_and_boolean_scientific_values(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text(_DESIGN + "length: 3\n")
    boolean = tmp_path / "boolean.yaml"
    boolean.write_text(_DESIGN.replace("count: 2", "count: true"))

    duplicate_result = runner.invoke(app, ["design", str(duplicate), "--check"])
    boolean_result = runner.invoke(app, ["design", str(boolean), "--check"])

    assert duplicate_result.exit_code == 2
    assert "duplicate key 'length'" in duplicate_result.stderr
    assert boolean_result.exit_code == 2
    assert "boolean values are not valid" in boolean_result.stderr


def test_cli_inspection_verifies_and_deprecated_report_alias_uses_same_html(
    tmp_path: Path,
) -> None:
    spec = tmp_path / "design.yaml"
    bundle = tmp_path / "result"
    regenerated = tmp_path / "review.html"
    direct = tmp_path / "direct.html"
    spec.write_text(_DESIGN)
    assert runner.invoke(app, ["design", str(spec), "--out", str(bundle)]).exit_code == 0

    inspected = runner.invoke(app, ["inspect", str(bundle)])
    rendered = runner.invoke(
        app,
        ["render-report", str(bundle), "--out", str(regenerated)],
    )
    direct_render = runner.invoke(
        app,
        ["inspect", str(bundle), "--format", "html", "--out", str(direct)],
    )

    assert inspected.exit_code == 0
    assert "Artifact integrity: self consistent" in inspected.stdout
    assert rendered.exit_code == 0
    assert "deprecated" in rendered.stderr.lower()
    assert direct_render.exit_code == 0
    assert regenerated.read_bytes() == direct.read_bytes()


def test_cli_inspects_and_catalogs_explicit_bundle_references(tmp_path: Path) -> None:
    spec = tmp_path / "design.yaml"
    bundle = tmp_path / "result"
    review = tmp_path / "review.html"
    catalog = tmp_path / "catalog.json"
    catalog_review = tmp_path / "catalog.html"
    spec.write_text(_DESIGN)
    assert runner.invoke(app, ["design", str(spec), "--out", str(bundle)]).exit_code == 0

    inspected = runner.invoke(app, ["inspect", str(bundle)])
    rendered = runner.invoke(
        app,
        [
            "inspect",
            str(bundle),
            "--format",
            "html",
            "--out",
            str(review),
        ],
    )
    indexed = runner.invoke(
        app,
        [
            "integration",
            "catalog",
            "--entry",
            f"pairwise=bundle:{bundle}",
            "--out",
            str(catalog),
        ],
    )
    rendered_catalog = runner.invoke(
        app,
        [
            "integration",
            "catalog",
            "--entry",
            f"pairwise=bundle:{bundle}",
            "--format",
            "html",
            "--out",
            str(catalog_review),
        ],
    )

    assert inspected.exit_code == 0
    assert "Portfolio delivery: complete" in inspected.stdout
    assert "Artifact integrity: self consistent" in inspected.stdout
    assert "Search completion: exhaustive" in inspected.stdout
    assert rendered.exit_code == 0
    assert "Motif Balance result review" in review.read_text()
    assert indexed.exit_code == 0
    payload = json.loads(catalog.read_text())
    assert payload["schema_version"] == "motif-balance.result-catalog/v2"
    assert payload["entries"][0]["entry_id"] == "pairwise"
    assert rendered_catalog.exit_code == 0
    assert "does not rank" in catalog_review.read_text()


def test_cli_inspection_refuses_existing_output(tmp_path: Path) -> None:
    spec = tmp_path / "design.yaml"
    bundle = tmp_path / "result"
    out = tmp_path / "inspection.json"
    spec.write_text(_DESIGN)
    out.write_text("keep")
    assert runner.invoke(app, ["design", str(spec), "--out", str(bundle)]).exit_code == 0

    result = runner.invoke(
        app,
        [
            "inspect",
            str(bundle),
            "--format",
            "json",
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 2
    assert "Refusing to replace existing inspection output" in result.stderr
    assert out.read_text() == "keep"


def test_cli_inspection_refuses_output_inside_the_subject(tmp_path: Path) -> None:
    spec = tmp_path / "design.yaml"
    bundle = tmp_path / "result"
    spec.write_text(_DESIGN)
    assert runner.invoke(app, ["design", str(spec), "--out", str(bundle)]).exit_code == 0

    inspected = runner.invoke(
        app,
        [
            "inspect",
            str(bundle),
            "--format",
            "html",
            "--out",
            str(bundle / "inspection.html"),
        ],
    )
    cataloged = runner.invoke(
        app,
        [
            "integration",
            "catalog",
            "--entry",
            f"pairwise=bundle:{bundle}",
            "--out",
            str(bundle / "catalog.json"),
        ],
    )

    assert inspected.exit_code == 2
    assert cataloged.exit_code == 2
    assert "outside every inspected result root" in inspected.stderr
    assert "outside every inspected result root" in cataloged.stderr
    assert not (bundle / "inspection.html").exists()
    assert not (bundle / "catalog.json").exists()


def test_cli_reports_an_unsupported_manifest_as_an_artifact_error(tmp_path: Path) -> None:
    spec = tmp_path / "design.yaml"
    bundle = tmp_path / "result"
    spec.write_text(_DESIGN)
    assert runner.invoke(app, ["design", str(spec), "--out", str(bundle)]).exit_code == 0
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["schema_version"] = "run-manifest/v1"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    verified = runner.invoke(app, ["inspect", str(bundle)])

    assert verified.exit_code == 2
    assert "error artifact_error:" in verified.stderr
    assert "invalid_design" not in verified.stderr


def test_cli_convert_motif_requires_explicit_scientific_parameters(tmp_path: Path) -> None:
    source = tmp_path / "source.jaspar"
    output = tmp_path / "motif.yaml"
    source.write_text(">MA0001.1 synthetic\nA [ 8 0 ]\nC [ 0 8 ]\nG [ 0 0 ]\nT [ 0 0 ]\n")

    result = runner.invoke(
        app,
        [
            "motif",
            "prepare",
            str(source),
            "--motif-id",
            "synthetic",
            "--background",
            "0.25,0.25,0.25,0.25",
            "--prior-weight",
            "0.1",
            "--out",
            str(output),
        ],
    )

    assert result.exit_code == 0
    payload = output.read_text()
    assert "method: jaspar_counts_to_probabilities_v1" in payload
    assert "prior_weight: 0.1" in payload
    assert "source_digest:" in payload
    assert "canonical_file_digest:" not in payload
    assert "canonical_file_name:" not in payload


def test_cli_convert_motif_reports_invalid_background_as_a_motif_error(tmp_path: Path) -> None:
    source = tmp_path / "source.jaspar"
    source.write_text(">MA0001.1 synthetic\nA [ 8 ]\nC [ 0 ]\nG [ 0 ]\nT [ 0 ]\n")

    result = runner.invoke(
        app,
        [
            "motif",
            "prepare",
            str(source),
            "--motif-id",
            "synthetic",
            "--background",
            "not,numbers",
            "--prior-weight",
            "0.1",
            "--out",
            str(tmp_path / "motif.yaml"),
        ],
    )

    assert result.exit_code == 2
    assert "error invalid_motif:" in result.stderr
    assert "field: background" in result.stderr


def test_cli_convert_motif_sanitizes_an_unwritable_destination(tmp_path: Path) -> None:
    source = tmp_path / "source.jaspar"
    source.write_text(">MA0001.1 synthetic\nA [ 8 ]\nC [ 0 ]\nG [ 0 ]\nT [ 0 ]\n")

    result = runner.invoke(
        app,
        [
            "motif",
            "prepare",
            str(source),
            "--motif-id",
            "synthetic",
            "--background",
            "0.25,0.25,0.25,0.25",
            "--prior-weight",
            "0.1",
            "--out",
            str(tmp_path / "missing" / "motif.yaml"),
        ],
    )

    assert result.exit_code == 2
    assert "error artifact_error:" in result.stderr
    assert "Unable to write motif model 'motif.yaml'." in result.stderr
    assert "Traceback" not in result.stderr
    assert str(tmp_path) not in result.stderr


def test_cli_executes_and_verifies_an_atomic_execution_workspace(tmp_path: Path) -> None:
    spec = tmp_path / "design.yaml"
    workspace = tmp_path / "execution"
    release = tmp_path / "motif_balance-0.3.0a1-py3-none-any.whl"
    spec.write_text(_DESIGN)
    _write_runtime_equivalent_wheel(release)

    executed = runner.invoke(
        app,
        [
            "orchestration",
            "execute",
            str(spec),
            "--producer-revision",
            "a" * 40,
            "--release-artifact",
            str(release),
            "--out",
            str(workspace),
        ],
    )

    assert executed.exit_code == 0
    index = json.loads((workspace / "execution-workspace.json").read_text())
    receipt = json.loads((workspace / "execution-receipt.json").read_text())
    assert {item.name for item in workspace.iterdir()} == {
        "execution-receipt.json",
        "execution-workspace.json",
        "inputs",
        "bundle",
    }
    assert receipt["execution_status"] == "completed"
    assert receipt["bundle_id"] == index["bundle"]["bundle_id"]

    verified = runner.invoke(
        app,
        [
            "inspect",
            str(workspace),
            "--source",
            "execution",
            "--expected-workspace-id",
            index["workspace_id"],
            "--expected-receipt-sha256",
            index["receipt"]["sha256"],
            "--expected-release-sha256",
            hashlib.sha256(release.read_bytes()).hexdigest(),
            "--expected-producer-revision",
            "a" * 40,
        ],
    )

    assert verified.exit_code == 0
    assert index["workspace_id"] in verified.stdout
    assert "Artifact integrity: externally verified" in verified.stdout


def test_cli_rejects_a_wheel_with_a_corrupt_member_without_a_traceback(
    tmp_path: Path,
) -> None:
    spec = tmp_path / "design.yaml"
    workspace = tmp_path / "execution"
    release = tmp_path / "motif_balance-0.3.0a1-py3-none-any.whl"
    spec.write_text(_DESIGN)
    _write_runtime_equivalent_wheel(release)
    _corrupt_stored_wheel_member(release, "motif_balance/__init__.py")

    result = runner.invoke(
        app,
        [
            "orchestration",
            "execute",
            str(spec),
            "--producer-revision",
            "a" * 40,
            "--release-artifact",
            str(release),
            "--out",
            str(workspace),
        ],
    )

    assert result.exit_code == 2
    assert "error artifact_error:" in result.stderr
    assert "unreadable wheel members" in result.stderr
    assert "Traceback" not in result.stderr
    assert str(tmp_path) not in result.stderr

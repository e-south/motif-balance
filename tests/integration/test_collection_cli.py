"""Collections are a usable installed command over a verified saved search."""

import json

from typer.testing import CliRunner

from motif_balance import DesignSpec, design
from motif_balance.cli import app


def bundle(tmp_path, pairwise_spec):
    payload = pairwise_spec.model_dump(mode="python")
    payload.update(length=4, count=1, evaluations=256, min_distance=None, strands="forward")
    result = design(DesignSpec.model_validate(payload))
    path = tmp_path / "result"
    result.write(path)
    return path, result.manifest.bundle_id


def test_collection_cli_returns_full_profile_and_explicit_partial_status(tmp_path, pairwise_spec):
    path, identity = bundle(tmp_path, pairwise_spec)
    run = CliRunner().invoke(
        app,
        [
            "collect",
            str(path),
            "--expected-bundle-id",
            identity,
            "--count",
            "100",
            "--format",
            "json",
        ],
    )
    assert run.exit_code == 0, run.output
    output = json.loads(run.stdout)
    assert output["ranking"]["grouping"] == "interval_topology"
    collection = output["collection"]
    assert collection["status"] == "insufficient_retained_architectures"
    assert 2 < collection["delivered_count"] < collection["requested_count"] == 100
    assert len(output["ranking"]["prefixes"]) == collection["available_count"]


def test_collection_cli_requires_a_verified_identity_and_preserves_outputs(tmp_path, pairwise_spec):
    path, identity = bundle(tmp_path, pairwise_spec)
    out = tmp_path / "review.json"
    out.write_text("keep")
    args = [
        "collect",
        str(path),
        "--expected-bundle-id",
        identity,
        "--count",
        "3",
        "--out",
        str(out),
    ]
    run = CliRunner().invoke(app, args)
    assert run.exit_code != 0 and "replace" in run.output
    assert out.read_text() == "keep"
    bad = CliRunner().invoke(
        app, ["collect", str(path), "--expected-bundle-id", "bundle-" + "0" * 16, "--count", "3"]
    )
    assert bad.exit_code != 0

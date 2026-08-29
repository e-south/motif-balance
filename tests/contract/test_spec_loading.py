from __future__ import annotations

from pathlib import Path

import pytest

from motif_balance.errors import InvalidDesign, InvalidMotif
from motif_balance.formats import read_motif
from motif_balance.formats.design import load_design_spec


def test_load_spec_resolves_relative_motif_file(tmp_path: Path) -> None:
    (tmp_path / "motif.yaml").write_text(
        """motif_id: fixture
probabilities:
  - [0.7, 0.1, 0.1, 0.1]
background: [0.25, 0.25, 0.25, 0.25]
"""
    )
    design_path = tmp_path / "design.yaml"
    design_path.write_text(
        """motifs:
  fixture: motif.yaml
length: 1
count: 1
evaluations: 1
seed: 0
"""
    )

    spec = load_design_spec(design_path)
    assert spec.motifs[0].source_name == "motif.yaml"


def test_load_spec_resolves_contained_avoider_file_and_ceiling(tmp_path: Path) -> None:
    for name, motif_id, row in (
        ("target.yaml", "target", "[0.7, 0.1, 0.1, 0.1]"),
        ("avoider.yaml", "avoider", "[0.1, 0.7, 0.1, 0.1]"),
    ):
        (tmp_path / name).write_text(
            f"motif_id: {motif_id}\nprobabilities:\n  - {row}\n"
            "background: [0.25, 0.25, 0.25, 0.25]\n"
        )
    design_path = tmp_path / "design.yaml"
    design_path.write_text(
        "schema_version: design-spec/v2\n"
        "motifs:\n  target: target.yaml\n"
        "avoiders:\n"
        "  avoider:\n"
        "    motif: avoider.yaml\n"
        "    score_ceiling: 0.2\n"
        "length: 1\ncount: 1\nevaluations: 4\nseed: 0\n"
    )

    spec = load_design_spec(design_path)

    assert spec.avoiders[0].motif.source_name == "avoider.yaml"
    assert spec.avoiders[0].score_ceiling == 0.2


def test_load_spec_applies_the_same_containment_boundary_to_avoiders(tmp_path: Path) -> None:
    root = tmp_path / "specification"
    root.mkdir()
    private = tmp_path / "private.yaml"
    private.write_text(
        "motif_id: avoider\nprobabilities:\n  - [0.7, 0.1, 0.1, 0.1]\n"
        "background: [0.25, 0.25, 0.25, 0.25]\n"
    )
    (root / "link.yaml").symlink_to(private)
    target = (
        "motif_id: target\nprobabilities:\n  - [0.7, 0.1, 0.1, 0.1]\n"
        "background: [0.25, 0.25, 0.25, 0.25]\n"
    )
    (root / "target.yaml").write_text(target)

    for index, reference in enumerate(("../private.yaml", "link.yaml")):
        design_path = root / f"avoidance-{index}.yaml"
        design_path.write_text(
            "motifs:\n  target: target.yaml\n"
            f"avoiders:\n  avoider:\n    motif: {reference}\n    score_ceiling: 0.2\n"
            "length: 1\ncount: 1\nevaluations: 4\nseed: 0\n"
        )
        with pytest.raises(InvalidDesign, match=r"contained|symbolic"):
            load_design_spec(design_path)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("- not\n- a\n- mapping\n", "one mapping"),
        ("length: 2\ncount: 1\nevaluations: 1\nseed: 0\n", "name-to-model"),
        (
            "motifs:\n  fixture: 4\nlength: 2\ncount: 1\nevaluations: 1\nseed: 0\n",
            "path or model",
        ),
    ],
)
def test_load_spec_rejects_malformed_surfaces(
    tmp_path: Path,
    content: str,
    message: str,
) -> None:
    path = tmp_path / "design.yaml"
    path.write_text(content)
    with pytest.raises(InvalidDesign, match=message):
        load_design_spec(path)


def test_load_spec_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(InvalidDesign, match="Unable to read"):
        load_design_spec(tmp_path / "missing.yaml")


def test_structured_inputs_reject_duplicate_keys(tmp_path: Path) -> None:
    design_path = tmp_path / "design.yaml"
    design_path.write_text(
        "motifs:\n"
        "  fixture:\n"
        "    probabilities:\n"
        "      - [0.7, 0.1, 0.1, 0.1]\n"
        "    background: [0.25, 0.25, 0.25, 0.25]\n"
        "length: 1\n"
        "length: 2\n"
        "count: 1\n"
        "evaluations: 1\n"
        "seed: 0\n"
    )
    with pytest.raises(InvalidDesign, match="duplicate key 'length'"):
        load_design_spec(design_path)

    motif_path = tmp_path / "motif.yaml"
    motif_path.write_text(
        "motif_id: fixture\n"
        "motif_id: substituted\n"
        "probabilities:\n"
        "  - [0.7, 0.1, 0.1, 0.1]\n"
        "background: [0.25, 0.25, 0.25, 0.25]\n"
    )
    with pytest.raises(InvalidMotif, match="duplicate key 'motif_id'"):
        read_motif(motif_path)

    motif_json_path = tmp_path / "motif.json"
    motif_json_path.write_text(
        '{"motif_id":"fixture","motif_id":"substituted",'
        '"probabilities":[[0.7,0.1,0.1,0.1]],'
        '"background":[0.25,0.25,0.25,0.25]}'
    )
    with pytest.raises(InvalidMotif, match="duplicate key 'motif_id'"):
        read_motif(motif_json_path)


def test_load_spec_rejects_traversal_and_symlink_motif_references(tmp_path: Path) -> None:
    specification_root = tmp_path / "specification"
    specification_root.mkdir()
    private = tmp_path / "private.yaml"
    private.write_text(
        "motif_id: leaked\n"
        "probabilities:\n  - [0.7, 0.1, 0.1, 0.1]\n"
        "background: [0.25, 0.25, 0.25, 0.25]\n"
    )
    (specification_root / "link.yaml").symlink_to(private)

    for index, reference in enumerate(("../private.yaml", "link.yaml")):
        design_path = specification_root / f"design-{index}.yaml"
        design_path.write_text(
            f"motifs:\n  leaked: {reference}\nlength: 1\ncount: 1\nevaluations: 1\nseed: 0\n"
        )
        with pytest.raises(InvalidDesign, match=r"contained|symbolic"):
            load_design_spec(design_path)


def test_load_spec_and_motif_loader_enforce_byte_bounds(tmp_path: Path) -> None:
    design_path = tmp_path / "oversized-design.yaml"
    design_path.write_bytes(b" " * 1_000_001)
    with pytest.raises(InvalidDesign, match="byte limit"):
        load_design_spec(design_path)

    motif_path = tmp_path / "oversized-motif.yaml"
    motif_path.write_bytes(b" " * 1_000_001)
    design_path = tmp_path / "design.yaml"
    design_path.write_text(
        "motifs:\n  fixture: oversized-motif.yaml\nlength: 1\ncount: 1\nevaluations: 1\nseed: 0\n"
    )
    with pytest.raises(InvalidDesign, match="byte limit"):
        load_design_spec(design_path)

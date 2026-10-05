"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_motif_display.py

Check the compact motif display without changing scientific records.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import pytest

from motif_balance import MotifModel


def test_print_motif_labels_background_and_each_small_model_position(
    capsys: pytest.CaptureFixture[str],
) -> None:
    motif = MotifModel(
        motif_id="two_positions",
        probabilities=((0.7, 0.1, 0.1, 0.1), (0.1, 0.2, 0.3, 0.4)),
        background=(0.3, 0.2, 0.2, 0.3),
    )

    print(motif)

    assert capsys.readouterr().out == (
        "two_positions (2 positions)\n"
        "Background (A C G T): 0.3 0.2 0.2 0.3\n"
        "Nucleotide probabilities\n"
        "Position         A         C         G         T\n"
        "       1       0.7       0.1       0.1       0.1\n"
        "       2       0.1       0.2       0.3       0.4\n"
    )


@pytest.mark.parametrize(
    ("width", "positions", "omitted"),
    (
        (8, [1, 2, 3, 4, 5, 6, 7, 8], None),
        (9, [1, 2, 3, 8, 9], 4),
        (1000, [1, 2, 3, 999, 1000], 995),
    ),
)
def test_wide_display_keeps_labelled_head_and_tail_with_explicit_omission(
    width: int, positions: list[int], omitted: int | None
) -> None:
    motif = MotifModel(
        motif_id="wide",
        probabilities=((0.7, 0.1, 0.1, 0.1),) * (width - 2)
        + ((0.1, 0.7, 0.1, 0.1), (0.1, 0.1, 0.7, 0.1)),
        background=(0.25, 0.25, 0.25, 0.25),
    )

    text = str(motif)
    rows = [line.split() for line in text.splitlines() if line.split()[0].isdigit()]

    assert [int(row[0]) for row in rows] == positions
    assert rows[-2][1:] == ["0.1", "0.7", "0.1", "0.1"]
    assert rows[-1][1:] == ["0.1", "0.1", "0.7", "0.1"]
    if omitted is None:
        assert "omitted" not in text
    else:
        assert f"... {omitted} positions omitted ..." in text
        header = next(line for line in text.splitlines() if line.startswith("Position"))
        omission = next(line for line in text.splitlines() if "omitted" in line)
        heading_center = (header.index("A") + header.rindex("T")) / 2
        omission_center = (len(omission) - len(omission.lstrip()) + len(omission) - 1) / 2
        assert abs(omission_center - heading_center) <= 0.5
        assert omission == omission.rstrip()
        assert len(text) < 600


def test_one_position_display_keeps_tiny_positive_probabilities_visible() -> None:
    motif = MotifModel(
        motif_id="small_probability",
        probabilities=((5e-324, 0.25, 0.25, 0.5),),
        background=(5e-324, 0.25, 0.25, 0.5),
    )

    lines = str(motif).splitlines()

    assert lines[0] == "small_probability (1 position)"
    assert lines[1] == "Background (A C G T): 4.94e-324 0.25 0.25 0.5"
    assert lines[-1] == "       1 4.94e-324      0.25      0.25       0.5"
    assert len(lines) == 5


def test_preview_rounding_preserves_model_identity_and_full_serialization() -> None:
    motif = MotifModel(
        motif_id="precision",
        probabilities=((0.123456789, 0.2, 0.3, 0.376543211),),
        background=(0.25, 0.25, 0.25, 0.25),
        source_name="source.json",
        source_digest="a" * 64,
    )
    before = motif.model_dump_json(), motif.model_digest, hash(motif), repr(motif)

    preview = str(motif)

    assert "0.123" in preview and "0.377" in preview
    assert "0.123456789" not in preview and "source.json" not in preview
    assert (motif.model_dump_json(), motif.model_digest, hash(motif), repr(motif)) == before
    assert motif.probabilities[0] == (0.123456789, 0.2, 0.3, 0.376543211)
    assert "0.123456789" in motif.model_dump_json()

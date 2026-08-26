from __future__ import annotations

from pathlib import Path

import pytest

from motif_balance import read_motif
from motif_balance.errors import InvalidMotif


def test_read_meme_preserves_source_and_canonical_model_identity(tmp_path: Path) -> None:
    source = tmp_path / "pair.meme"
    source.write_text(
        """MEME version 5

ALPHABET= ACGT

Background letter frequencies
A 0.25 C 0.25 G 0.25 T 0.25

MOTIF motif_a
letter-probability matrix: alength= 4 w= 2 nsites= 4 E= 0
0.7 0.1 0.1 0.1
0.1 0.7 0.1 0.1

MOTIF motif_b
letter-probability matrix: alength= 4 w= 2 nsites= 4 E= 0
0.1 0.1 0.7 0.1
0.1 0.1 0.1 0.7
"""
    )

    first = read_motif(source, motif_id="motif_a")
    second = read_motif(source, motif_id="motif_b")

    assert first.motif_id == "motif_a"
    assert second.motif_id == "motif_b"
    assert first.source_digest == second.source_digest
    assert first.source_name == "pair.meme"
    assert first.model_digest != second.model_digest


def test_read_motif_refuses_zero_probability_without_explicit_conversion(tmp_path: Path) -> None:
    source = tmp_path / "invalid.yaml"
    source.write_text(
        """motif_id: invalid
probabilities:
  - [0.7, 0.1, 0.2, 0.0]
background: [0.25, 0.25, 0.25, 0.25]
"""
    )

    with pytest.raises(InvalidMotif, match="positive"):
        read_motif(source)

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from motif_balance import read_motif
from motif_balance.errors import InvalidMotif
from motif_balance.formats import convert_jaspar


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


def test_explicit_jaspar_conversion_records_the_conversion_semantics(tmp_path: Path) -> None:
    source = tmp_path / "counts.jaspar"
    source.write_text(">MA0001.1 synthetic\nA [ 8 0 ]\nC [ 0 8 ]\nG [ 0 0 ]\nT [ 0 0 ]\n")

    motif = convert_jaspar(
        source,
        motif_id="synthetic",
        background=(0.25, 0.25, 0.25, 0.25),
        prior_weight=0.1,
    )

    assert motif.conversion is not None
    assert motif.conversion.method == "jaspar_counts_to_probabilities_v1"
    assert motif.conversion.source_motif_id == "MA0001.1"
    assert motif.conversion.prior_weight == 0.1
    assert motif.canonical_file_digest is None
    assert motif.canonical_file_name is None
    assert motif.probabilities[0][0] == pytest.approx((1.0 + 0.1 * 0.25) / 1.1)
    assert motif.probabilities[0][1] == pytest.approx((0.0 + 0.1 * 0.25) / 1.1)

    canonical = tmp_path / "canonical.yaml"
    canonical.write_text(
        yaml.safe_dump(motif.model_dump(mode="json", exclude_none=True), sort_keys=False)
    )
    reloaded = read_motif(canonical)

    assert reloaded.source_digest == hashlib.sha256(source.read_bytes()).hexdigest()
    assert reloaded.source_name == "counts.jaspar"
    assert reloaded.canonical_file_digest == hashlib.sha256(canonical.read_bytes()).hexdigest()
    assert reloaded.canonical_file_name == "canonical.yaml"


@pytest.mark.parametrize(
    ("payload", "requested_id", "message"),
    [
        ("MOTIF a\n", None, "background frequencies"),
        (
            "Background letter frequencies\nA 0.25 C 0.25 G 0.25 T 0.25\n",
            None,
            "no MOTIF record",
        ),
        (
            "Background letter frequencies\nA 0.25 C 0.25 G 0.25 T 0.25\nMOTIF a\n",
            "missing",
            "no motif named",
        ),
        (
            "Background letter frequencies\nA 0.25 C 0.25 G 0.25 T 0.25\nMOTIF a\n",
            "a",
            "lacks a probability matrix",
        ),
        (
            "Background letter frequencies\nA 0.25 C 0.25 G 0.25 T 0.25\n"
            "MOTIF a\nletter-probability matrix: alength= 4 w= 2\n0.25 0.25 0.25 0.25\n",
            "a",
            "declares width 2",
        ),
    ],
)
def test_read_meme_rejects_ambiguous_or_incomplete_models(
    tmp_path: Path,
    payload: str,
    requested_id: str | None,
    message: str,
) -> None:
    source = tmp_path / "invalid.meme"
    source.write_text(payload)

    with pytest.raises(InvalidMotif, match=message):
        read_motif(source, motif_id=requested_id)


@pytest.mark.parametrize(
    ("name", "payload", "message"),
    [
        ("invalid.json", b"{", "Unable to read motif file"),
        ("list.yaml", b"- not\n- an\n- object\n", "must contain one object"),
    ],
)
def test_read_structured_motif_requires_one_valid_object(
    tmp_path: Path,
    name: str,
    payload: bytes,
    message: str,
) -> None:
    source = tmp_path / name
    source.write_bytes(payload)

    with pytest.raises(InvalidMotif, match=message):
        read_motif(source)


def test_read_meme_rejects_invalid_utf8(tmp_path: Path) -> None:
    source = tmp_path / "invalid.meme"
    source.write_bytes(b"\xff\xfe")

    with pytest.raises(InvalidMotif, match="UTF-8"):
        read_motif(source)


def test_read_motif_rejects_a_conflicting_requested_identity(tmp_path: Path) -> None:
    source = tmp_path / "motif.yaml"
    source.write_text(
        "motif_id: first\nprobabilities: [[0.25, 0.25, 0.25, 0.25]]\n"
        "background: [0.25, 0.25, 0.25, 0.25]\n"
    )

    with pytest.raises(InvalidMotif, match="does not match file id"):
        read_motif(source, motif_id="second")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("A [ 1 ]\nC [ 1 ]\nG [ 1 ]\nT [ 1 ]\n", "explicit.*header"),
        (">x\nA [ 1 ]\nA [ 1 ]\nC [ 1 ]\nG [ 1 ]\nT [ 1 ]\n", "repeats"),
        (">x\nA [ bad ]\nC [ 1 ]\nG [ 1 ]\nT [ 1 ]\n", "nonnumeric"),
        (">x\nA [ -1 ]\nC [ 1 ]\nG [ 1 ]\nT [ 1 ]\n", "finite nonnegative"),
        (">x\nA [ 1 ]\nC [ 1 ]\nG [ 1 ]\n", "missing count rows"),
        (">x\nA [ 1 2 ]\nC [ 1 ]\nG [ 1 ]\nT [ 1 ]\n", "equal widths"),
        (">x\nA [ 0 ]\nC [ 0 ]\nG [ 0 ]\nT [ 0 ]\n", "zero total"),
    ],
)
def test_jaspar_conversion_rejects_malformed_count_matrices(
    tmp_path: Path,
    payload: str,
    message: str,
) -> None:
    source = tmp_path / "invalid.jaspar"
    source.write_text(payload)

    with pytest.raises(InvalidMotif, match=message):
        convert_jaspar(
            source,
            motif_id="canonical",
            background=(0.25, 0.25, 0.25, 0.25),
            prior_weight=0.1,
        )


def test_jaspar_conversion_rejects_invalid_parameters_and_encoding(tmp_path: Path) -> None:
    source = tmp_path / "counts.jaspar"
    source.write_text(">x\nA [ 1 ]\nC [ 1 ]\nG [ 1 ]\nT [ 1 ]\n")
    with pytest.raises(InvalidMotif, match="conversion parameters"):
        convert_jaspar(
            source,
            motif_id="canonical",
            background=(0.25, 0.25, 0.25, 0.25),
            prior_weight=-1.0,
        )

    binary = tmp_path / "binary.jaspar"
    binary.write_bytes(b"\xff\xfe")
    with pytest.raises(InvalidMotif, match="UTF-8"):
        convert_jaspar(
            binary,
            motif_id="canonical",
            background=(0.25, 0.25, 0.25, 0.25),
            prior_weight=0.1,
        )


def test_motif_readers_refuse_symbolic_links(tmp_path: Path) -> None:
    target = tmp_path / "target.yaml"
    target.write_text(
        "motif_id: motif\nprobabilities: [[0.25, 0.25, 0.25, 0.25]]\n"
        "background: [0.25, 0.25, 0.25, 0.25]\n"
    )
    link = tmp_path / "link.yaml"
    link.symlink_to(target)

    with pytest.raises(InvalidMotif, match="symbolic-link"):
        read_motif(link)
    with pytest.raises(InvalidMotif, match="symbolic-link"):
        convert_jaspar(
            link,
            motif_id="canonical",
            background=(0.25, 0.25, 0.25, 0.25),
            prior_weight=0.1,
        )

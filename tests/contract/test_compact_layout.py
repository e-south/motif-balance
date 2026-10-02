"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_compact_layout.py

Keep compact molecular drawings aligned without changing strand or logo information.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from xml.etree import ElementTree as ET

import pytest

from motif_balance import Candidate, DesignSpec, MotifModel, MotifSpecification, score
from motif_balance.inspection import inspect_candidate
from motif_balance.inspection.render import render_candidate_svg
from motif_balance.model import candidate_id_for_sequence


def _drawing():
    models = tuple(
        MotifModel(
            motif_id=name,
            background=(0.25,) * 4,
            probabilities=tuple(tuple(0.7 if b == base else 0.1 for b in "ACGT") for base in word),
        )
        for name, word in (("ArgR", "AC"), ("Cra", "GT"))
    )
    spec = DesignSpec(
        specifications=tuple(MotifSpecification(motif=m, direction="seek") for m in models),
        length=2,
        count=1,
        evaluations=1,
        seed=1,
    )
    result = score("AC", spec)
    candidate = Candidate(
        candidate_id=candidate_id_for_sequence("AC"), rank=1, **result.model_dump()
    )
    return ET.fromstring(render_candidate_svg(inspect_candidate(candidate, spec), compact=True))


def test_compact_windows_have_equal_gaps_to_their_strands():
    root = _drawing()
    ns = "{http://www.w3.org/2000/svg}"
    upper = root.find(".//*[@id='primary-sequence']")
    lower = root.find(".//*[@id='complementary-sequence']")
    upper_y = float(upper.find(f"{ns}text").get("y"))
    lower_y = float(lower.find(f"{ns}text").get("y"))
    windows = {
        n.get("data-strand"): n.find(f"{ns}rect")
        for n in root.findall(".//*[@class='motif-match']")
    }
    # Window letters and duplex letters share a font. Compare baseline offsets.
    assert upper_y - (float(windows["+"].get("y")) + 15) == pytest.approx(
        float(windows["-"].get("y")) + 15 - lower_y
    )
    for logo in root.findall(".//*[@class='motif-information-logo']"):
        baseline = logo.find(".//*[@class='information-logo-baseline']")
        window = windows[logo.get("data-match-strand")]
        y = float(baseline.get("y1"))
        edge = float(window.get("y")) + (20 if logo.get("data-match-strand") == "-" else 0)
        assert abs(edge - y) == 4


def test_compact_card_has_transparent_corners_and_explicit_model_labels():
    root = _drawing()
    ns = "{http://www.w3.org/2000/svg}"
    background = root.find(f"{ns}rect")
    assert float(background.get("rx", "0")) > 0
    labels = ["".join(n.itertext()) for n in root.findall(f".//{ns}text")]
    assert any("ArgR" in t and "q" in t for t in labels)
    assert any("Cra" in t and "q" in t for t in labels)

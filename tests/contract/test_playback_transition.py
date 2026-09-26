"""Display tweening may move glyphs, but cannot invent scored search states."""

from xml.etree import ElementTree as ET

import pytest

from motif_balance.errors import ArtifactError
from motif_balance.playback.transition import blend_svgs

A = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" data-evaluations="8">'
    b'<g data-duplex-layout="fixed"><text>A</text><g data-motif-id="M" data-strand="+">'
    b'<rect x="10" y="20" width="40" height="20"/></g></g></svg>'
)
B = (
    A.replace(b'="8"', b'="16"')
    .replace(b'="+"', b'="-"')
    .replace(b'x="10"', b'x="90"')
    .replace(b'y="20"', b'y="120"')
)


def test_transition_endpoints_and_unscored_midpoint():
    assert blend_svgs(A, B, 0) == A
    assert blend_svgs(A, B, 1) == B
    r = ET.fromstring(blend_svgs(A, B, 0.5))
    assert r.get("data-visual-transition") == "true"
    assert r.get("data-evaluations") == "8"
    transforms = [n.get("transform", "") for n in r.iter()]
    assert any("translate(70 80)" in s and "rotate(90)" in s for s in transforms)
    assert any("rotate(-90)" in s for s in transforms)


@pytest.mark.parametrize("p", [-0.1, 1.1, float("nan"), True])
def test_invalid_transition_fraction(p):
    with pytest.raises(ArtifactError):
        blend_svgs(A, B, p)


def test_transition_keeps_moving_without_braking_at_every_saved_state():
    root = ET.fromstring(blend_svgs(A, B, 0.25))
    transforms = [n.get("transform", "") for n in root.iter()]
    assert any("translate(50 55)" in s and "rotate(45)" in s for s in transforms)
    assert "Transition between recorded states" not in "".join(root.itertext())

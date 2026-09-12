"""Check measured vector outlines, independently of the SVG's information metadata."""

from __future__ import annotations

import math
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from motif_balance import DesignSpec, design
from motif_balance.inspection import inspect_result
from motif_balance.inspection.render import render_candidate_svg


def test_rendered_glyph_heights_encode_model_information(
    tmp_path: Path, pairwise_spec: DesignSpec
) -> None:
    inkscape = shutil.which("inkscape")
    if inkscape is None:
        pytest.skip("Inkscape is required for the external vector-geometry qualification")
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")
    svg = tmp_path / "candidate.svg"
    svg.write_bytes(render_candidate_svg(inspection))
    result = subprocess.run(
        [inkscape, str(svg), "--query-all"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    bounds = {
        fields[0]: tuple(map(float, fields[1:]))
        for line in result.stdout.splitlines()
        if len(fields := line.split(",")) == 5
    }
    ns = "{http://www.w3.org/2000/svg}"
    root = ET.fromstring(svg.read_bytes())
    motifs = {motif.motif_id: motif for motif in inspection.problem.motifs}
    measured = 0
    for logo in root.findall(f".//{ns}g[@class='motif-information-logo']"):
        motif = motifs[logo.attrib["data-motif-id"]]
        for column in logo.findall(f"{ns}g[@class='information-logo-column']"):
            row = motif.probabilities[int(column.attrib["data-motif-position"])]
            information = max(0.0, 2 + sum(p * math.log2(p) for p in row if p))
            for glyph in column.findall(f"{ns}path[@class='information-logo-letter']"):
                probability = row["ACGT".index(glyph.attrib["data-base"])]
                _, _, width, height = bounds[glyph.attrib["id"]]
                assert width == pytest.approx(24 * 0.8, abs=1e-4)
                assert height == pytest.approx(probability * information * 36, abs=1e-4)
                measured += 1
    assert measured > 0

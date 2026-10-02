"""
--------------------------------------------------------------------------------
motif-balance
examples/argr-cra/render_previews.py

Generate the README drawings from the same real request used in its commands.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from motif_balance import design
from motif_balance.alternatives import rank_architectures
from motif_balance.examples import prepare_example
from motif_balance.formats.collection import collection_json, read_collection
from motif_balance.formats.design import load_design_spec
from motif_balance.inspection import inspect_collection, inspect_result
from motif_balance.inspection.render import render_candidate_svg
from motif_balance.inspection.render.collection import render_collection_svg
from motif_balance.inspection.render.png import svg_to_png


def render(out: Path) -> None:
    """Write new images only after checking the design and collection scores."""
    if out.exists():
        raise FileExistsError("Choose a new preview directory")
    with TemporaryDirectory() as temporary:
        root = prepare_example("argr-cra", Path(temporary) / "argr-cra")
        spec = load_design_spec(root / "design.yaml")
        portfolio = design(spec)
        portfolio.write(root / "result")
        review = inspect_result(root / "result", kind="bundle")
        ranking = rank_architectures(
            [item.sequence for item in portfolio.manifest.elites],
            spec,
            grouping="interval_topology",
        )
        report = root / "collection.json"
        report.write_text(
            collection_json(
                ranking, count=2, source_id=portfolio.manifest.bundle_id, anchored=False
            )
        )
        members = inspect_collection(read_collection(report))
        candidate = svg_to_png(render_candidate_svg(review, compact=True))
        arrangements = svg_to_png(render_collection_svg(members))
        out.mkdir()
        (out / "candidate.png").write_bytes(candidate)
        (out / "arrangements.png").write_bytes(arrangements)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Draw the README example in a new directory.")
    parser.add_argument("--out", required=True, type=Path)
    render(parser.parse_args().out)

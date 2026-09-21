"""Generate a recorded Dorsal/Twist/Zelda design and its reusable playback.

Maintainer(s): Eric J. South, Dunlop Lab
"""

import argparse
import hashlib
import json
from pathlib import Path

from motif_balance.api import design_observed
from motif_balance.formats.design import load_design_spec
from motif_balance.formats.motif import convert_jaspar
from motif_balance.model.search_observation import ObservationSpec
from motif_balance.playback import (
    inspect_playback,
    render_playback_html,
    render_playback_media,
    render_playback_svg,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="A new output directory")
    parser.add_argument("--media", action="store_true", help="Also export PNG, GIF and MP4")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    spec = load_design_spec(root / "design.yaml")
    for item, accession in zip(
        spec.specifications, ("MA0022.1", "MA0249.3", "MA1462.2"), strict=True
    ):
        prepared = convert_jaspar(
            root / "source" / f"{accession}.jaspar",
            motif_id=item.motif.motif_id,
            background=(0.25,) * 4,
        )
        if prepared.model_digest != item.motif.model_digest:
            raise ValueError(f"prepared matrix differs from pinned source {accession}")
    args.out.mkdir(parents=True, exist_ok=False)
    portfolio, observation = design_observed(spec, ObservationSpec(max_snapshots=48))
    observed_bytes = observation.model_dump_json().encode()
    (args.out / "observation.json").write_bytes(observed_bytes)
    view = inspect_playback(observation)
    (args.out / "playback.html").write_bytes(render_playback_html(view))
    (args.out / "final-frame.svg").write_bytes(render_playback_svg(view))
    if args.media:
        for extension in ("png", "gif", "mp4"):
            name = "final-frame.png" if extension == "png" else f"playback.{extension}"
            (args.out / name).write_bytes(render_playback_media(view, format_name=extension))
    summary = {
        "inputs": ["MA0022.1", "MA0249.3", "MA1462.2"],
        "engine": observation.engine,
        "seed": spec.seed,
        "evaluations": observation.evaluation_count,
        "snapshots": len(observation.snapshots),
        "first_recorded_balance": view.frames[0].best_balance,
        "final_balance": view.frames[-1].best_balance,
        "sequence": portfolio.candidates[0].sequence,
        "observation_sha256": hashlib.sha256(observed_bytes).hexdigest(),
        "files": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(args.out.iterdir())
            if path.is_file()
        },
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"{len(view.frames)} recorded observations; best balance {summary['final_balance']:.3f}")
    print(args.out / "playback.html")


if __name__ == "__main__":
    main()

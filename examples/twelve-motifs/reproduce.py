"""Repeat the twelve-model example and export a recorded search animation."""

import argparse
import json
import time
from pathlib import Path

from motif_balance.api import design_observed
from motif_balance.constants import PACKAGE_VERSION
from motif_balance.formats.design import load_design_spec
from motif_balance.model.search_observation import ObservationSpec
from motif_balance.playback import (
    inspect_playback,
    render_playback_html,
    render_playback_media,
    render_playback_svg,
)


def verify_replay_version(expected: dict) -> None:
    if expected.get("replay_package_version") != PACKAGE_VERSION:
        raise ValueError("Example replay package differs from the declared version")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="A new output directory")
    parser.add_argument("--media", action="store_true", help="Also export an MP4, GIF, and PNG")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    expected = json.loads((root / "expected.json").read_text())
    verify_replay_version(expected)
    spec = load_design_spec(root / "design.yaml")
    provenance = json.loads((root / "SOURCE.json").read_text())
    digests = {p["record"]: p["prepared_model_digest"] for p in provenance["profiles"]}
    if {item.motif.motif_id: item.motif.model_digest for item in spec.specifications} != digests:
        raise ValueError("Example models differ from the declared preparation")
    args.out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    # Record early improvement at doubling counts, plus one late-search checkpoint.
    # Recording does not change the proposal sequence, acceptance, or search budget.
    checkpoints = tuple(sorted({*(2**power for power in range(3, 17)), 49_152}))
    portfolio, observation = design_observed(
        spec, ObservationSpec(max_snapshots=2, incumbent_evaluations=checkpoints)
    )
    elapsed = time.perf_counter() - started
    winner = portfolio.candidates[0]
    if (
        winner.sequence != expected["sequence"]
        or abs(winner.balance_score - expected["balance"]) > 1e-12
    ):
        raise ValueError("Recorded example differs; check the declared software and environment")
    (args.out / "observation.json").write_text(observation.model_dump_json())
    view = inspect_playback(observation)
    (args.out / "inspected.json").write_text(view.model_dump_json())
    (args.out / "playback.html").write_bytes(render_playback_html(view))
    (args.out / "final-frame.svg").write_bytes(render_playback_svg(view))
    if args.media:
        # The movie moves between saved placements; it does not invent search states.
        (args.out / "playback.mp4").write_bytes(
            render_playback_media(view, format_name="mp4", fps=20, transition_frames=24, width=1920)
        )
        (args.out / "playback.gif").write_bytes(
            render_playback_media(view, format_name="gif", fps=20, transition_frames=24, width=700)
        )
        (args.out / "final-frame.png").write_bytes(render_playback_media(view, format_name="png"))
    print(f"Best balance {winner.balance_score:.3f}; complete search {elapsed:.1f} seconds elapsed")
    print(args.out / "playback.html")


if __name__ == "__main__":
    main()

"""
--------------------------------------------------------------------------------
motif-balance
examples/twelve-motifs/reproduce.py

Repeat the twelve-model example and export a recorded search animation.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

import argparse
import hashlib
import json
import time
from pathlib import Path

from motif_balance.api import design_observed
from motif_balance.constants import PACKAGE_VERSION
from motif_balance.formats.design import load_design_spec
from motif_balance.model.search_observation import ObservationSpec
from motif_balance.playback import (
    PlaybackInspection,
    inspect_playback,
    render_playback_html,
    render_playback_media,
    render_playback_svg,
)


def verify_replay_version(expected: dict) -> None:
    if expected.get("recipe_package_version") != PACKAGE_VERSION:
        raise ValueError("Example recipe package differs from the declared version")


def best_progress(source: PlaybackInspection) -> PlaybackInspection:
    """Select the best DNA and its recorded curve, ending at the last improvement."""
    if source.chain_id is not None:
        raise ValueError("The example requires recorded best sequences, not one search chain")
    view = PlaybackInspection.model_validate(
        source.model_copy(update={"search_display": "molecule"}).model_dump(mode="python")
    )
    return view.until_last_improvement()


def write_media(view: PlaybackInspection, destination: Path, *, source_evaluations: int) -> None:
    """Render the shared selection and bind its media files to their recorded scores."""
    view = best_progress(view)
    settings = {"pacing": "accelerating"}
    assets = {}
    # The GIF uses fewer transition frames to keep the higher-resolution preview bounded.
    for name, format_name, width, fps, transitions in (
        ("playback.mp4", "mp4", 1800, 20, 6),
        ("playback.gif", "gif", 1000, 10, 2),
        ("final-frame.png", "png", None, 1, 0),
    ):
        payload = render_playback_media(
            view,
            format_name=format_name,
            width=width,
            **(
                {}
                if format_name == "png"
                else {**settings, "fps": fps, "transition_frames": transitions}
            ),
        )
        (destination / name).write_bytes(payload)
        assets[name] = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "width": width,
            "fps": fps,
            "transition_frames": transitions,
        }
    metadata = {
        "source_record_sha256": view.observation_sha256,
        "source_evaluations": source_evaluations,
        "final_displayed_evaluations": view.frames[-1].evaluations,
        "recorded_checkpoints": len(view.frames),
        "distinct_best": len({frame.candidate.sequence for frame in view.frames}),
        "displayed_chains": max(len(f.recorded_search_candidates) for f in view.frames),
        "search_chain_id": view.search_chain_id,
        "search_display": view.search_display,
        "balance": view.frames[-1].best_balance,
        "full_run_elapsed_seconds": view.full_run_elapsed_seconds,
        "render_package_version": PACKAGE_VERSION,
        **settings,
        "meaning": (
            "The curve shows the best score. Gray molecular layers show recorded search states. "
            "Motion connects saved placements without interpolating scores."
        ),
        "selection": (
            "The displayed record ends at the first recorded occurrence of the final best score."
        ),
        "assets": assets,
    }
    (destination / "media.json").write_text(json.dumps(metadata, indent=2) + "\n")


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
    # Observe the improvement counts verified in this example's original run.
    # These retrospective display choices do not guide proposals or acceptance.
    checkpoints = tuple(expected["showcase_evaluations"])
    portfolio, observation = design_observed(
        spec, ObservationSpec(max_snapshots=96, incumbent_evaluations=checkpoints)
    )
    elapsed = time.perf_counter() - started
    winner = portfolio.candidates[0]
    if (
        winner.sequence != expected["sequence"]
        or abs(winner.balance_score - expected["balance"]) > 1e-12
    ):
        raise ValueError("Recorded example differs; check the declared software and environment")
    (args.out / "observation.json").write_text(observation.model_dump_json())
    # Keep the best-score curve separate from the gray molecular search states.
    full_view = inspect_playback(observation, search_chain_id="all").model_copy(
        update={"full_run_elapsed_seconds": elapsed}
    )
    (args.out / "inspected.json").write_text(full_view.model_dump_json())
    view = best_progress(full_view)
    # Keep the interactive overview small; the movie retains recorded improvements.
    indices = sorted({round(i * (len(view.frames) - 1) / 7) for i in range(8)})
    overview = view.model_copy(
        update={
            "search_chain_id": None,
            "frames": tuple(
                view.frames[i].model_copy(
                    update={
                        "search_candidates": (),
                        "search_evaluations": None,
                    }
                )
                for i in indices
            ),
        }
    )
    (args.out / "playback.html").write_bytes(render_playback_html(overview))
    (args.out / "final-frame.svg").write_bytes(render_playback_svg(view))
    if args.media:
        # The movie moves between saved placements; it does not invent search states.
        write_media(view, args.out, source_evaluations=spec.evaluations)
    print(f"Best balance {winner.balance_score:.3f}; complete search {elapsed:.1f} seconds elapsed")
    print(args.out / "playback.html")


if __name__ == "__main__":
    main()

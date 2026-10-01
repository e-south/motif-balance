"""GIF export preserves complete frames without repeatedly storing their background."""

import io
import math

import pytest

from motif_balance.api import design_observed
from motif_balance.model.search_observation import ObservationSpec
from motif_balance.playback import inspect_playback


def test_gif_stores_changes_without_leaving_previous_frame_marks(pairwise_spec, monkeypatch):
    image_module = pytest.importorskip("PIL.Image")
    image_draw = pytest.importorskip("PIL.ImageDraw")
    image_sequence = pytest.importorskip("PIL.ImageSequence")
    renderer = pytest.importorskip("resvg_py")
    from motif_balance.playback import media

    spec = pairwise_spec.model_copy(update={"length": 7, "evaluations": 91, "count": 1})
    view = inspect_playback(design_observed(spec, ObservationSpec(max_snapshots=12))[1])
    native_width, native_height, _ = media.frame_dimensions(view)
    size = (320, math.ceil(native_height * 320 / native_width))
    expected = []
    for index in range(len(view.frames)):
        image = image_module.new("RGB", size, "white")
        draw = image_draw.Draw(image)
        draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline="black")
        # The moving mark must erase its previous position, including on reversal.
        x = 20 + 15 * min(index, len(view.frames) - 1 - index)
        draw.rectangle((x, 40, x + 8, 48), fill="black")
        expected.append(image)
    remaining = iter(expected)

    def raster(**_kwargs):
        target = io.BytesIO()
        next(remaining).save(target, format="PNG")
        return target.getvalue()

    monkeypatch.setattr(renderer, "svg_to_bytes", raster)
    payload = media.render_playback_media(view, format_name="gif", width=320, fps=5)
    baseline = io.BytesIO()
    expected[0].save(
        baseline,
        format="GIF",
        save_all=True,
        append_images=expected[1:],
        duration=200,
        loop=0,
        disposal=2,
    )
    with image_module.open(io.BytesIO(payload)) as actual:
        # Equal consecutive frames may be combined, but their duration is retained.
        decoded = []
        for frame in image_sequence.Iterator(actual):
            decoded.extend([frame.convert("RGB").tobytes()] * (frame.info["duration"] // 200))
        assert decoded == [frame.tobytes() for frame in expected]
        assert actual.info["loop"] == 0
    assert len(payload) < len(baseline.getvalue())

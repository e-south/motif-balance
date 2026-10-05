"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_playback_media.py

GIF export preserves complete frames without repeatedly storing their background.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

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


@pytest.mark.parametrize("palette_colors", [None, 64])
def test_gif_encoding_preserves_frames_and_holds_the_final_state(
    pairwise_spec, monkeypatch, palette_colors
):
    image_module = pytest.importorskip("PIL.Image")
    image_sequence = pytest.importorskip("PIL.ImageSequence")
    renderer = pytest.importorskip("resvg_py")
    pytest.importorskip("imageio_ffmpeg")
    from motif_balance.playback import media

    view = inspect_playback(
        design_observed(
            pairwise_spec.model_copy(update={"evaluations": 64}),
            ObservationSpec(max_snapshots=4),
        )[1]
    )
    native_width, native_height, _ = media.frame_dimensions(view)
    size = (320, math.ceil(native_height * 320 / native_width))
    colors = [(20 + i * 10, 40, 80) for i in range(len(view.frames))]
    remaining = iter(colors)

    def raster(**_kwargs):
        target = io.BytesIO()
        image_module.new("RGB", size, next(remaining)).save(target, format="PNG")
        return target.getvalue()

    monkeypatch.setattr(renderer, "svg_to_bytes", raster)
    payload = media.render_playback_media(
        view,
        format_name="gif",
        width=320,
        fps=10,
        gif_palette_colors=palette_colors,
        final_frame_duration_ms=2000,
    )
    with image_module.open(io.BytesIO(payload)) as actual:
        assert actual.n_frames == len(colors)
        durations = []
        decoded = []
        for frame in image_sequence.Iterator(actual):
            durations.append(frame.info["duration"])
            decoded.append(frame.convert("RGB").getpixel((0, 0)))
        assert decoded == colors
        assert durations == [100] * (len(colors) - 1) + [2000]
        assert actual.info["loop"] == 0


def test_gif_palette_uses_colors_from_all_frames_without_dithering():
    image_module = pytest.importorskip("PIL.Image")
    image_sequence = pytest.importorskip("PIL.ImageSequence")
    pytest.importorskip("imageio_ffmpeg")
    from motif_balance.playback.media import _encode_gif

    images = []
    for blue in (0, 255):
        image = image_module.new("RGB", (384, 4))
        image.putdata([(x // 4 * 2, 20, blue) for _ in range(4) for x in range(384)])
        images.append(image)
    source = io.BytesIO()
    images[0].save(
        source, format="GIF", save_all=True, append_images=images[1:], duration=200, loop=0
    )
    payload = _encode_gif(source.getvalue(), palette_colors=64, final_frame_duration_ms=None)
    with image_module.open(io.BytesIO(payload)) as actual:
        assert actual.n_frames == 2
        colors = set()
        for index, frame in enumerate(image_sequence.Iterator(actual)):
            pixels = frame.convert("RGB")
            colors.update(color for _, color in pixels.getcolors(maxcolors=384 * 4))
            assert frame.info["duration"] == 200
            assert pixels.getpixel((0, 0))[2] == index * 255
            # Every solid source patch stays solid instead of acquiring dither patterns.
            for x in range(0, 384, 4):
                assert pixels.crop((x, 0, x + 4, 4)).getcolors(maxcolors=1) is not None
        assert len(colors) <= 64


@pytest.mark.parametrize(
    "settings",
    [
        {"gif_palette_colors": True},
        {"gif_palette_colors": 3},
        {"gif_palette_colors": 257},
        {"final_frame_duration_ms": True},
        {"final_frame_duration_ms": 0},
        {"final_frame_duration_ms": 15},
        {"final_frame_duration_ms": 655360},
        {"format_name": "mp4", "gif_palette_colors": 64},
        {"format_name": "png", "final_frame_duration_ms": 2000},
    ],
)
def test_gif_encoding_settings_fail_before_loading_dependencies(
    pairwise_spec, monkeypatch, settings
):
    from motif_balance.errors import ArtifactError
    from motif_balance.playback import media

    view = inspect_playback(
        design_observed(
            pairwise_spec.model_copy(update={"evaluations": 64}),
            ObservationSpec(max_snapshots=4),
        )[1]
    )
    monkeypatch.setattr(
        media, "_dependency", lambda _: pytest.fail("invalid GIF settings admitted")
    )
    with pytest.raises(ArtifactError, match=r"GIF|gif_palette_colors|final_frame_duration_ms"):
        media.render_playback_media(view, **{"format_name": "gif", **settings})

"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/playback/media.py

Export inspected search frames with optional raster and video dependencies.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import importlib
import io
import math
import tempfile
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any, Literal

from motif_balance.errors import ArtifactError

from .model import PlaybackInspection
from .render import frame_dimensions, render_playback_svg, validate_view
from .transition import blend_svgs

_MAX_PIXELS = 128_000_000
_MAX_TOTAL_PIXELS = 1_000_000_000
_MAX_BYTES = 64 * 1024 * 1024


def _dependency(name: str) -> ModuleType:
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise ArtifactError(
            "media export requires the visualization extra; install motif-balance[visualization]"
        ) from exc


def render_playback_media(
    view: PlaybackInspection,
    *,
    format_name: Literal["png", "gif", "mp4"],
    fps: int = 4,
    frame: int = -1,
    transition_frames: int = 0,
    width: int | None = None,
) -> bytes:
    """Return PNG for one frame, or GIF/MP4 for all recorded frames in order.

    Movie timing expresses a viewing rate. It is not search elapsed time. The
    optional transitions move and crossfade the recorded drawings without
    inventing intermediate scores or DNA sequences.
    """
    view = validate_view(view)
    if format_name not in ("png", "gif", "mp4"):
        raise ArtifactError("media format must be png, gif or mp4")
    if type(fps) is not int or not 1 <= fps <= 30:
        raise ArtifactError("fps must be an integer from 1 through 30")
    if type(transition_frames) is not int or not 0 <= transition_frames <= 30:
        raise ArtifactError("transition_frames must be an integer from zero through thirty")
    if transition_frames and format_name == "png":
        raise ArtifactError("transitions apply only to GIF or MP4")
    native_width, native_height, _ = frame_dimensions(view)
    if width is not None and (type(width) is not int or not 320 <= width <= native_width):
        raise ArtifactError("width must be an integer from 320 through the native frame width")
    width = native_width if width is None else width
    height = math.ceil(native_height * width / native_width)
    hold = max(1, fps // 2) if transition_frames else 1
    count = (
        1
        if format_name == "png"
        else len(view.frames) * hold + (len(view.frames) - 1) * transition_frames
    )
    # GIF retains its frames; MP4 streams one raster at a time to the encoder.
    if width * height * (count if format_name == "gif" else 1) > _MAX_PIXELS:
        raise ArtifactError("media exceeds the 128-million-pixel limit; reduce width or use MP4")
    if width * height * count > _MAX_TOTAL_PIXELS:
        raise ArtifactError(
            "media exceeds the one-billion total-pixel limit; reduce width or frames"
        )
    renderer = _dependency("resvg_py")
    image_module = _dependency("PIL.Image")

    def raster(svg: bytes) -> Any:
        png = renderer.svg_to_bytes(svg_string=svg.decode(), width=width)
        with image_module.open(io.BytesIO(png)) as image:
            if image.size != (width, height):
                raise ArtifactError(f"renderer returned {image.size}, expected {(width, height)}")
            return image.convert("RGB")

    if format_name == "png":
        return bytes(
            renderer.svg_to_bytes(
                svg_string=render_playback_svg(view, frame=frame).decode(), width=width
            )
        )

    def frames() -> Iterator[Any]:
        previous = None
        for index in range(len(view.frames)):
            svg = render_playback_svg(view, frame=index)
            if previous is not None:
                for step in range(1, transition_frames + 1):
                    yield raster(blend_svgs(previous, svg, step / (transition_frames + 1)))
            image = raster(svg)
            for _ in range(hold):
                yield image
            previous = svg

    if format_name == "gif":
        images = list(frames())
        target = io.BytesIO()
        images[0].save(
            target,
            format="GIF",
            save_all=True,
            append_images=images[1:],
            duration=round(1000 / fps),
            loop=0,
            disposal=2,
        )
        payload = target.getvalue()
    else:
        encoder = _dependency("imageio_ffmpeg")
        with tempfile.TemporaryDirectory(prefix="motif-playback-") as directory:
            target_path = Path(directory) / "playback.mp4"
            # Explicit even padding supports H.264 without resizing the molecule.
            writer = encoder.write_frames(
                str(target_path),
                (width, height),
                fps=fps,
                codec="libx264",
                pix_fmt_in="rgb24",
                pix_fmt_out="yuv420p",
                macro_block_size=1,
                ffmpeg_timeout=30,
                output_params=["-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-movflags", "+faststart"],
            )
            try:
                writer.send(None)
                for image in frames():
                    writer.send(image.tobytes())
            finally:
                writer.close()
            if target_path.stat().st_size > _MAX_BYTES:
                raise ArtifactError("playback media exceeds 64 MiB")
            payload = target_path.read_bytes()
    if len(payload) > _MAX_BYTES:
        raise ArtifactError("playback media exceeds 64 MiB")
    return payload

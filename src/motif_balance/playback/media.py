"""Export inspected search frames with optional raster and video dependencies.

Maintainer(s): Eric J. South, Dunlop Lab
"""

import importlib
import io
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Literal

from motif_balance.errors import ArtifactError

from .model import PlaybackInspection
from .render import frame_dimensions, render_playback_svg, validate_view

_MAX_PIXELS = 128_000_000
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
) -> bytes:
    """Return PNG for one frame, or GIF/MP4 for all recorded frames in order.

    Movie timing expresses a viewing rate. It is not search elapsed time. The
    renderer never interpolates scores, nucleotides or motif arrangements.
    """
    view = validate_view(view)
    if format_name not in ("png", "gif", "mp4"):
        raise ArtifactError("media format must be png, gif or mp4")
    if type(fps) is not int or not 1 <= fps <= 30:
        raise ArtifactError("fps must be an integer from 1 through 30")
    width, height, _ = frame_dimensions(view)
    count = 1 if format_name == "png" else len(view.frames)
    if width * height * count > _MAX_PIXELS:
        raise ArtifactError("media exceeds the 128-million-pixel limit; request fewer snapshots")
    renderer = _dependency("resvg_py")
    image_module = _dependency("PIL.Image")
    indices = (frame,) if format_name == "png" else tuple(range(len(view.frames)))
    images = []
    for index in indices:
        svg = render_playback_svg(view, frame=index).decode()
        png = renderer.svg_to_bytes(svg_string=svg)
        if format_name == "png":
            return bytes(png)
        with image_module.open(io.BytesIO(png)) as image:
            images.append(image.convert("RGB"))
    if format_name == "gif":
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
                for image in images:
                    writer.send(image.tobytes())
            finally:
                writer.close()
            if target_path.stat().st_size > _MAX_BYTES:
                raise ArtifactError("playback media exceeds 64 MiB")
            payload = target_path.read_bytes()
    if len(payload) > _MAX_BYTES:
        raise ArtifactError("playback media exceeds 64 MiB")
    return payload

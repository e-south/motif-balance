"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/examples/preparation.py

Write complete example inputs and an editable request from packaged recipes.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

import json
import os
import shutil
import tempfile
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

from motif_balance.artifacts.publication import _publish_directory_no_replace
from motif_balance.errors import ArtifactError

from .download import archive_bytes, default_cache
from .profiles import prepare_profiles

ExampleName = Literal["argr-cra", "twelve-motifs"]


def recipe(name: str) -> tuple[dict[str, Any], bytes]:
    """Read a packaged recipe without fetching its third-party inputs."""
    if name not in ("argr-cra", "twelve-motifs"):
        raise ValueError("Choose argr-cra or twelve-motifs")
    root = files("motif_balance.examples").joinpath("data", name)
    return json.loads(root.joinpath("SOURCE.json").read_text()), root.joinpath(
        "design.yaml"
    ).read_bytes()


def prepare_example(name: ExampleName, out: Path, *, cache: Path | None = None) -> Path:
    """Download/check source data, then publish a new editable example directory.

    Only this explicit operation accesses the network. Existing outputs are
    never replaced. A checked cache supports subsequent offline preparation.
    """
    out = Path(out).absolute()
    if os.path.lexists(out):
        raise ArtifactError(
            "Choose a new output directory; the requested directory already exists."
        )
    if not out.parent.is_dir():
        raise FileNotFoundError("The output parent directory must already exist")
    provenance, request = recipe(name)
    archive = archive_bytes(
        provenance["url"], provenance["archive_sha256"], cache or default_cache()
    )
    outputs = prepare_profiles(archive, provenance)
    outputs = {f"inputs/{name}": content for name, content in outputs.items()}
    outputs["design.yaml"] = request
    outputs["SOURCE.json"] = (json.dumps(provenance, indent=2) + "\n").encode()
    _publish_files(out, outputs)
    return out


def _publish_files(out: Path, outputs: dict[str, bytes]) -> None:
    stage = Path(tempfile.mkdtemp(prefix=f".{out.name}.", dir=out.parent))
    try:
        for relative, content in outputs.items():
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        _publish_directory_no_replace(stage, out)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def prepare_inputs(name: ExampleName, out: Path) -> None:
    """Support the source-checkout replay scripts through the installed recipe."""
    if os.path.lexists(out):
        raise ArtifactError("Choose a new input directory; the requested directory already exists.")
    provenance, _ = recipe(name)
    archive = archive_bytes(provenance["url"], provenance["archive_sha256"], default_cache())
    _publish_files(out.absolute(), prepare_profiles(archive, provenance))

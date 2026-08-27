from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _checker() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "check_architecture.py"
    spec = importlib.util.spec_from_file_location("motif_balance_architecture_checker", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_renderer_cannot_import_scoring_or_verified_source_layers() -> None:
    checker = _checker()

    scoring = checker.violations_for_source(
        Path("inspection/render/rogue.py"),
        "from motif_balance.scoring import evaluate\n",
    )
    verified_source = checker.violations_for_source(
        Path("inspection/render/rogue.py"),
        "from ..verify import VerifiedResultSource\n",
    )

    assert any("inspection renderer" in error and "scoring" in error for error in scoring)
    assert any("inspection renderer" in error and "verify" in error for error in verified_source)


def test_projection_cannot_depend_on_renderers() -> None:
    checker = _checker()

    errors = checker.violations_for_source(
        Path("inspection/project.py"),
        "from .render import render_html\n",
    )

    assert any("inspection projector" in error and "render" in error for error in errors)

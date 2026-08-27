from __future__ import annotations

import importlib.util
import subprocess
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


def test_repository_owned_paths_ignore_cache_residue_but_keep_new_source(tmp_path: Path) -> None:
    checker = _checker()
    subprocess.run(("git", "init", "-q", str(tmp_path)), check=True)
    (tmp_path / ".gitignore").write_text("__pycache__/\n")
    cache = tmp_path / "tests" / "migration" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "stale.pyc").write_bytes(b"cache")

    owned = checker.repository_owned_paths(tmp_path)
    assert Path("tests/migration/__pycache__/stale.pyc") not in owned
    assert checker.forbidden_surface_violations(owned) == []

    source = tmp_path / "tests" / "migration" / "test_old.py"
    source.write_text("def test_old(): pass\n")
    owned = checker.repository_owned_paths(tmp_path)
    assert Path("tests/migration/test_old.py") in owned
    assert checker.forbidden_surface_violations(owned) == [
        "non-product surface must live with its owning workflow: tests/migration"
    ]

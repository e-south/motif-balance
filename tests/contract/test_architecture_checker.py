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


def test_pair_assessment_uses_compilation_but_cannot_invoke_search_or_selection() -> None:
    checker = _checker()
    assert (
        checker.violations_for_source(
            Path("assessment.py"), "from motif_balance.compile import _compile_motif\n"
        )
        == []
    )
    for layer in ("search", "selection", "api", "artifacts"):
        errors = checker.violations_for_source(
            Path("assessment.py"), f"from motif_balance.{layer} import operation\n"
        )
        assert any(f"must not import '{layer}'" in error for error in errors)


def test_projection_cannot_depend_on_renderers() -> None:
    checker = _checker()

    errors = checker.violations_for_source(
        Path("inspection/project.py"),
        "from .render import render_html\n",
    )

    assert any("inspection projector" in error and "render" in error for error in errors)


def test_supplied_projection_preserves_the_data_only_renderer_boundary() -> None:
    checker = _checker()
    assert (
        checker.violations_for_source(
            Path("inspection/render/candidate.py"),
            "from ..candidate_model import CandidateInspection\n",
        )
        == []
    )
    assert checker.violations_for_source(
        Path("inspection/render/candidate.py"),
        "from ..supplied import inspect_candidate\n",
    )
    assert checker.violations_for_source(
        Path("inspection/supplied.py"),
        "from .render import render_candidate_svg\n",
    )
    assert checker.violations_for_source(
        Path("inspection/candidate_model.py"),
        "from motif_balance.scoring import evaluate\n",
    )


def test_assessment_projection_and_render_keep_the_calculation_boundary() -> None:
    checker = _checker()
    assert (
        checker.violations_for_source(
            Path("inspection/assessment/project.py"),
            "from motif_balance.assessment import assess_pair\n",
        )
        == []
    )
    assert (
        checker.violations_for_source(
            Path("inspection/render/assessment.py"),
            "from motif_balance.inspection.assessment.model import PairAssessmentInspection\n",
        )
        == []
    )
    for module in (
        "motif_balance.assessment",
        "motif_balance.inspection.assessment",
        "motif_balance.inspection.assessment.project",
    ):
        assert checker.violations_for_source(
            Path("inspection/render/assessment.py"), f"from {module} import operation\n"
        )
    assert checker.violations_for_source(
        Path("inspection/assessment/project.py"),
        "from motif_balance.inspection.render import render_pair_assessment_svg\n",
    )


def test_architecture_ranking_can_score_but_cannot_search_or_publish() -> None:
    checker = _checker()
    for layer in ("compile", "constants", "model", "scoring"):
        assert (
            checker.violations_for_source(
                Path("alternatives/api.py"), f"from motif_balance.{layer} import operation\n"
            )
            == []
        )
    for layer in ("search", "api", "artifacts", "inspection", "cli"):
        errors = checker.violations_for_source(
            Path("alternatives/api.py"), f"from motif_balance.{layer} import operation\n"
        )
        assert any(f"must not import '{layer}'" in error for error in errors)


def test_nested_projection_modules_cannot_depend_on_renderers() -> None:
    checker = _checker()

    errors = checker.violations_for_source(
        Path("inspection/project/helpers.py"),
        "from motif_balance.inspection.render import render_html\n",
    )

    assert any("inspection projector" in error and "render" in error for error in errors)


def test_nested_modules_inherit_their_declared_top_level_layer() -> None:
    checker = _checker()

    allowed = checker.violations_for_source(
        Path("search/proposals/local.py"),
        "from motif_balance.scoring import evaluate\n",
    )
    inverted = checker.violations_for_source(
        Path("search/proposals/local.py"),
        "from motif_balance.cli import main\n",
    )
    unknown = checker.violations_for_source(
        Path("unknown/helpers.py"),
        "from motif_balance.model import Candidate\n",
    )

    assert allowed == []
    assert any("layer 'search' must not import 'cli'" in error for error in inverted)
    assert any("unknown first-party" in error and "unknown" in error for error in unknown)


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

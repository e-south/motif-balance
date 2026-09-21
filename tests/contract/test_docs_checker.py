"""Documentation links must resolve before a branch becomes public main."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def checker() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "check_docs.py"
    spec = importlib.util.spec_from_file_location("motif_balance_docs_checker", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/e-south/motif-balance/blob/main/docs/missing.md",
        "https://github.com/e-south/motif-balance/tree/main/examples/missing",
        "https://raw.githubusercontent.com/e-south/motif-balance/main/assets/missing.svg",
    ],
)
def test_repository_web_links_are_checked_in_current_tree(url: str) -> None:
    module = checker()
    errors = module.link_errors(module.REPO_ROOT / "README.md", f"[Guide]({url})")
    assert len(errors) == 1
    assert "broken link" in errors[0]


def test_repository_web_link_fragment_is_checked() -> None:
    module = checker()
    url = "https://github.com/e-south/motif-balance/blob/main/README.md#missing-heading"
    assert (
        "broken heading fragment"
        in module.link_errors(module.REPO_ROOT / "README.md", f"[Guide]({url})")[0]
    )


def test_valid_repository_and_external_links_are_accepted() -> None:
    module = checker()
    text = "\n".join(
        f"[Guide]({url})"
        for url in (
            "https://github.com/e-south/motif-balance/blob/main/docs/biological-example.md",
            "https://github.com/e-south/motif-balance/tree/main/examples/developmental-trio/",
            "https://raw.githubusercontent.com/e-south/motif-balance/main/assets/motif-balance-banner.svg",
            "https://github.com/another/project/blob/main/README.md",
        )
    )
    assert module.link_errors(module.REPO_ROOT / "README.md", text) == []


def test_readme_and_example_links_are_included(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = checker()
    (tmp_path / "README.md").write_text("[Missing](absent.md)")
    example = tmp_path / "examples" / "demo"
    example.mkdir(parents=True)
    (example / "README.md").write_text("[Missing](absent.md)")
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "ROOT_DOCS", [])
    module.main()
    output = capsys.readouterr().out
    assert "README.md: broken link" in output
    assert "examples/demo/README.md: broken link" in output

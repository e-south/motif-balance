#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
motif-balance
scripts/check_docs.py

Check documentation links, fenced blocks, and accessible banner routing.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_DOCS = [
    REPO_ROOT / "IA.md",
    REPO_ROOT / "ARCHITECTURE.md",
    REPO_ROOT / "DESIGN.md",
    REPO_ROOT / "RELIABILITY.md",
    REPO_ROOT / "SECURITY.md",
]
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
BANNER_PATH = REPO_ROOT / "assets" / "motif-balance-banner.svg"
REPOSITORY_FILE_URLS = (
    "https://github.com/e-south/motif-balance/blob/main/",
    "https://github.com/e-south/motif-balance/tree/main/",
    "https://raw.githubusercontent.com/e-south/motif-balance/main/",
)


def heading_anchors(text: str) -> set[str]:
    """Return GitHub-style anchors for Markdown headings."""
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for raw in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", text, flags=re.MULTILINE):
        plain = re.sub(r"[`*_~]", "", raw).strip().lower()
        anchor = re.sub(r"[^\w\- ]", "", plain).replace(" ", "-")
        suffix = counts.get(anchor, 0)
        counts[anchor] = suffix + 1
        anchors.add(anchor if suffix == 0 else f"{anchor}-{suffix}")
    return anchors


class _PreviewLinks(HTMLParser):
    """Read image and video links used for sized documentation previews."""

    def __init__(self) -> None:
        super().__init__()
        self.targets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attribute = {"a": "href", "img": "src", "video": "src", "source": "src"}.get(tag)
        for name, value in attrs:
            if name == attribute and value:
                self.targets.append(value)


def link_errors(path: Path, text: str) -> list[str]:
    """Check local and canonical repository-file links against this checkout."""
    errors: list[str] = []
    previews = _PreviewLinks()
    previews.feed(text)
    for raw_target in [*LINK_PATTERN.findall(text), *previews.targets]:
        target_with_fragment = raw_target.strip().strip("<>")
        repository_prefix = next(
            (prefix for prefix in REPOSITORY_FILE_URLS if target_with_fragment.startswith(prefix)),
            None,
        )
        if repository_prefix is not None:
            target_with_fragment = target_with_fragment.removeprefix(repository_prefix)
            base = REPO_ROOT
        elif "://" in target_with_fragment or target_with_fragment.startswith("mailto:"):
            continue
        else:
            base = path.parent
        target, _, fragment = target_with_fragment.partition("#")
        resolved = path if not target else (base / unquote(target)).resolve()
        try:
            resolved.relative_to(REPO_ROOT)
        except ValueError:
            errors.append(f"{path.relative_to(REPO_ROOT)}: link escapes repository {raw_target!r}")
            continue
        if not resolved.exists():
            errors.append(f"{path.relative_to(REPO_ROOT)}: broken link {raw_target!r}")
        elif (
            fragment
            and resolved.suffix == ".md"
            and unquote(fragment) not in heading_anchors(resolved.read_text(encoding="utf-8"))
        ):
            errors.append(f"{path.relative_to(REPO_ROOT)}: broken heading fragment {raw_target!r}")
    return errors


def main() -> int:
    """Check readable documentation without requiring administrative metadata."""
    errors: list[str] = []
    docs = sorted(
        set(ROOT_DOCS)
        | set(REPO_ROOT.glob("*.md"))
        | set((REPO_ROOT / "docs").rglob("*.md"))
        | set((REPO_ROOT / "examples").rglob("*.md"))
    )
    for path in docs:
        if not path.is_file():
            errors.append(f"{path.relative_to(REPO_ROOT)}: missing document")
            continue
        text = path.read_text(encoding="utf-8")
        if text.count("```") % 2:
            errors.append(f"{path.relative_to(REPO_ROOT)}: unbalanced fenced code blocks")
        errors.extend(link_errors(path, text))

    try:
        banner = ET.parse(BANNER_PATH).getroot()
        expected_attributes = {"width": "1280", "height": "230", "viewBox": "0 0 1280 230"}
        for name, value in expected_attributes.items():
            if banner.get(name) != value:
                errors.append(f"assets/motif-balance-banner.svg: invalid {name}")
        namespace = "{http://www.w3.org/2000/svg}"
        if banner.find(f"{namespace}title") is None or banner.find(f"{namespace}desc") is None:
            errors.append(
                "assets/motif-balance-banner.svg: missing accessible title or description"
            )
        if "assets/motif-balance-banner.svg" not in (REPO_ROOT / "README.md").read_text():
            errors.append("README.md: missing banner route")
    except (OSError, ET.ParseError) as exc:
        errors.append(f"assets/motif-balance-banner.svg: unable to parse: {exc}")

    if errors:
        print("Documentation integrity failures:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Documentation integrity: ok (links and fenced blocks in {len(docs)} documents)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

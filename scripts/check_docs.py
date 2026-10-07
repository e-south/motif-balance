#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
motif-balance
scripts/check_docs.py

Check documentation links, fenced blocks, and accessible banner routing.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import os
import re
import subprocess
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_DOCS = [
    REPO_ROOT / "ARCHITECTURE.md",
    REPO_ROOT / "DESIGN.md",
    REPO_ROOT / "RELIABILITY.md",
    REPO_ROOT / "SECURITY.md",
]
# Match destinations independently of labels, including links around images.
LINK_PATTERN = re.compile(r"\]\(([^)]+)\)")
BANNER_PATH = REPO_ROOT / "assets" / "motif-balance-banner.svg"
# GitHub redirects between blob/tree pages; raw URLs must resolve to files.
REPOSITORY_FILE_URL = re.compile(
    r"https://(?:github\.com/e-south/motif-balance/(?P<route>blob|tree)"
    r"|raw\.githubusercontent\.com/e-south/motif-balance)"
    r"/(?P<revision>main|[0-9a-f]{40})/(?P<target>.*)"
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


def package_description_errors(text: str) -> list[str]:
    """Require links that resolve when the README is displayed outside GitHub."""
    previews = _PreviewLinks()
    previews.feed(text)
    errors: list[str] = []
    for raw_target in [*LINK_PATTERN.findall(text), *previews.targets]:
        target = raw_target.strip().strip("<>")
        if not target.startswith(("https://", "#")):
            errors.append(f"Package description needs an absolute HTTPS link: {raw_target!r}")
    return errors


def _git_object(option: str, reference: str) -> bytes | None:
    """Read only available Git objects; incomplete history must not pass a link."""
    try:
        result = subprocess.run(
            ["git", "cat-file", option, reference],
            cwd=REPO_ROOT,
            env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def _pinned_link_errors(
    path: Path, revision: str, target: str, raw_target: str, route: str
) -> list[str]:
    """Check immutable repository URLs in their declared tree, including byte limits."""
    label = path.relative_to(REPO_ROOT)
    target, _, fragment = target.partition("#")
    relative = PurePosixPath(unquote(target))
    if relative.is_absolute() or ".." in relative.parts:
        return [f"{label}: link escapes repository {raw_target!r}"]
    if _git_object("-e", f"{revision}^{{commit}}") is None:
        return [
            f"{label}: broken link {raw_target!r}: pinned revision unavailable; "
            "check out full Git history"
        ]
    reference = f"{revision}:{relative.as_posix()}"
    kind = _git_object("-t", reference)
    if kind is None:
        return [f"{label}: broken link {raw_target!r}"]
    if route == "raw" and kind.strip() != b"blob":
        return [f"{label}: broken link {raw_target!r}: raw URL requires a file"]
    if kind.strip() == b"blob":
        if path == REPO_ROOT / "README.md" and relative.suffix.lower() in {
            ".png",
            ".gif",
            ".jpg",
            ".jpeg",
            ".webp",
            ".svg",
        }:
            size = _git_object("-s", reference)
            if size is None:
                return [f"{label}: unable to read pinned image {raw_target!r}"]
            if int(size) > 10_000_000:
                return [f"README.md: image exceeds 10 MB for the PyPI proxy: {raw_target!r}"]
        if fragment and relative.suffix == ".md":
            content = _git_object("-p", reference)
            if content is None or unquote(fragment) not in heading_anchors(content.decode("utf-8")):
                return [f"{label}: broken heading fragment {raw_target!r}"]
    return []


def link_errors(path: Path, text: str) -> list[str]:
    """Check local links in this checkout and pinned URLs in their declared Git tree."""
    errors: list[str] = []
    previews = _PreviewLinks()
    previews.feed(text)
    for raw_target in [*LINK_PATTERN.findall(text), *previews.targets]:
        route = None
        target_with_fragment = raw_target.strip().strip("<>")
        repository_match = REPOSITORY_FILE_URL.fullmatch(target_with_fragment)
        if repository_match is not None:
            route = repository_match.group("route") or "raw"
            revision = repository_match.group("revision")
            target_with_fragment = repository_match.group("target")
            if revision != "main":
                errors.extend(
                    _pinned_link_errors(path, revision, target_with_fragment, raw_target, route)
                )
                continue
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
        elif route == "raw" and not resolved.is_file():
            errors.append(
                f"{path.relative_to(REPO_ROOT)}: broken link {raw_target!r}: "
                "raw URL requires a file"
            )
        elif (
            path == REPO_ROOT / "README.md"
            and resolved.suffix.lower() in {".png", ".gif", ".jpg", ".jpeg", ".webp", ".svg"}
            and resolved.stat().st_size > 10_000_000
        ):
            errors.append(f"README.md: image exceeds 10 MB for the PyPI proxy: {raw_target!r}")
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
        if path == REPO_ROOT / "README.md":
            errors.extend(package_description_errors(text))

    try:
        banner = ET.parse(BANNER_PATH).getroot()
        expected_attributes = {"width": "1280", "height": "200", "viewBox": "0 0 1280 200"}
        for name, value in expected_attributes.items():
            if banner.get(name) != value:
                errors.append(f"assets/motif-balance-banner.svg: invalid {name}")
        namespace = "{http://www.w3.org/2000/svg}"
        if banner.find(f"{namespace}title") is None or banner.find(f"{namespace}desc") is None:
            errors.append(
                "assets/motif-balance-banner.svg: missing accessible title or description"
            )
        if "assets/motif-balance-banner.png" not in (REPO_ROOT / "README.md").read_text():
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

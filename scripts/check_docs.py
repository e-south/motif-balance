#!/usr/bin/env python3
"""Check documentation metadata, local links, and fenced blocks."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_DOCS = [
    REPO_ROOT / "ARCHITECTURE.md",
    REPO_ROOT / "DESIGN.md",
    REPO_ROOT / "RELIABILITY.md",
    REPO_ROOT / "SECURITY.md",
]
REQUIRED_KEYS = {
    "doc_id",
    "title",
    "intent",
    "audience",
    "owner",
    "status",
    "last_verified",
    "doc_type",
}
DOC_TYPES = {"tutorial", "how-to", "reference", "explanation", "decision", "index"}
STATUSES = {"active", "accepted"}
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def frontmatter(path: Path) -> tuple[dict[str, object], str]:
    """Read one complete Markdown YAML frontmatter block."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("missing opening frontmatter delimiter")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("missing closing frontmatter delimiter") from exc
    parsed = yaml.safe_load("\n".join(lines[1:closing]))
    if not isinstance(parsed, dict) or not all(isinstance(key, str) for key in parsed):
        raise ValueError("frontmatter must be a YAML mapping with string keys")
    return parsed, text


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


def link_errors(path: Path, text: str) -> list[str]:
    """Return broken local Markdown links."""
    errors: list[str] = []
    for raw_target in LINK_PATTERN.findall(text):
        target_with_fragment = raw_target.strip().strip("<>")
        if "://" in target_with_fragment or target_with_fragment.startswith("mailto:"):
            continue
        target, _, fragment = target_with_fragment.partition("#")
        resolved = path if not target else (path.parent / target).resolve()
        try:
            resolved.relative_to(REPO_ROOT)
        except ValueError:
            errors.append(f"{path.relative_to(REPO_ROOT)}: link escapes repository {raw_target!r}")
            continue
        if not resolved.exists():
            errors.append(f"{path.relative_to(REPO_ROOT)}: broken link {raw_target!r}")
        elif (
            fragment
            and resolved.is_file()
            and fragment not in heading_anchors(resolved.read_text(encoding="utf-8"))
        ):
            errors.append(f"{path.relative_to(REPO_ROOT)}: broken heading fragment {raw_target!r}")
    return errors


def main() -> int:
    """Run repository knowledge-integrity checks."""
    errors: list[str] = []
    doc_ids: dict[str, Path] = {}
    oldest_allowed = date.today() - timedelta(days=180)
    docs = ROOT_DOCS + sorted((REPO_ROOT / "docs").rglob("*.md"))

    for path in docs:
        try:
            metadata, text = frontmatter(path)
        except ValueError as exc:
            errors.append(f"{path.relative_to(REPO_ROOT)}: {exc}")
            continue
        missing = REQUIRED_KEYS - metadata.keys()
        if missing:
            errors.append(
                f"{path.relative_to(REPO_ROOT)}: missing keys {', '.join(sorted(missing))}"
            )
        for scalar_key in ("title", "intent", "owner"):
            value = metadata.get(scalar_key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{path.relative_to(REPO_ROOT)}: invalid {scalar_key}")
        audience = metadata.get("audience")
        if (
            not isinstance(audience, list)
            or not audience
            or not all(isinstance(item, str) and item.strip() for item in audience)
        ):
            errors.append(f"{path.relative_to(REPO_ROOT)}: invalid audience")
        doc_id = metadata.get("doc_id")
        if not isinstance(doc_id, str) or not doc_id.strip():
            errors.append(f"{path.relative_to(REPO_ROOT)}: invalid doc_id")
        elif doc_id in doc_ids:
            errors.append(
                f"{path.relative_to(REPO_ROOT)}: duplicate doc_id also in "
                f"{doc_ids[doc_id].relative_to(REPO_ROOT)}"
            )
        else:
            doc_ids[doc_id] = path
        if metadata.get("status") not in STATUSES:
            errors.append(f"{path.relative_to(REPO_ROOT)}: invalid status")
        if metadata.get("doc_type") not in DOC_TYPES:
            errors.append(f"{path.relative_to(REPO_ROOT)}: invalid doc_type")
        verified = metadata.get("last_verified")
        if isinstance(verified, date):
            verified_date = verified
        elif isinstance(verified, str):
            try:
                verified_date = date.fromisoformat(verified)
            except ValueError:
                verified_date = None
        else:
            verified_date = None
        if verified_date is None or verified_date > date.today():
            errors.append(f"{path.relative_to(REPO_ROOT)}: invalid last_verified date")
        elif verified_date < oldest_allowed:
            errors.append(f"{path.relative_to(REPO_ROOT)}: stale last_verified date")
        if text.count("```") % 2:
            errors.append(f"{path.relative_to(REPO_ROOT)}: unbalanced fenced code blocks")
        errors.extend(link_errors(path, text))

    if errors:
        print("Documentation integrity failures:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Documentation integrity: ok ({len(docs)} documents)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

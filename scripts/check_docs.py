#!/usr/bin/env python3
"""Check documentation metadata, local links, and fenced blocks."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_DOCS = [
    REPO_ROOT / "IA.md",
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
KNOWN_JOURNEYS = {"install", "design", "score", "verify", "inspect", "integrate", "maintain"}
REQUIRED_JOURNEY_DOCS = {
    "docs/quickstart.md": ("tutorial", {"install", "design", "verify"}),
    "docs/score-sequences.md": ("how-to", {"score"}),
    "docs/reference/result-inspection.md": ("reference", {"inspect"}),
    "docs/reference/public-contract.md": ("reference", {"integrate"}),
    "ARCHITECTURE.md": ("explanation", {"maintain"}),
}
BANNER_PATH = REPO_ROOT / "assets" / "motif-balance-banner.svg"


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
    metadata_by_path: dict[str, dict[str, object]] = {}
    oldest_allowed = date.today() - timedelta(days=180)
    docs = ROOT_DOCS + sorted((REPO_ROOT / "docs").rglob("*.md"))

    for path in docs:
        try:
            metadata, text = frontmatter(path)
        except ValueError as exc:
            errors.append(f"{path.relative_to(REPO_ROOT)}: {exc}")
            continue
        relative_path = path.relative_to(REPO_ROOT).as_posix()
        metadata_by_path[relative_path] = metadata
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
        journey = metadata.get("journey")
        if journey is not None and (
            not isinstance(journey, list)
            or not journey
            or not all(isinstance(item, str) and item in KNOWN_JOURNEYS for item in journey)
            or len(journey) != len(set(journey))
        ):
            errors.append(f"{path.relative_to(REPO_ROOT)}: invalid journey")
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

    for path, (expected_type, expected_journeys) in REQUIRED_JOURNEY_DOCS.items():
        metadata = metadata_by_path.get(path)
        if metadata is None:
            errors.append(f"{path}: missing required journey document")
            continue
        if metadata.get("doc_type") != expected_type:
            errors.append(f"{path}: journey document must be {expected_type}")
        actual = metadata.get("journey")
        if not isinstance(actual, list) or set(actual) != expected_journeys:
            errors.append(f"{path}: journey must be {', '.join(sorted(expected_journeys))}")

    try:
        banner = ET.parse(BANNER_PATH).getroot()
        expected_attributes = {"width": "1280", "height": "260", "viewBox": "0 0 1280 260"}
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
    print(f"Documentation integrity: ok ({len(docs)} documents)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

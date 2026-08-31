#!/usr/bin/env python3
"""Enforce Motif Balance first-party dependency direction."""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "src" / "motif_balance"
FORBIDDEN_PRODUCT_SURFACES = (
    Path("benchmarks/technical-note"),
    Path("docs/migration"),
    Path("docs/reproduce-paper.md"),
    Path("migration"),
    Path("tests/migration"),
)
_FALLBACK_IGNORED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
}

KNOWN_LAYERS = {
    "admissibility",
    "api",
    "artifacts",
    "cli",
    "claim_language",
    "compile",
    "constants",
    "errors",
    "execution",
    "formats",
    "inspection",
    "model",
    "observation",
    "receipt",
    "scoring",
    "search",
    "selection",
}
ALLOWED_IMPORTS = {
    "claim_language": set(),
    "constants": set(),
    "errors": set(),
    "model": {"constants", "errors"},
    "formats": {"constants", "errors", "model"},
    "compile": {"constants", "errors", "model"},
    "scoring": {"compile", "constants", "errors", "model"},
    "admissibility": {"compile", "model"},
    "search": {"admissibility", "compile", "constants", "errors", "model", "scoring"},
    "selection": {"constants", "errors", "model", "scoring"},
    "artifacts": {"compile", "constants", "errors", "model", "scoring", "selection"},
    "receipt": {"constants", "errors", "model"},
    "api": {
        "admissibility",
        "artifacts",
        "compile",
        "constants",
        "errors",
        "model",
        "scoring",
        "search",
        "selection",
    },
    "observation": {"api", "compile", "constants", "errors", "model", "scoring", "search"},
    "execution": {"api", "artifacts", "constants", "errors", "formats", "model", "receipt"},
    "inspection": {
        "artifacts",
        "compile",
        "constants",
        "errors",
        "execution",
        "model",
        "receipt",
        "scoring",
    },
    "cli": {"api", "compile", "errors", "execution", "formats", "inspection"},
}


def _source_layer(relative_path: Path) -> str | None:
    """Return the declared layer for one package source path."""
    if relative_path == Path("__init__.py"):
        return None
    if relative_path.parts[0] in {"formats", "inspection"}:
        return relative_path.parts[0]
    if len(relative_path.parts) != 1:
        raise ValueError(f"unknown first-party package path {relative_path.as_posix()!r}")
    layer = relative_path.stem
    if layer not in KNOWN_LAYERS:
        raise ValueError(f"unknown first-party module {relative_path.name!r}")
    return layer


def _absolute_module(relative_path: Path, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    package_parts = ["motif_balance", *relative_path.parent.parts]
    ascend = node.level - 1
    if ascend >= len(package_parts):
        return ""
    prefix = package_parts[: len(package_parts) - ascend]
    if node.module:
        prefix.extend(node.module.split("."))
    return ".".join(prefix)


def imported_modules(relative_path: Path, node: ast.Import | ast.ImportFrom) -> set[str]:
    """Return first-party module paths imported by one AST node."""

    modules: list[str] = []
    if isinstance(node, ast.Import):
        modules.extend(alias.name for alias in node.names)
    else:
        base = _absolute_module(relative_path, node)
        modules.append(base)
        if base == "motif_balance":
            modules.extend(f"motif_balance.{alias.name}" for alias in node.names)

    return {
        module
        for module in modules
        if module == "motif_balance" or module.startswith("motif_balance.")
    }


def imported_layers(relative_path: Path, node: ast.Import | ast.ImportFrom) -> set[str]:
    """Return first-party top-level layers imported by one AST node."""

    layers: set[str] = set()
    for module in imported_modules(relative_path, node):
        parts = module.split(".")
        if len(parts) >= 2 and parts[0] == "motif_balance":
            layers.add(parts[1])
    return layers


def inspection_boundary_violations(
    relative_path: Path,
    node: ast.Import | ast.ImportFrom,
) -> list[str]:
    """Enforce verify, project, and render direction inside inspection."""

    if not relative_path.parts or relative_path.parts[0] != "inspection":
        return []
    modules = imported_modules(relative_path, node)
    if len(relative_path.parts) >= 2 and relative_path.parts[1] == "render":
        allowed = (
            "motif_balance.errors",
            "motif_balance.inspection.limits",
            "motif_balance.inspection.model",
            "motif_balance.inspection.render",
        )
        return [
            f"{relative_path}:{node.lineno}: inspection renderer must not import {module!r}"
            for module in sorted(modules)
            if not any(module == prefix or module.startswith(prefix + ".") for prefix in allowed)
        ]
    if relative_path == Path("inspection/project.py"):
        return [
            f"{relative_path}:{node.lineno}: inspection projector must not import {module!r}"
            for module in sorted(modules)
            if module == "motif_balance.inspection.render"
            or module.startswith("motif_balance.inspection.render.")
        ]
    return []


def violations_for_source(relative_path: Path, source: str) -> list[str]:
    """Return dependency violations for one package source file."""
    try:
        layer = _source_layer(relative_path)
    except ValueError as exc:
        return [str(exc)]
    if layer is None:
        return []

    errors: list[str] = []
    tree = ast.parse(source, filename=relative_path.as_posix())
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        imported = imported_layers(relative_path, node)
        for target in sorted(imported - KNOWN_LAYERS):
            errors.append(f"{relative_path}:{node.lineno}: import targets unknown layer {target!r}")
        for target in sorted(imported - ALLOWED_IMPORTS[layer] - {layer}):
            errors.append(
                f"{relative_path}:{node.lineno}: layer {layer!r} must not import {target!r}"
            )
        errors.extend(inspection_boundary_violations(relative_path, node))
    return errors


def repository_owned_paths(repo_root: Path) -> set[Path]:
    """Return tracked and nonignored untracked files, independent of cache residue."""

    if (repo_root / ".git").exists():
        result = subprocess.run(
            ("git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"),
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        return {Path(raw.decode("utf-8")) for raw in result.stdout.split(b"\0") if raw}
    return {
        path.relative_to(repo_root)
        for path in repo_root.rglob("*")
        if path.is_file() and not (_FALLBACK_IGNORED_PARTS & set(path.relative_to(repo_root).parts))
    }


def forbidden_surface_violations(owned_paths: set[Path]) -> list[str]:
    """Report forbidden source surfaces present in repository-owned content."""

    return [
        f"non-product surface must live with its owning workflow: {surface.as_posix()}"
        for surface in FORBIDDEN_PRODUCT_SURFACES
        if any(path == surface or surface in path.parents for path in owned_paths)
    ]


def main() -> int:
    """Check every package module and report all inversions."""
    if not PACKAGE_ROOT.is_dir():
        print(f"Architecture invariant failures:\n- missing package root: {PACKAGE_ROOT}")
        return 1

    errors = forbidden_surface_violations(repository_owned_paths(REPO_ROOT))
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        relative = path.relative_to(PACKAGE_ROOT)
        errors.extend(violations_for_source(relative, path.read_text(encoding="utf-8")))

    if errors:
        print("Architecture invariant failures:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Architecture invariants: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

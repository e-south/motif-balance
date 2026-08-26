#!/usr/bin/env python3
"""Enforce Motif Balance first-party dependency direction."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "src" / "motif_balance"

KNOWN_LAYERS = {
    "api",
    "artifacts",
    "cli",
    "compile",
    "constants",
    "errors",
    "formats",
    "model",
    "report",
    "receipt",
    "scoring",
    "search",
    "selection",
}
ALLOWED_IMPORTS = {
    "constants": set(),
    "errors": set(),
    "model": {"constants", "errors"},
    "formats": {"constants", "errors", "model"},
    "compile": {"constants", "errors", "model"},
    "scoring": {"compile", "constants", "errors", "model"},
    "search": {"compile", "constants", "errors", "model", "scoring"},
    "selection": {"constants", "errors", "model", "scoring"},
    "artifacts": {"constants", "errors", "model"},
    "report": {"constants", "errors", "model"},
    "receipt": {"constants", "errors", "model"},
    "api": KNOWN_LAYERS - {"api", "cli"},
    "cli": {"api", "errors"},
}


def _source_layer(relative_path: Path) -> str | None:
    """Return the declared layer for one package source path."""
    if relative_path == Path("__init__.py"):
        return None
    if relative_path.parts[0] == "formats":
        return "formats"
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


def imported_layers(relative_path: Path, node: ast.Import | ast.ImportFrom) -> set[str]:
    """Return first-party top-level layers imported by one AST node."""
    modules: list[str] = []
    if isinstance(node, ast.Import):
        modules.extend(alias.name for alias in node.names)
    else:
        base = _absolute_module(relative_path, node)
        modules.append(base)
        if base == "motif_balance":
            modules.extend(f"motif_balance.{alias.name}" for alias in node.names)

    layers: set[str] = set()
    for module in modules:
        parts = module.split(".")
        if len(parts) >= 2 and parts[0] == "motif_balance":
            layers.add(parts[1])
    return layers


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
    return errors


def main() -> int:
    """Check every package module and report all inversions."""
    if not PACKAGE_ROOT.is_dir():
        print(f"Architecture invariant failures:\n- missing package root: {PACKAGE_ROOT}")
        return 1

    errors: list[str] = []
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

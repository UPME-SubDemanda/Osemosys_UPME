#!/usr/bin/env python3
"""Validate Alembic revision IDs and heads without requiring a database."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any


VERSIONS_DIR = Path(__file__).resolve().parents[2] / "backend" / "alembic" / "versions"


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _assignment_value(tree: ast.AST, name: str) -> Any:
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return _literal(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name:
                return _literal(node.value)
    return None


def _down_revisions(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, (tuple, list, set)):
        return {item for item in value if isinstance(item, str)}
    return set()


def main() -> int:
    revisions: dict[str, Path] = {}
    referenced: set[str] = set()
    failures: list[str] = []

    if not VERSIONS_DIR.is_dir():
        print(f"Missing Alembic versions directory: {VERSIONS_DIR}", file=sys.stderr)
        return 1

    for path in sorted(VERSIONS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        revision = _assignment_value(tree, "revision")
        down_revision = _assignment_value(tree, "down_revision")

        if not isinstance(revision, str) or not revision:
            failures.append(f"{path}: missing string revision")
            continue
        if revision in revisions:
            failures.append(
                f"duplicate revision {revision}: {revisions[revision]} and {path}"
            )
        revisions[revision] = path
        referenced.update(_down_revisions(down_revision))

    missing = sorted(ref for ref in referenced if ref not in revisions)
    heads = sorted(revision for revision in revisions if revision not in referenced)

    if missing:
        failures.append("missing down_revision targets: " + ", ".join(missing))
    if len(heads) != 1:
        failures.append(
            "expected exactly one Alembic head, found "
            f"{len(heads)}: {', '.join(heads) or '<none>'}"
        )

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    print(f"Alembic graph OK: {len(revisions)} revisions, head={heads[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

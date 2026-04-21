from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path("src")

BOUNDARY_RULES = {
    "src.models": {"src.connectors", "src.harness", "src.skills", "src.tools", "src.ui"},
    "src.skills": {"src.connectors", "src.ui"},
    "src.connectors": {"src.ui"},
    "src.tools": {"src.ui"},
}


def _module_name(path: Path) -> str:
    return ".".join(path.with_suffix("").parts)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_layer_boundaries_do_not_drift():
    violations: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        module = _module_name(path)
        forbidden_prefixes = set()
        for owner_prefix, banned_prefixes in BOUNDARY_RULES.items():
            if module == owner_prefix or module.startswith(f"{owner_prefix}."):
                forbidden_prefixes.update(banned_prefixes)

        for imported in _imports(path):
            for forbidden in forbidden_prefixes:
                if imported == forbidden or imported.startswith(f"{forbidden}."):
                    violations.append(f"{module} imports {imported}")

    assert violations == []

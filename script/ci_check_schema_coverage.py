#!/usr/bin/env python3
"""Report config keys declared in components that the language schema never emits.

``script/build_language_schema.py`` can only walk voluptuous schema objects.
Keys declared behind plain function validators are invisible to it unless the
function opts in with ``@schema_extractor``. This script finds those keys by
parsing every ``cv.Optional(...)`` / ``cv.Required(...)`` in the component
sources and checking that the key appears somewhere in the generated schema.
"""

from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
COMPONENTS_DIR = ROOT / "esphome" / "components"
DEFAULT_BASELINE = ROOT / "script" / "schema_coverage_baseline.json"

KEY_MARKERS = {
    "Optional",
    "Required",
    "Inclusive",
    "Exclusive",
    "OnlyWith",
    "OnlyWithout",
}


def _const_assignments(tree: ast.Module) -> dict[str, str]:
    consts: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(
            node.value.value, str
        ):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.startswith("CONF_"):
                consts[target.id] = node.value.value
    return consts


def _rel(path: Path) -> Path:
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return None


_module_consts_cache: dict[Path, dict[str, str]] = {}


def _module_path(module: str, level: int, from_file: Path) -> Path | None:
    """Resolve an import target to a source file under the repo, if it is one."""
    if level:
        base = from_file.parent
        for _ in range(level - 1):
            base = base.parent
        parts = module.split(".") if module else []
        candidate = base.joinpath(*parts)
    else:
        if not module.startswith("esphome."):
            return None
        candidate = ROOT.joinpath(*module.split("."))
    if candidate.is_dir():
        candidate = candidate / "__init__.py"
    else:
        candidate = candidate.with_suffix(".py")
    return candidate if candidate.is_file() else None


def module_consts(path: Path) -> dict[str, str]:
    """CONF_ string constants visible in a module: its own and imported ones.

    Modules imported under a name (``import ... as df``) are included as
    ``df.CONF_X`` entries so attribute lookups resolve too.
    """
    if path in _module_consts_cache:
        return _module_consts_cache[path]
    consts: dict[str, str] = {}
    _module_consts_cache[path] = consts  # guard against import cycles
    tree = _parse(path)
    if tree is None:
        return consts
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            target = _module_path(node.module or "", node.level, path)
            if target is None:
                continue
            imported = module_consts(target)
            for alias in node.names:
                if alias.name == "*":
                    consts.update(imported)
                elif alias.name in imported:
                    consts[alias.asname or alias.name] = imported[alias.name]
                else:
                    submodule = _module_path(alias.name, 0, target.parent)
                    if submodule is None and node.level:
                        submodule = _module_path(alias.name, 1, target)
                    elif submodule is None:
                        submodule = _module_path(f"{node.module}.{alias.name}", 0, path)
                    if submodule is not None:
                        prefix = alias.asname or alias.name
                        for name, value in module_consts(submodule).items():
                            consts[f"{prefix}.{name}"] = value
        elif isinstance(node, ast.Import):
            for alias in node.names:
                target = _module_path(alias.name, 0, path)
                if target is None:
                    continue
                prefix = alias.asname or alias.name
                for name, value in module_consts(target).items():
                    consts[f"{prefix}.{name}"] = value
    consts.update(_const_assignments(tree))
    return consts


def _marker_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _is_invalid_validator(value: ast.expr) -> bool:
    # cv.invalid(...) marks removed keys that must stay out of the schema
    return isinstance(value, ast.Call) and _marker_name(value.func) == "invalid"


unresolved: list[tuple[Path, int, str]] = []


def declared_keys(component_dir: Path) -> dict[str, list[tuple[Path, int]]]:
    """Map each declared key of a component to the locations declaring it."""
    found: dict[str, list[tuple[Path, int]]] = defaultdict(list)
    for path in sorted(component_dir.rglob("*.py")):
        tree = _parse(path)
        if tree is None:
            continue
        consts = module_consts(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values, strict=True):
                if not isinstance(key, ast.Call) or not key.args:
                    continue
                if _marker_name(key.func) not in KEY_MARKERS:
                    continue
                if _is_invalid_validator(value):
                    continue
                arg = key.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    name = arg.value
                elif (
                    isinstance(arg, (ast.Name, ast.Attribute))
                    and ast.unparse(arg) in consts
                ):
                    name = consts[ast.unparse(arg)]
                else:
                    unresolved.append((_rel(path), key.lineno, ast.unparse(arg)))
                    continue
                found[name].append((_rel(path), key.lineno))
    return found


def _collect_schema_keys(obj: object, keys: set[str]) -> None:
    if isinstance(obj, dict):
        config_vars = obj.get("config_vars")
        if isinstance(config_vars, dict):
            keys.update(config_vars)
        typed_key = obj.get("typed_key")
        if isinstance(typed_key, str):
            keys.add(typed_key)
        for value in obj.values():
            _collect_schema_keys(value, keys)
    elif isinstance(obj, list):
        for value in obj:
            _collect_schema_keys(value, keys)


def schema_keys_from_dir(schema_dir: Path) -> set[str]:
    keys: set[str] = set()
    for path in schema_dir.glob("*.json"):
        _collect_schema_keys(json.loads(path.read_text(encoding="utf-8")), keys)
    return keys


def schema_keys_from_build() -> set[str]:
    """Run the schema build in-process and read its output without writing files."""
    script = ROOT / "script" / "build_language_schema.py"
    spec = importlib.util.spec_from_file_location("build_language_schema", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.args.check = True
    with contextlib.redirect_stdout(io.StringIO()):
        module.build_schema()
    keys: set[str] = set()
    _collect_schema_keys(module.output, keys)
    return keys


def component_names() -> list[str]:
    return sorted(
        p.name for p in COMPONENTS_DIR.iterdir() if (p / "__init__.py").is_file()
    )


def find_missing(
    components: list[str], schema_keys: set[str]
) -> dict[str, dict[str, list[tuple[Path, int]]]]:
    missing: dict[str, dict[str, list[tuple[Path, int]]]] = {}
    for component in components:
        declared = declared_keys(COMPONENTS_DIR / component)
        gaps = {k: v for k, v in declared.items() if k not in schema_keys}
        if gaps:
            missing[component] = gaps
    return missing


def load_baseline(path: Path) -> dict[str, set[str]]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {component: set(keys) for component, keys in data.items()}


def write_baseline(
    path: Path, missing: dict[str, dict[str, list[tuple[Path, int]]]]
) -> None:
    data = {component: sorted(keys) for component, keys in sorted(missing.items())}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schema-dir",
        type=Path,
        help="Read generated schema JSON from this directory instead of building",
    )
    parser.add_argument(
        "-c",
        "--components",
        nargs="*",
        help="Only check these components (default: all)",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="Known gaps that do not fail --check",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Write the current gaps to the baseline file",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when a gap is not in the baseline",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Also list key declarations whose name could not be resolved",
    )
    args = parser.parse_args()

    schema_keys = (
        schema_keys_from_dir(args.schema_dir)
        if args.schema_dir
        else schema_keys_from_build()
    )
    components = args.components or component_names()
    missing = find_missing(components, schema_keys)

    if args.update_baseline:
        write_baseline(args.baseline, missing)
        print(f"Wrote {args.baseline}")
        return 0

    baseline = load_baseline(args.baseline) if args.check else {}
    new_gaps = 0
    total = 0
    for component, gaps in sorted(missing.items()):
        known = baseline.get(component, set())
        for key, locations in sorted(gaps.items()):
            total += 1
            if key in known:
                continue
            new_gaps += 1
            path, line = locations[0]
            print(f"{path}:{line}: {component}: '{key}' is not in the language schema")

    if args.verbose:
        for path, line, name in unresolved:
            print(f"{path}:{line}: key name {name} could not be resolved statically")
    print(
        f"{total} keys in {len(missing)} components are not in the language schema"
        f" ({len(unresolved)} declarations unresolved)"
        + (f", {new_gaps} not in the baseline" if args.check else "")
    )
    if args.check and new_gaps:
        print(
            "Validators that build a schema in code must opt in with "
            "@schema_extractor (see esphome/schema_extractors.py), "
            f"or add the key to {_rel(args.baseline)}"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
